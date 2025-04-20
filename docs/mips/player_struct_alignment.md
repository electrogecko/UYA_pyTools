Below is a “best‐fit” walkthrough of how the assembly‐level offsets (like 0x14B8, 0x14BC, 0x2F0, etc.) probably map into 
Player struct (the one of total size 0x4500), and in particular how they appear to fall within  HeroJump (and nearby) 
sub‐structures. The short version is that **most** of the references do indeed land inside HeroJump block, but there seems
to be extra padding or subtle layout differences that shift some fields compared to preliminary definitions. 
This is very normal when reverse‐engineering large game structs.

**1\. Confirmed Easy One: lw v0, 0x2F0(s1) → Player->timers**

In your Player struct:

/\* 0x02F0 \*/ HeroTimers timers;

So any MIPS instruction like:

lw v0, 0x2F0(s1)

very clearly corresponds to player->timers (some integer/flag in that sub‐struct).

That part lines up perfectly, with no offset mismatch.

**2\. The Block Around 0x14B8 ~ 0x14C4**

References like:

lwc1 f03, 0x14B8(s1) ; float read

lh v1, 0x14BC(s1) ; half‐word read

lwc1 f01, 0x14C0(s1) ; float read/write

lwc1 f03, 0x14C4(s1) ; float read/write

plus some neighbors like lh v1, 0x14BC(s1) repeated, or lh v1, 0x14BC(s1); lh v1, 0x1528(s1); ....

All of these are in the range **0x14B8..0x14C4**. That is well within Player struct (size 0x4500). Numerically:

0x14B8 = 5304 decimal

0x14BC = 5308

0x14C0 = 5312

0x14C4 = 5316

**Where Does That Fall in HeroJump?**

HeroJump guess at Player + 0x1430,  you found a **40‐byte discrepancy** when trying to align “accel” at 0x202F8B50. 
In reality:

- HeroJump must actually start at Player + 0x1470 in memory (not 0x1430).
- Because “accel” ( declared at offset 0xD0 within HeroJump) showing up at 0x202F8B50 = **(base 0x202F7640) + 0x14B10**.

But wait, also have references to 0x14B8 ~ 0x14C4. That is extremely close to 0x14B10–0x14B50. In fact:

- 0x14B8 - 0x1470 = 0x48 into the HeroJump.
- 0x14C0 - 0x1470 = 0x50 into the HeroJump.
- 0x14C4 - 0x1470 = 0x54.

So the fields at offsets \[+0x48..+0x54\] from the start of HeroJump are being used. 
Then you also see code that does **lh v1, 0x14BC** (that’s 0x14BC - 0x1470 = 0x4C from the start of HeroJump), 
except it’s a half‐word load, so it might be pulling a short from the upper half of a float or from a separate
short field adjacent to the float.

All this suggests that inside HeroJump, around offset \[0x40..0x50\], the compiler placed a group
of floats **plus** a short—possibly in some union/padding arrangement. Or it might be that the code 
is reusing the top half of a float for a timer or frames count (this occasionally happens in certain older games).

**A Guess: Snap‐Jump or Partial Thrust Vectors?**

In HeroJump:

/\* 0x40 \*/ VECTOR snapJumpThrustVec; // 4 floats

/\* 0x50 \*/ VECTOR snapJumpForwardVec;

...

If HeroJump truly starts at 0x1470, then offset 0x40 from that is 0x14B0. So:

- snapJumpThrustVec\[0\] is at 0x14B0
- snapJumpThrustVec\[1\] is at 0x14B4
- snapJumpThrustVec\[2\] is at 0x14B8
- snapJumpThrustVec\[3\] is at 0x14BC

But in assembly, you see lwc1 f03, 0x14B8(s1) for a float, and **also** lh v1, 0x14BC(s1) for a half‐word. 
That’s consistent if:

- snapJumpThrustVec\[2\] is read/written as a float at 0x14B8,
- and the _fourth_ float’s location (0x14BC) is partially used as a short.
- Possibly the code is doing lh to read only the upper or lower 16 bits.
- Or the layout might have changed from the guess (the game might store only 3 floats
-  in snapJumpThrustVec, and the “4th float” is actually a short + 2 bytes of pad, etc.).

So that would neatly explain the repeated combination of 0x14B8 (float) and 0x14BC (short).

