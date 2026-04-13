Full State-134 Launch Chain

```
Player stands on moby 0x09B9 or 0x0F05
  |
  v
0x4E2DF4: player->ground.pMoby->oClass check
  |
  v
Player enters state 134 (launch-prep)
  |
  v
0x4E31E8: State 134 init seeds parameters into hero singleton
  height, target, steps=17, gravity, etc.
  |
  v
0x4E430C: State 134 -> 0x4F0988(7, 0, 5.0)
  Hands off to state 7 (JUMP) with 5-frame transition
  |
  v
Per-frame: 0x4D2650 hero update loop
  |
  v
0x4D2A24: Arc updater computes delta = sqrt(2*h*g) - accumulated
  h ramps from start to target over 17 frames
  |
  v
0x4F2098: Adds delta to hero singleton displacement vector Z (+0xF8)
  |
  v
Hero pipeline finalizer: decomposes displacement into Player HeroMove
  behavior, actual, ascent, zSpeed
  |
  v
Player position updated from HeroMove.actual
