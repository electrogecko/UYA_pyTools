JumpPadFunction_004F50xx 
 ├─> NameGuess_004F8D58  (if f12 > 0)
 └─> [various local branches / labels in the same function]

LargeRoutine_004FE888
 ├─> pos_004F89A8, pos_004F8668, pos_004F8C58, pos_004F8928, etc.
 └─> [Eventually calls] NameGuess_004F8D58 (with f12 = -0.35)
     pos_004F8D58 is also reached in other states if [a0+0x1A06]==0

LargeRoutine_004F74CC
 ├─> Subcalls like pos_004F8A48
 ├─> pos_004F75E8
 └─> pos_004F7894 (return)

LargeRoutine_004F8F30
 ├─> pos_004F8F9C, pos_004F8FCC, etc. 
 ├─> pos_00453060, pos_00453250
 └─> final vector math

**1\. Overview Table**

| **Address / Label** | **Snippet or Block** | **Calls / Branches To** | **Brief Explanation** |
| --- | --- | --- | --- |
| **0x004F50xx** | _Jump Pad Calculation Block_ (initial snippet) | \- pos_004F8D58 (if f12 > 0.0) | The primary “jump pad” or “thrust” calculation routine. Checks various floats/shorts around offsets 0x14B8..0x14C4, 0x1518..1530. Also checks \[0x2F0\] (timers) and \[0x14AD\] (byte flag). Computes final thrust via sqrt(...), accumulates in \[0x14C0\], sometimes calls NameGuess_004F8D58. Has branches named pos_004F5118, pos_004F5150, etc. |
| **pos_004F5118** | Inside the Jump Pad code | Jumps to pos_004F5150 in some conditions | Subsection that does a partial thrust calculation: doubles a float, multiplies by \[0x1530\], takes sqrt, subtracts \[0x14C0\] & \[0x14C4\]. Updates \[0x14C0\]. |
| **pos_004F5150** | Inside the Jump Pad code | Falls through to snippet checking f12 > 0 | Another label that checks if f12 > 0, then calls pos_004F8D58, and resets \[0x14C0\] to 0.0 while adding its old value to \[0x14C4\]. Also checks \[0x14AD\]. |
| **pos_004F519C** | Inside the Jump Pad code | Goes to pos_004F530C if \[s1 + 0x14AD\]=0 | A small “flag check” section. If the byte at 0x14AD is zero, it branches away to pos_004F530C. This code is partial and was not fully mapped out. |
| **0x004F74CC** | Large function referencing \[s0 + 0x1A06\], etc. | Branches to pos_004F75E8, pos_004F7894 | Checks various states/flags in the player struct (\[0x1A06\], \[0x2DE\], \[0x2AC\]). If \[1A06\] != 0, it skips. Possibly applies movement logic or calls other subroutines. |
| **pos_004F75E8** | Sub‐label in the 0x004F74CC region | Possibly calls pos_004F89A8 | Code that sets or clears \[0x2D4(s0)\], checks a float at \[0x2AC(s0)\]. Calls pos_004F8A48 or branches out. Contains additional sub‐logic for movement or states. |
| **0x004F8D58** | _NameGuess_004F8D58 Helper_ | Returns to the caller if \[a0+0x1A06\]!=0 | A small helper function. Copies 16 bytes from (a2) to (a1) if \[a0 + 0x1A06\]==0, then adds f12 to the float at offset +8 of (a1). Called by the jump pad code with f12=some positive or negative. |
| **pos_004F8DD8** | Return sequence for 0x004F8D58 | —   | The tail end of that helper. Just a stack cleanup and jr ra. |
| **0x004F8F30** | Another large function referencing \[a0+0x1A06\] | Branch logic to pos_004F8F9C, pos_004F8FCC, pos_004F9008 | Checks if \[a0+0x1A06\] == 1, does different copying or calls to movement code. Uses vector instructions (lq, sq, lqc2, sqc2). Possibly an extended movement/transform routine. |
| **pos_004F8F9C** | Sub‐label in 0x004F8F30 | Calls pos_00453250, pos_00453060, etc. | If \[a0+0x1A06\]==1, it triggers multiple sub‐calls that update camera or movement data, then branches to final logic. |
| **pos_004F8FCC** | Sub‐label in 0x004F8F30 | Calls pos_00453060 | Another path for state=2, calls a function with f12=f00. Then a VU operation for a position difference. |
| **0x004FE888** | Large routine referencing \[a0+0xFB0\], \[0x19E6\], \[0x19E4\] etc. | Calls pos_004F89A8, pos_00452FF8, pos_004F8668, pos_004F8928, and eventually pos_004F8D58 | Very big “update loop” for the player struct. Checks flags like \[0x19E4\]/0x19E6, sets \[a0+0xFB0\] = 0. Possibly a main “per‐frame” logic function. Eventually calls the small helper pos_004F8D58 with negative or positive float. |
| **pos_004FEA4C** | Sub‐label in 0x004FE888 region | Jumps to pos_004FEAA4 or calls pos_004F89A8, pos_004F8668, pos_004F8C58 | Possibly does advanced checks on f20, f21 floats, triggers some camera or collision checks. Then sets up for the next step. |
| **pos_004FEAA4** | Sub‐label in 0x004FE888 region | Calls pos_004F8928 and eventually pos_004F8D58 | Another step in the update pipeline: does vector addition with vf01, vf02, loads \[s0+0x2530\] or \[sp\]. Typical movement math, then calls the “copy+add” function. |
| **pos_004FEAF0** | Sub‐label from 0x004FE888 block | Calls pos_004F8D58 with f12=0xBEB33333 | The well‐noted negative float (-0.35). After the call, more logic about \[0x2524(s0)\] or references to 0x0026XXXX. Possibly final friction or damping in the same frame. |
| **pos_004FEB7C** | The final return inside 0x004FE888 | Restores registers, does jr ra | The cleanup & exit for that giant routine. |