**Then 0x14C0, 0x14C4?**

Next, offset 0x50 from HeroJump start is 0x14C0. In the layout, that’s the first float of snapJumpForwardVec. 
Then 0x14C4 is the second float, etc. That lines up with the code that does:

lwc1 f01, 0x14C0(s1)

lwc1 f03, 0x14C4(s1)

and uses them as floats. The assembly later writes back to 0x14C0 (and never touches 0x14C4 except reading).
That could be something like “update the forward vector’s X component,” while the Y or Z stays the same. 
Or maybe it’s just partial usage.

So everything around 0x14B8..0x14C4 is almost certainly somewhere in the “snap jump” or “takeoff thrust” area of the HeroJump struct. 
The only mismatch from  typed definitions is that the compiler (or devs) may have introduced an extra short/union for \[+0x4C\], 
or they are storing a short in the last half of one of those floats. That can happen if the dev used a union or re‐purposed some pieces of the vector to store frame counts.

**3\. The Other Offsets: 0x1518, 0x151C, 0x1528, 0x1530, etc.**

There exists code referencing:

- lwc1 f02, 0x151C(s1)
- lh v1, 0x1528(s1)
- lwc1 f02, 0x1530(s1)

All of these are in the range ~0x1518..0x1530, i.e. about +0x60 to +0xC0 after 0x14B8..0x14C4.

If HeroJump starts at 0x1470 and is 0x100 in size, it extends up to 0x1570.
So offsets in the 0x1518..0x1530 range are still _inside_ that same HeroJump. They could be referencing fields like:

- /\* 0x60 \*/ float camHeight;
- /\* 0x64 \*/ float turnSpeed;
- /\* 0x68 \*/ float wallJumpXySpeed;
- /\* 0x70 \*/ float maxFallSpeed;
- /\* 0x74 \*/ float maxXySpeed;
- /\* 0x78 \*/ float ideal_height;
- ...
- up to the bottom of the struct at 0x1570.

Which exact fields correspond to 0x1518, 0x151C, 0x1528, etc., depends on how the compiler placed them
—and on any union or extra short fields the devs used. 
You would check the instructions carefully: are they lwc1 vs. lh vs. lw? 
A lh means it’s definitely a 16‐bit field. A lwc1 is a 32‐bit float. 
That helps you guess which part of your C struct lines up.

Given that one sees both lwc1 and lh in that range, you can infer certain spots are floats,
others are shorts—possibly for timers or counters.

**4\. The “Moon Jump Gravity” at 0x249C is Already Perfect**

0x249C(s1) lines up exactly with moonJumpGravity in  Player struct:

/\* 0x249c \*/ float moonJumpGravity;

and in memory at 0x202F9ADC. That had no offset mismatch, which confirms that from around 0x1Axx onward, the struct layout is probably correct. 
The difference in the 0x13xx–0x15xx region is simply that the real code has about +0x40 more bytes than the initial guess.

**5\. Summarizing How to “Line It All Up”**

1. **s1 = 0x202F7640** is the base of  Player struct in RAM.
2. Instructions referencing lh/lw/lwc1 at offsets like 0x14B8, 0x14C0, 0x1528, 0x1530, they are almost certainly inside the HeroJump sub‐struct (which really starts at Player + 0x1470).
4. The exact sub‐fields being used do not match your preliminary names 1:1, because it looks like the developers used (or the compiler inserted) some half‐word fields or union overlays. That leads to the interesting pattern: “float at offset +0x14B8, half‐word at offset +0x14BC, float at offset +0x14C0,” etc.
5. **lw v0, 0x2F0(s1)** lines up directly with Player->timers at 0x02F0. No mystery there.
6. “moonJumpGravity” at 0x249C lines up perfectly as well, confirming that from ~0x1A00 and up, the struct is correct.

So yes, the assembly  (lh v1, 0x14BC(s1), lwc1 f03, 0x14B8(s1), etc.) is indeed referencing Player struct (the same one at 0x202F7640). The only tricky part is that the region around 0x13E0–0x1430 in your definitions is missing about +0x40 bytes of real data/padding, which shifts “HeroJump” to start at 0x1470. Once you account for that shift (and the possibility of a short stuffed among those floats), the code references make sense as pieces of the jump/thrust logic.
