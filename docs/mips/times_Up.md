# Global Game-End Function (NTSC) — Disassembly Notes

## Entry Point

The function stepped out into after the Time-Up/UI callback chain is the **global game-end controller**. Based on trace, the entry point is:

```
0x00454BC4
```

This address is consistently reached after KOTH "Time Up!" → UI callback → callback dispatcher.

## High-Level Purpose

This routine:

* Performs end-of-round/game teardown.
* Clears multiple state globals.
* Dispatches mode-specific and global end callbacks.
* Triggers sound, HUD cleanup, summary screens, scoreboards.
* Calls the callback dispatcher where your Time-Up text function resides.

## Early Structure Summary

```
00454BC4:
  jal   00463848(0)          # conditional early cleanup
  jal   004523B0
  jal   00476148
  jal   004533D8
  jal   00453D58
  sw    -1, (0x0025:-0x7E28)
  sw     0, (0x0024:5D30)
  sw     0, (gp-0x240C)
```

## Flag-Based Branching

The function checks many bits of `0x0025:-0x7FBC`:

* **0x0001 / 0x0002 / 0x0004 / 0x0008 / 0x0010 / 0x0020 / 0x0040 / 0x0080 / 0x0180**
* Each bit gates calls such as:

  * `004C4698`
  * `004CD8A0(0201/0202/0204/0208)`
  * `004C61A8`, `004CD308`, `004553E0`, `00456018/90`, `00455510`
  * `00456F20`, `00457000`, `00494CF0`, `00473B00`

These handle:

* HUD teardown
* Voice/chat cleanup
* Mode-specific finishing logic
* Postgame UI
* Alpha/animation effects

## Callback Dispatcher

Later, the function calls:

```
jal 00456298
```

That call enters the callback dispatcher traced earlier, which invokes **Time-Up text builder**.

## Late-Stage Work (Updated)

Includes:

* Scoreboard voting flow
* Player-slot dependent HUD effects via `s1 * 0x460` index
* Float-driven alpha transitions
* End-of-game sound events
* Final cleanup before transitioning to results/menus

## Current Status

You have provided the correct entry point (`0x00454BC4`).

## Additional Disassembly Block: 0x00455144–0x00455290

This block performs late-stage event dispatch and feature-specific teardown:

* Begins with a conditional branch into `00456DA0` depending on bit tests.
* Performs a UI/asset cleanup call via `004CCBA0(a0+0xAE0)`, followed by `001264E0`.
* Reads a signed engine counter at `0x1000:0800`, converts it to float, normalizes it by either `f00 = 9500.0` (`0x4616`) or `11328.0` (`0x4634`), depending on a status flag at `0x001A:5990`.
* Stores the normalized float to `0x0025:-0x7E34`.
* Repeated calls to `004CCF20(a0 = 2, 4, 8, 16)` signal internal state transitions.
* **Bit 0x0002:** triggers `004C5728` and `004C45F8`.
* **Bit 0x0004:** copies three quadwords from `0x0026:-0x63E0` to `0x003C:0xFE0`, then calls `004C9F88` and `004C60E8`.
* **Bit 0x0008:** runs `004BFB98` and `004BDEA8`.
* **Bit 0x0010:** runs `00476468`.
* Final teardown uses `00452680(s1)` before clearing `0x0025:-0x7DF0` and returning.
