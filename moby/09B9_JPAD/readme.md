# HOVEN LEVEL41 NTSC RAC3
## The Hero Controller Singleton

The global at 0x001A4BE0 (level24) is the **hero controller runtime workspace** -
It is a large runtime data area used by the hero state
machine. Some notable offsets include:

| Offset | Type    | Description |
|--------|---------|-------------|
| +0x00F0| VECTOR  | **Per-frame displacement accumulator** (X, Y, Z, W) |
| +0x00F8| float   | Z component of displacement (vertical) |
| +0x01B8| int     | Frame counter |
| +0x0478| float   | Current height parameter (ramping) |
| +0x0480| float   | Pending delta (per-frame, cleared after apply) |
| +0x0484| float   | Accumulated total displacement applied so far |
| +0x04D8| float   | Start height = gp[-3272] |
| +0x04DC| float   | Target height = gp[-3272] + 1.0 |
| +0x04E8| short   | Step count = 17 frames |
| +0x04F0| float   | Gravity param = gp[-3268] / 3600 |
| +0x25C0| Player* | Pointer to the current Player struct |
| +0x25C4| int     | Hero state/action ID |
| +0x25F4| u8      | Coordinate mode flag (0=simple, 1-2=matrix-transformed) |

Note, this is distinct from the Player struct at `*(hero+0x25C0)`, which contains
the `HeroMove move` field at player+0x0120.

## The Displacement Vector (+0xF0)

The VECTOR at hero+0x00F0 is the **per-frame displacement accumulator**.
Multiple subsystems write into it during a frame:

- Arc updater (0x4D2A24): writes launch delta into Z via 0x4F2098
- Ground movement: writes XY movement via 0x4F1D20, 0x4F2320
- Gravity: writes gravity delta via the same vector functions

The function 0x4F2098 (`HeroApplyDisplacementZ`) does this in the simple path
(when hero+0x25F4 == 0):

```c
void HeroApplyDisplacementZ(VECTOR *disp, VECTOR *src, float delta) {
    // simple: just add delta to Z component
    disp->z += delta;       // disp[2] += delta
}
```

## The Arc Physics 

Function at 0x4D2650 (per-frame hero jump/fall updater), arc section at 0x4D2A24.
pseudocode:
```c
// hero = 0x001A4BE0 (global base)
float h      = hero->launchHeight;    // +0x478
float target = hero->launchTarget;    // +0x4DC
float start  = hero->launchStart;     // +0x4D8
short steps  = hero->launchSteps;     // +0x4E8 (17)
float grav   = hero->launchGravity;   // +0x4F0

// Ramp height toward target
if (h < target) {
    float step = (target - start) / (float)steps;
    h = h + step;
    if (h > target) h = target;
    hero->launchHeight = h;           // +0x478
}

// Compute displacement
float total_vel = sqrtf(2.0f * h * grav);
float prev_sum  = hero->accumDelta;   // +0x484
float pending   = hero->pendingDelta; // +0x480

float delta = total_vel - prev_sum - pending;
hero->pendingDelta = pending + delta; // +0x480

// Apply if positive and frame count allows
if (hero->pendingDelta > 0.0f) {
    HeroApplyDisplacementZ(&hero->dispVec, &hero->dispVec, hero->pendingDelta);
    // Transfer pending to accumulated, clear pending
    hero->accumDelta += hero->pendingDelta;  // +0x484
    hero->pendingDelta = 0.0f;               // +0x480
}
```

Semantics: `pendingDelta` simplifies each frame to
`sqrt(2*h*g) - accumDelta`, because:
  delta = sqrt(2*h*g) - accumDelta - pending
  new_pending = pending + delta = sqrt(2*h*g) - accumDelta
Then after apply: accumDelta += new_pending => accumDelta = sqrt(2*h*g)

So the net upward displacement after N frames = sqrt(2 * h_N * g), where h_N
ramps from start toward target over 17 frames. This produces a smooth
accelerating upward curve, rather than a constant velocity.

When the coordinate mode flag is nonzero (1 or 2), it instead rotates the
displacement through a matrix at hero+0x40 via 0x3F4750 and 0x3F43F0 before
storing - this handles camera-relative or world-relative coordinate transforms.

## Approach: Bypass SP Arc Physics, Use FALL + Velocity Impulse
The SP launch chain (state 134 -> arc updater -> hero singleton displacement
vector -> HeroMove decomposition) was too complex to transplant into MP.
Instead, the hook directly:

