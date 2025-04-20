# Base Map Level44 on PAL 

## Big‐Picture Flow
```
[Some Unknown Caller]    
         |
         v
  0x00512DBC : "Master State Handler"
  ----------------------------------
  - Checks player's high-level state 
  - Decides whether to do jump logic, 
    or some other movement code

  Calls -> 0x004F4CF8 if it determines
           the player is in a "jump" state
```

## Inside 0x004F4CF8 : General Jump Routine

```
              0x004F4CF8 : "General Jump Routine"
              -----------------------------------
    1)  Obfuscation Checks
        - The code reads bytes like [s0+0x19E4], [s0+0x19E6], 
          and [s0+0x313] using a "scrambler" table at 0x003B6EA0.
        - If certain states aren't met, it branches around 
          or skips further jump actions.

    2)  Subroutine Calls
        - The function may call:
             pos_004F89A8, pos_004F8A48, pos_004F8668, 
             pos_004F8928, pos_004F8DF0, etc.
        - These subroutines handle pieces of 
          movement, collision, or camera logic.

    3)  Jump Pad Calculation (the “jump pad snippet”)
        - Occurs if conditions show the player is using 
          a jump pad, or has extra vertical thrust.
        - Reads/writes memory at offsets like [0x14B8], [0x14BC], 
          [0x14C0], [0x14C4] (these hold partial thrust values).
        - Does math like:
            thrust = sqrt( 2.0 * currentValue * someScale ) 
            subtract offsets
            store final thrust in [0x14C0]
        - If the result is > 0.0, it calls 
          NameGuess_004F8D58 to do that "16‐byte copy + add f12" step.

    4)  Float Loads (Hard‐coded Values)
        - **Where we see `lui at,0x39D1; ori at,0xB718; mtc1 at,f00`**:
          This happens in the middle of the jump code 
          to load a specific float into `f00`. 
          It’s often a small positive number 
          (like ~0.06 or 0.07) or negative value 
          used for some aspect of jump math.
        - The code compares it, adds or multiplies it 
          with the player's current jump values.

    5)  Final Updates & Return
        - The routine may store final velocity 
          or position updates back into the player struct,
          reset certain flags, then returns.
```

## Entry Point: NameGuess_004F8D58

- Takes three parameters (`a0`, `a1`, `a2`).
- `a0` is usually `s1` (player struct) or a movement-related structure.
- `a1` and `a2` are often related to movement calculations (e.g., position updates or a jump velocity vector).

```
1) Register i/o
   - Extracts (likely movement) vectors from memory
   - Checks if the movement update is valid.
2) Movement Calcuation 
   -  Use float math (`mtc1`) to load values into FPU registers.
   -  Performs conditional movement updates:
   -    If movement values > threshold, clamp.
   -    If movement is ~0, reset velocity (prevents floating/stuck motion).
3) Calls to Other Functions
| pos_004F530A0 | Likely clamps movement values, ensuring jumps don’t exceed a max height. |
| pos_004F53250 | Adjusts movement based on a computed force (e.g., gravity, external forces). |
| pos_004F53060 | Updates player velocity or acceleration based on computed physics. |

4) Apply Final Movement Updates
   - Stores new movement values back to the player struct
   - Ensures player velocity changes are within expected ranges.
   - Adjusts player position or forces applied.
  
5) Return logic and jump to return address
```

## After the Jump Routine

```
  After 0x004F4CF8 finishes:
  - Control returns to Master Handler 0x00512DBC
```

## Map
| Offset (Hex) | Variable Name & Source Definition | Opcode Read Address(es) | Opcode Write Address(es) | Notes |
|-------------|----------------------------------|-------------------------|--------------------------|-------|
| 0x14AC      | **Unknown**                      | `0x004F4E30`            | `0x004F51A0`             | Used in jump logic |
| 0x14AD      | **Unknown**                      | `0x0051364C`            | `0x00513678`             | Possibly jump-related flag |
| 0x14AE      | **Unknown**                      | `0x005136E0`            | `0x00513700`             | Written when jump logic activates |
| 0x14B0      | **Unknown**                      | `0x004F4E60`            | `0x004F4E68`             | Used in jump calculation |
| 0x14B4      | **Unknown**                      | `0x00512EEC`            | `0x00512EFC`             | Jump physics calculation |
| 0x14B8      | **Unknown**                      | `0x004F50C0`            | `0x004F5150`             | Related to vertical movement |
| 0x14BC      | **Unknown**                      | `0x004F4DB8`, `0x00512EB0` | `0x004F5150`       | Some form of vertical check |
| 0x14C0      | **Unknown**                      | `0x004F4FE4`            | `0x004F5150`             | Jump height determination |
| 0x14C4      | **Unknown**                      | `0x004F50B0`            | `0x004F50C0`             | Used in gravity calculations |
| 0x19E4      | `uint8_t state;`                 | `0x004F4D34`, `0x00512DF0` | `0x004F4D58`, `0x00512E18` | Determines player's current state |
| 0x19E6      | `uint8_t stateType;`             | `0x004F0A2C`            | `0x004F0BAC`             | Determines type of current state |
| 0x1A08      | `uint8_t raisedGunArm;`          | `0x004F0C28`            | `0x004F0D4C`             | Possibly affects jump physics |
| 0x1A14      | `uint8_t isLocal;`               | `0x00513700`            | `0x00513840`             | Checks if the player is local |
| 0x1A18      | `uint8_t handGadgetType;`        | `0x004F0E0C`            | `0x004F0F30`             | Possibly used for gadget interactions |
| 0x1DC0      | `Vector3 failsafePosRing[32];`   | `0x004F5308`            | `0x004F74D0`             | Stores past positions for rollback safety |
| 0x2040      | `Quaternion gadgetRotRing[16];`  | `0x004F0F98`            | `0x004F1010`             | Rotation memory buffer, might affect jumps |
| 0x2340      | `uint8_t rotZringIndex;`         | `0x004F1358`            | `0x004F1390`             | Might track rotational state for jump logic |
| 0x2484      | `float skidDeceleration;`        | `0x004F5010`            | `0x004F5150`             | Possibly modifies ground interaction |
| 0x2490      | `uint8_t deathFallChannel;`      | `0x004F519C`            | `0x004F51A0`             | Could relate to falling detection |
| 0x2498      | `float moonJumpIdealHeight;`     | `0x004F1350`            | `0x004F1380`             | Possibly used for jump height calculation |
| 0x249C      | `float moonJumpGravity;`         | `0x004F51A0`            | `0x004F530C`             | Affects jump physics |
| 0x2501      | `uint8_t lastDeathWasSuicide;`   | `0x004F1340`            | `0x004F1360`             | May alter respawn/jump behaviors |
| 0x251B      | `uint8_t playerType;`            | `0x004F12E8`            | `0x004F1310`             | Determines behavior based on player type |
| 0x2520      | `PlayerConstants *playerConstants;` | `0x004F12E0`        | `0x004F1330`             | Holds constants affecting movement |
