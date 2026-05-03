Level 44 NTSSC

For now, we hijack the (inactive registry of the) Snowman Skin (16DB oClass) which has Primary 0. 
This allows us a free-running update for continuous visuals. 
Why not our own? Perhaps a new class can be thrown into the registry rows, but I am afraid of growing the size and moving targets. 
| Data |
|------|
| `0x3BB100  registry rows`<br>`...`<br>`0x3BB76C  sentinel row: FFFFFFFF 00000000 003BB778`<br>`0x3BB778  secondary descriptor blobs start here` |

We then intercep the stock jumppad 10C4 stock and hook with our comparaator. 
Our hook decides which jump pad type to use. 

The 9B9 jump pad has been mostly gutted.
Importing its donor routines are a mess and not worth getting right, but we have some looes about each of its routines and patterns that very strongly resemble the FX emissions. 
Instead, we immediatley force fall state 6 and drive a vertical impulse. This can be buffed by ranging the gravity constant, which will gracefully and naturally reset on state change. 

Code6 is where our custom logic and colorshade lives, so we need to increase the size

  | File          | Address / Region        | Edit                                                                 | Purpose                                                                 |
|---------------|------------------------|----------------------------------------------------------------------|-------------------------------------------------------------------------|
| code.0003.bin | 0x003BB430             | Reused empty 16DB registry slot as class 09B9, primary 0x0053FA70, secondary 0x003BBAD8 | Registers our custom 09B9 moby runtime without touching native 10C4     |
| code.0003.bin | 0x003BBAD8             | Copied stock 10C4 secondary descriptor over unsafe 16DB descriptor   | Gives 09B9 safe descriptor callbacks; avoids 16DB skin/blob behavior    |
| code.0006.bin | appended 0x0053FA70    | custom_main per-frame moby callback                                  | Seeds render flags/state, writes dark pulse color to moby+0x78, updates pvar+0x04 |
| code.0006.bin | 0x00515A20             | Replaced stock compare branch with `j 0x00540270`                    | Intercepts jump-pad class detection for player launch                   |
| code.0006.bin | 0x00515A24             | NOPed old branch-likely delay slot                                   | Fixes native 10C4 path by preventing v0 clobber before hook logic       |
| code.0006.bin | appended 0x00540270    | launch_hook                                                          | If touched moby is 09B9: plays sound, sets player to fall, applies launch; if 10C4: routes to native handler |
| code.0006.bin | appended 0x0054032C    | velocity_wrapper                                                     | Reads live pvar launch params and writes player launch/fall physics fields |
| code.0006.bin | appended 0x005403C4    | visual_helper                                                        | Drives pulse loop using `(game_time >> 6) & 0xF`, writes darker greyscale color table |
| code.0006.def | size 0x183670 → 0x1840CC | Updated code segment size                                            | Makes appended custom code/data part of loaded code blob                |