## How Displacement Reaches the Player

The displacement vector at hero+0xF0 is consumed by the **hero movement
pipeline finalization** - the code that runs after all per-frame movement
sources have accumulated their contributions. Namely:

1. Per-frame sources write into hero+0xF0 (arc updater, gravity, ground move)
2. The hero update loop (containing function 0x4D2650) is called from
   the main per-frame updater at ~0x4DBD80 / 0x4DC5B0 / 0x4DE064
3. After 0x4D2650 returns, the caller pipeline copies the accumulated
   displacement into the Player struct's **HeroMove** fields:
   - `player->move.behavior` (VECTOR at player+0x0120)
   - `player->move.actual` (VECTOR at player+0x0140)
4. The HeroMove is then applied to the player's moby position

The HeroMove struct (at player+0x0120, size 0xA0):

| Offset (in HeroMove) | Player offset | Field |
|---|---|---|
| +0x00 | 0x0120 | VECTOR behavior (intended movement) |
| +0x08 | 0x0128 | behavior.Z (vertical intent) |
| +0x20 | 0x0140 | VECTOR actual (post-collision movement) |
| +0x28 | 0x0148 | actual.Z (vertical realized) |
| +0x8C | 0x01AC | float ascent |
| +0x90 | 0x01B0 | float zSpeed |

The exact transfer from hero singleton to player HeroMove involves the
rotation/projection functions (0x4F1D20, 0x4F22C8) that decompose the
displacement vector into behavior/actual/ascent/zSpeed components.

1. Clears ground state (detach player from pad)
2. Sets player state to FALL (6) !! FALL_STATE 6 allows freedom of movement, unlike the default behavior of 0x9B9
3. Writes an upward velocity impulse to HeroMove fields
4. Lets the game's existing FALL per-frame gravity produce the arc

## Parameters
- **State**: FALL (6) - no init-side velocity override, gravity-only per-frame
- **Velocity**: 10.0 (0x41200000) - written to behavior.z, actual.z, ascent, zSpeed
- **Peak height**: ~v0^2/(2g) where g is the game's per-frame gravity constant
- **Ground clear**: pMoby and onGood zeroed before setState to prevent crash and re-trigger

## Hook Assembly (29 instructions at 0x554378)
Entry context from patched compare at 0x5235A0:
- v1 = ground moby oClass
- v0 = 0x10C4 (original compare value)
- s1 = player struct pointer

```
 0: beq  v1, v0, native_10c4    ; class == 0x10C4?
 1: addiu v0, zero, 0x09B9      ; (delay) load 0x09B9 for next compare
 2: bne  v1, v0, no_match       ; class != 0x09B9? fall through
 3: nop

--- 0x09B9 launch ---
 4: sw   zero, 0x02CC(s1)       ; ground.pMoby = NULL (BEFORE setState)
 5: sw   zero, 0x02D0(s1)       ; ground.onGood = 0
 6: lw   v1, 0x0014(s1)         ; v1 = player->vtable
 7: daddu a0, s1, zero           ; a0 = player
 8: addiu a1, zero, 6            ; a1 = FALL
 9: addiu a2, zero, 1
10: daddu a3, zero, zero
11: lw   v0, 0x0034(v1)         ; v0 = vtable->setState
12: jalr v0                      ; setState(player, 6, 1, 0)
13: addiu t0, zero, 1            ; (delay)

--- velocity impulse (s1 preserved across jalr) ---
14: lui  at, 0x4120              ; at = 10.0f upper bits
15: mtc1 at, $f0                 ; $f0 = 10.0
16: swc1 $f0, 0x0128(s1)        ; move.behavior.z = 10.0
17: swc1 $f0, 0x0148(s1)        ; move.actual.z = 10.0
18: swc1 $f0, 0x01AC(s1)        ; move.ascent = 10.0
19: swc1 $f0, 0x01B0(s1)        ; move.zSpeed = 10.0

--- return ---
20: j    0x528650                ; STATE_SET_RETURN_ADDR
21: daddu v0, zero, zero         ; (delay)

--- native 0x10C4 handler (Moon Jump pads) ---
22: lw   v1, 0x0014(s1)
23: daddu a0, s1, zero
24: j    0x523670                ; original 0x10C4 handler
25: addiu a1, zero, 131          ; (delay) MOON_JUMP state

--- no match: original code path ---
26: lbu  v0, 0x19E4(s1)         ; displaced original instruction
27: j    0x5235BC                ; continue original compare chain
28: nop
```
