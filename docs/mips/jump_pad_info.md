# Jump anywhere on Bakisi

`patch=1,EE,20413608,extended,24020001`

## Identifying Address Ranges: Jump Pad-Only vs. Continuous Execution

To add context around relevant instructions, we will divide **MIPS memory regions** into two categories:

## **Jump Pad-Specific Execution (Triggered Only on Use)**

| **Address Range** | **Instruction Example** | **Estimated Behavior** |
|------------------|------------------------|-------------|
| `0x00413608`    | `lw v0, 0x02F0(v0)` *(before patch)* | Loads a **jump-related value** from memory. |
| `0x0041360C`    | `bnezl v0, pos_00413780` | Branches based on whether the jump is triggered. |
| `0x00413610 - 0x00413780` | *(Skipped when patched!)* | **Jump pad setup, calculations, function calls.** |
| `0x0041377C`    | `dmove s4, s7` | Related to **setting up motion parameters.** |

### **Why These Are Event-Driven**
- `0x00413608` is only reached **when stepping onto the jump pad**.
- If the jump pad is **not in use**, this address range is **never accessed**.

---

## **Continuous Execution (Always Running, Even When Not Using Jump Pad)**

| **Address Range** | **Instruction Example** | **Behavior** |
|------------------|------------------------|-------------|
| `0x00413780`    | `slti v0, s4, 0x0008` | A **global check**, always executed. |
| `0x00413784`    | `bnez v0, pos_00413340` | **If `s4 < 8`, branches to `0x00413340`.** |
| `0x00413340 - 0x00413354` | *(Memory lookups, conditionals)* | Accesses global memory (`0x0025xxxx` region). |
| `0x00413A00 - 0x00413B08` | *(State updates, velocity calculations)* | **Ongoing motion adjustments.** |

# Branch Execution (If Not Patched)

If the patch **was not applied**, execution would **not** force the branch at `0x0041360C`, meaning the original logic would run. Below is a breakdown of **what would happen in the normal case** when using the jump pad.

---

## **Branch Behavior at `0x0041360C` (Without Patch)**

| **Address** | **Instruction** | **Analysis (Best Guess)** |
|------------|---------------|---------------------------|
| `0x00413608` | `lw v0, 0x02F0(v0)` | Loads a value from memory (possibly jump velocity, timer, or activation flag). |
| `0x0041360C` | `bnezl v0, pos_00413780` | **If `v0 ≠ 0`, jump to `0x00413780`. Otherwise, continue normal execution.** |
| `0x00413610` | `dmove s4, s7` | Stores a value (possibly jump state) into `s4`. |
| `0x00413614` | `li a0, 0x1` | Loads `1` into `a0` (activation flag). |
| `0x00413618` | `dmove a1, zero` | Sets `a1 = 0`, possibly resetting some parameter. |
| `0x0041361C` | `jal pos_004C33D8` | **Calls a function (`0x004C33D8`)**, likely handling **jump initialization or physics setup**. |
| `0x00413620` | `dmove a2, s5` | Moves a value into `a2`, likely related to jump parameters. |
| `0x00413624` | `addiu v1, s3, 0x130` | Adjusts an offset (`s3 + 0x130`), likely pointing to a **player state or physics struct**. |
| `0x00413628` | `addu s1, v1, s6` | Adds another value to `s1`, possibly **indexing a jump-related structure**. |
| `0x0041362C` | `lw v0, (s1)` | Loads a **counter or jump pad state** into `v0`. |
| `0x00413630` | `addiu v0, 0x1` | Increments the counter. |
| `0x00413634` | `slti v1, v0, 0x000C` | Compares `v0` to `12`. If `v0 < 12`, continue; otherwise, reset. |
| `0x00413638` | `bnez v1, pos_00413644` | **If `v1 ≠ 0`, jump to `0x00413644`.** Otherwise, reset counter. |
| `0x0041363C` | `sw v0, (s1)` | Stores updated jump state. |
| `0x00413640` | `sw zero, (s1)` | **Resets jump counter if condition was met.** |

---

## **Continuation at `0x00413644` (Normal Jump Execution)**
If the jump pad logic continues instead of being skipped, it follows:

| **Address** | **Instruction** | **Analysis (Best Guess)** |
|------------|---------------|---------------------------|
| `0x00413644` | `lw v1, (s1)` | Reloads the **jump state variable**. |
| `0x00413648` | `li a1, -0x1` | Loads `-1` into `a1`, possibly for **fall-time tracking**. |
| `0x0041364C` | `lui a2, 0x0024` | Loads **upper 16 bits of an address**. |
| `0x00413650` | `addiu a2, 0x7600` | Adjusts `a2`, possibly an address in **physics memory**. |
| `0x00413654` | `sll s0, s4, 0x04` | Shifts `s4` left by 4 (multiplying by 16), possibly **indexing an array of physics values**. |
| `0x00413658` | `slt a1, v1` | Compares `a1` and `v1`, likely checking if the **jump should continue**. |

---

## **Effects of Running This Unpatched**
- The **jump pad runs its full initialization sequence** instead of being immediately redirected.
- The function call to `0x004C33D8` **possibly processes velocity, gravity, or animation states**.
- The **jump counter at `s1` is properly updated**, which might influence **jump height or force**.
- The **physics data at `0x00247600` is actively modified**, meaning the jump interacts with the physics system properly.
- **Skipping this (as the patch does) avoids these calculations**, which may cause unintended behavior.

---

## **What Happens If the Branch at `0x0041360C` is Taken?**
If `bnezl v0, pos_00413780` **branches immediately** (which happens when `v0 = 1` due to the patch), then:

✔ **Everything in `0x00413610 - 0x00413780` is skipped.**  
✔ **The jump state counter is never updated.**  
✔ **The function at `0x004C33D8` is never called, so physics calculations are bypassed.**  
✔ **Execution jumps straight to `0x00413780`, which is part of the continuous loop.**
