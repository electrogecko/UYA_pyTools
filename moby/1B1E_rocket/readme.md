# Rocket Class 0x1B1E — Struct & Spawn Reference

**Map:** Hoven Gorge MP (NTSC), `code/*.bin`  
**Patch context:** `patch_5588_tank.py` (current implementation, we'll call this 'stk41')    
**Code segment:**  
All addresses below reside in `code.0006.bin` (base `0x003C4980`).  
Patches translate VA → file offset using:

## Scope and structure of this file

Class `0x1B1E` is the in-flight rocket moby. It is allocated by the factory `spawnRocket1B1E` at `0x0042A570` and ticked by the rocket-update FSM at `0x0042A020`. The two interesting "structs" are:

1. **The rocket pvar** — game-allocated block whose pointer lives at `Moby.pVar (Moby+0x68)`. The factory writes a fixed set of fields here at spawn; the update FSM reads them every frame. This is the durable struct definition.
2. **The rocket Moby itself** — a stock `Moby` (see `horizon-uya-patch/libuya/include/moby.h`), with class-specific touches at spawn time.

A note on heat-seeking / homing: **homing lives inside this struct.** Pvar `+0x24` is the target moby pointer and pvar `+0x28` is the steering/turn-rate clamp; they only have meaning together with the FSM at `0x42A020`. Splitting homing into a separate file would duplicate those rows. Instead, this file has one **Homing pipeline** section after the struct tables.

---

## 1. Certainties

### 1.1 Rocket pvar layout (written by `spawnRocket1B1E` @ `0x0042A570`)

All offsets are from the pvar base (`Moby+0x68 → pVar`). All stores below are from straight disassembly of the factory; the only entry with non-trivial conditional logic is `+0x24` (target), which is written only after a two-stage validation.

| Offset | Size | Field                | Source at spawn      | Consumer / meaning                                                                                  | Notes                                                                                                  |
| ------ | ---- | -------------------- | -------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `0x10` | u16  | `lifetime`           | `t2` (factory arg)   | Decremented every frame by `0x0045DDE8`; rocket detonates when it hits 0.                            | Stored as hword countdown. `u16` max 65535. stk41 patch passes `600` (≈10 s @60 fps).                  |
| `0x14` | ptr  | `shooter`            | `a0` (factory arg)   | Owner moby pointer (the firer). Used by damage-event apply.                                          | For tank fire: tank moby. For minirocket: player moby.                                                 |
| `0x18` | u32  | `a3_pass`            | `a3` (factory arg)   | Passthrough; purpose **uncertain** — see §2.                                                         | stk41 tank patch passes `0`.                                                                           |
| `0x1C` | u32  | `t0_mask`            | `t0` (factory arg)   | Likely collision/team mask; passed through to `SpawnMoby` via `[sp+0x14]` and surfaced on rocket.    | Stock minirocket wrapper passes `0x80FFFFFF`. stk41 tank patch passes `0` (proved neutral). **Partial.**|
| `0x20` | f32  | `f12_scalar`         | `f12` (factory arg)  | Scalar; named `speed/scale` in early notes. **Uncertain** which physics scalar — see §2.             | stk41 tank patch passes `0.0` and rockets behave correctly, suggesting it is not load-bearing for homing.|
| `0x24` | ptr  | `target`             | `t1` (after gate)    | Target moby pointer consumed by rocket-update homing FSM at `0x42A020`.                              | Written only if `t1 != 0` AND `0x00480870(t1) != 0` AND the secondary byte-gate at `0x42A6A8` passes. stk41 patches `0x42A6A8` from `beqz` → unconditional `b` to force the accept branch. |
| `0x28` | f32  | `turn_rate_clamp`    | `f13` (factory arg)  | **Critical for homing.** Used as steering/turn-rate clamp inside `0x42A020`. Zero here → no steering, even with a valid `+0x24`. | stk41 tank patch passes `2.0f` (reused F11 holding `MUZZLE_Z`). The "rockets dumbfire even with target" bug was this field being `0`. |
| `0x2C` | f32  | `f14_scalar`         | `f14` (factory arg)  | Speed scalar (rocket flight speed). **Confirmed by behaviour** (changing it changes rocket speed); exact units / clamp not measured. | stk41 tank patch passes `2.0f` (`ROCKET_SPEED_F14`).                                                   |

**Field-source proof:** dump at `tools/doc/codex_rocket` lines 56–64 ("writes key rocket-pvar fields") and `tools/doc/rocketnotes` §1–§6. Watch site for the conditional `+0x24` store: `0x0042A6B8`.

### 1.2 Factory call contract — `spawnRocket1B1E` (`0x0042A570`)

Argument register → pvar field mapping is consistent across the disassembly and the prologue saves (`a0→s7`, `a1→s0`, `a2→s6`, `t1→s5`, `t2→s8`, `f12→f22`, `f13→f21`, `f14→f20`).

| Reg     | Type            | Role                                              | stk41 tank value                                  |
| ------- | --------------- | ------------------------------------------------- | ------------------------------------------------- |
| `a0`    | `Moby*`         | shooter moby (saved → `s7`; written to pvar `+0x14`) | tank moby                                         |
| `a1`    | `VECTOR*`       | spawn position (saved → `s0`; `lq` loads qword)   | `(tank.x + fwd*4, tank.y + fwd*4, tank.z + 2.0)`  |
| `a2`    | `VECTOR*`       | direction / orient seed (saved → `s6`; used for orient build) | `(fwd.x, fwd.y, 0, 0)`                            |
| `a3`    | u32             | passthrough → pvar `+0x18` and `[sp+0x10]` to SpawnMoby | `0`                                               |
| `t0`    | u32             | passthrough → pvar `+0x1C` and `[sp+0x14]` to SpawnMoby | `0`                                               |
| `t1`    | `Moby*` (target) | candidate target → pvar `+0x24` (gated, see §1.1) | result of A1/A picker (see §1.4)                  |
| `t2`    | u16             | lifetime → pvar `+0x10`                            | `600` (`ROCKET_LIFETIME`)                         |
| `f12`   | f32             | → pvar `+0x20`                                     | `0.0f`                                            |
| `f13`   | f32             | → pvar `+0x28` (turn-rate clamp / homing)          | `2.0f` (must be nonzero)                          |
| `f14`   | f32             | → pvar `+0x2C` (speed scalar)                      | `2.0f` (`ROCKET_SPEED_F14`)                       |

Stock caller is `0x0042104C` inside the minirocket fire wrapper `0x00420CB8`. At `0x00421034` it does `lw t1, 0x220(s2)` — i.e. the stock fire path reads a *cached* target out of weapon state, not a fresh broadphase result.

### 1.3 Touches on the rocket Moby at spawn (selected)

Standard `Moby` layout (per `horizon-uya-patch/libuya/include/moby.h`) applies. Spawn-time class-specific writes confirmed in the factory:

| Moby offset | Field                  | Spawn-time behaviour                                                              |
| ----------- | ---------------------- | --------------------------------------------------------------------------------- |
| `0x10`      | `position` (VECTOR)    | Set from `a1` via `sq` of the loaded qword.                                       |
| `0x34`      | `modeBits` (u16)       | OR'd with `0x100` (active-projectile flag).                                       |
| `0x68`      | `pVar`                 | Allocated block — recipient of every store in §1.1.                               |
| `0xAA`      | `oClass`               | `0x1B1E` (set by `SpawnMoby(class=0x1B1E, flags=0x80, …)` via `jal 0x00476680`).  |

Additional Moby-side writes for orientation/velocity (around offsets `0x20..0x2C`) are noted in `tools/doc/rocket.txt` but are **not yet pinned** to specific fields; see §2.

### 1.4 Damage path (rocket update `0x0042A020`)

Two damage-event call sites into constructor `0x00482698` exist. Tank rockets always land in **site 1** at `0x42A2A0` (the `s4+0x2C >= 0` branch). Stock site 1 passes `f12 = 0.0f` — visible hit FX, zero HP loss. stk41 patches:

| VA           | Stock word    | Patched word    | Effect                                              |
| ------------ | ------------- | --------------- | --------------------------------------------------- |
| `0x0042A27C` | `0x00000000` (nop) | `0x3C060001` (`lui a2, 1`)        | Restore `a2 = 0x10001` flags (event +0x14).         |
| `0x0042A284` | `0x00000000` (nop) | `0x34C60001` (`ori a2, a2, 1`)    | …continued.                                         |
| `0x0042A28C` | `0x3C060001` (`lui a2, 1`) | `0x3C014248` (`lui at, 0x4248`) | Stage `at = 50.0f` upper.                           |
| `0x0042A2A4` | `0x34C60001` (`ori a2, a2, 1`) | `0x44816000` (`mtc1 at, f12`) | Damage amount `f12 = 50.0f` written to event `+0x1C`. |
| `0x0042A6A8` | `0x10600003` (`beqz v1,+3`) | `0x10000003` (`b +3`)         | Force the `+0x24 = t1` accept branch (see §1.1).    |

### 1.5 Reusable Hoven NTSC globals & helpers (homing context)

| Address       | Symbol / role                                 | Notes                                                                           |
| ------------- | --------------------------------------------- | ------------------------------------------------------------------------------- |
| `0x0042A570`  | `spawnRocket1B1E`                             | Rocket factory (this doc).                                                      |
| `0x0042A020`  | rocket update / homing FSM                    | Reads pvar `+0x24` (target) and `+0x28` (turn-rate). Watch sites: `0x42A0BC` revalidate, `0x42A104` clear. |
| `0x00480870`  | target validator                              | `a0 = moby`. Returns `*(moby->pVar + 0)` iff `moby != 0 && pVar != 0 && (modeBits & 0x20)`. Returns `0` otherwise. |
| `0x00450AD8`  | cone / spatial-hash broadphase query          | `a0=&fwd, a1=mode, a2=filter, a3=0, f12=cone scale`. Writes candidate moby pointers to `0x0025FCC0`; returns count in `v0`. |
| `0x0045E1B8`  | VU0 vector scale/write helper                 | Used twice during stock minirocket query build (with `f12 = -1.0`, then `f12 ≈ 0.275`). |
| `0x00476680`  | `SpawnMoby`                                   | `a0=class, a1=flags`. Used by the factory with class `0x1B1E`, flags `0x80`.    |
| `0x0048F448`  | link/init owner                               | Called by factory as `(newMoby, shooter)`.                                      |
| `0x0045DDE8`  | per-frame countdown ticker                    | Decrements pvar `+0x10` lifetime hword.                                         |
| `0x0025FCC0`  | broadphase result list                        | NULL-terminated moby-ptr list filled by `0x450AD8`.                             |
| `0x002496B0`  | player table base                             | Used by A1 picker.                                                              |
| `0x002487DC`  | live moby list begin ptr                      | Used by A picker (live walk).                                                   |
| `0x002487E4`  | live moby list end ptr                        | `BEGIN + 8`.                                                                    |
| `0x0025BC40`  | `CollOutput` (unrelated to rockets but in scan helper) | `+0x18 pMoby`, `+0x20 ip`, `+0x30 push`.                                |

### 1.6 Homing pipeline summary

The minimum to make a rocket home is:

1. Pass a **valid target moby pointer** in `t1` to `0x42A570`. "Valid" means it survives `0x00480870` (non-null, has a pvar, `modeBits & 0x20` set). The stk41 picker is A1 (player table) → A (live moby walk).
2. Pass a **nonzero `f13`** (turn-rate clamp). Zero here is the actual cause of "selected target but rocket flies straight."
3. The factory's secondary byte-gate at `0x42A6A8` is patched to unconditional in stk41 — without that, otherwise-usable targets get discarded before the `+0x24` store. **Whether this is still required after class filtering tightens is open** — see §2.

Stock minirocket scans continuously, caches the target into weapon state (`*(s2 + 0x220)`), and only at fire time loads it into `t1`. The stk41 path performs the pick at fire time instead. Functionally equivalent for downstream homing; differs in feel.

---

## 2. Uncertainties

These are gaps where a cleaner pass over `code.0006.bin` (e.g. tracing `s2` initialization for the minirocket wrapper, or watching memory writes in PCSX2) could turn an entry from §1 into a confirmed fact.

- **pvar `+0x18` (`a3_pass`):** purpose unknown. Factory pushes `a3` to `[sp+0x10]` for `SpawnMoby` and stores it to pvar `+0x18`, but no consumer of pvar `+0x18` has been identified inside `0x42A020`. stk41 passes `0` and rockets fly fine. Likely a flag word, but identity unverified.
- **pvar `+0x1C` (`t0_mask`):** stock minirocket passes `0x80FFFFFF`; stk41 passes `0`; no observable difference. Hypothesis is collision/team mask written onto the rocket Moby (factory pushes it to `[sp+0x14]` as `SpawnMoby` arg). Confirming would mean watching the `SpawnMoby` consumer of `[sp+0x14]` and finding the resulting Moby field.
- **pvar `+0x20` (`f12_scalar`):** stk41 passes `0.0` and rockets steer; stock minirocket passes nonzero. Whether this is a homing strength, an initial-speed boost, or unused-on-the-tank-path cannot be answered without targeted experiments. Early notes called it "speed/scale" but that may be a guess copied from the register name.
- **Rocket Moby fields at `+0x20..+0x2C`:** its specultaed that "+0x20=vel?, +0x28/+0x2C=orient floats". These are guesses from `sq` writes in the factory. The orientation matrix is built using `0x00478040` (norm?) and `0x00451240` (cross?) but the exact destination field assignments are not yet pinned down. **Direct inspection of `code.0006.bin` at `0x42A570 + ~0xC0..0x100` would resolve this** — the relevant `sq` instructions are immediately after the orientation build.
- **Rocket Moby `+0x24 = 0.5f` if caller flag `0x80`:** Conditional on a caller flag whose source is unidentified. Worth re-reading the factory bytes to confirm the immediate.
- **Secondary target gate at `0x42A6A8`:** stk41 patches this from `beqz v1,+3` → unconditional `b +3`. The original gate inspects a byte derived from the validator `0x480870` return. Whether the gate is genuinely needed once class filtering on the picker side is tighter (e.g. only accept hostile/player classes) is **open**; stk41 currently brute-forces it open for testing.
- **Stock weapon-state `+0x220`:** the stock fire path does `lw t1, 0x220(s2)`. `s2` is the weapon-state struct; `+0x220` is the cached lock-on target moby pointer. The full lifecycle (when written, when cleared, what struct lays it out) is not mapped.
- **Lock-strength float at `0x21AD0680 + 4`:** its been observed that a `[0,1]` lock-quality float at `0x21AD0680 + 4` for minirocket; tank does not write it. Whether this is sourced from / written by the lock-on FSM in `0x004004F8`, and whether it gates anything beyond UI, is unmapped. Probably weapon-state sibling to `+0x220` but not confirmed. Perhaps this is used for reticule color-strength mapping, just a guess. 
- **Continuous-scan port:** stk41 implentation is at time-of-fire. The minirocket scans continuously per-frame and cachess. The cache slot inside our implemtation is undecided; the rocket-side struct in §1.1 is unaffected by that decision.
