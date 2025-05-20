# Psudocode
## Vehicle 
 - Constants/PVAR table partilaly decoded 
 - Use SP-florana Vehicle (mostly working) 
  - BUGS: 
    - Animation crash when switching to passenger
    - Preferably disable animation (other use button for button) 
 - posssibly look into adjusting vehicle size 
   
## Map
- Barlow
- Level_44 base map, no water, has vehicle support. 
- Map filesize can contain ~70-80% ties. Must do away with:
  - Decoration
  - Far Mountains
  - Hidden ties
  - Possibly (hopefully not) any interact-able ties
  - Avoiding shrub FOR NOW

## Patch
- Scope is likely large and may require seperate server instance (due to patch size) 
- HUD control for game-mode
  - Ability Charge Bar (Hook into base_light_Thing PVAR at offset 0xTBD to control damage remain
    - Siege Base Health Blue -> Some permenant rechargable ability
      - (ex.) Extra speed boost, use it to go faaster, but drains charge. Non usage allows recharge
  - Item Charge Bar
    - Siege Base Health Red -> Primary item charge remaining
  - Lap Count
    - (ex.) Ammo HUD -> (M/N) -> current_lap / remaianing_laps;
    - (ex.) CTF Scoreboard -> current_lap / remaianing_laps;
- Hook button-down and map to actions:
  - (examaple) Map button [] to primary item usaage
    - if player->possess_item()  // switch-cases for each items?
      - (ex.) if custom->charge > 0: activate ability
      - (ex.) item usage indicator drops to empty on per frame basis
      - (ex.) if custom->charge < 0: drop item
- Hook inventory:
  - If has_changed(player->getitems())
    - HUD-> assign item (overwrite prior item)
    - HUD-> set(charge-bar-red, 100%)
  - If custom->player_is_using_ability()
    - decrement_charage_bar(red,rate)
   - else 
      - increment_charage_bar(red,rate)
  - If player->pick_up_ammo()
    - Turn on power_up_X_subroutine
  - Power_Up_X_Subroutine()
    - Set timer if not set
    - Decrement custom.timer_X
    - Override constant
    - Disable override and turn off subroutine and un_set_timer if less_or_equal(custom.timer_x,0)
- Lap_Tracker
  - (TBD) Communicate with server on game-end / winner .
  - (TBD) Communicate with server on lap-leader or final-lap-notify
    
## Lap Tracking  (to be expanded) 
- Use Horizon-Tracker to track player positions
 - Player lap count (1/N); 
 - Project to 2-d, set linear-intercept 'checkpoints' (e.g. 4 per map).
 - Player must pass all checkpoints to be awarded a 'lap'
 - If Tracker.Player[X].num_laps_passed >= N; Tracker.Player[X].wins();
   - Send-event-to-patch
     
## Items:
- Inspired by "Patch" from City Trial: (see https://kirby.fandom.com/wiki/Patch)
- Re-skin crates to item-up type.
  - Mini-Rocket -> reskin-> some_graphic.jpg
    - (ex.) Accelerate faster
  - Flux-Rifle -> reskin-> some_graphic.jpg
    - (ex.) Obtain max speed boost
  - Gravity-Bomb -> reskin -> some_graphic.jpg
    - (ex.) Override gravity constant when active
      
## Power-Ups
- Inspired by "Quick Fix" from City trial (see https://kirby.fandom.com/wiki/Patch)
  - Re-skin Ammo Pickups
  - (ex) N60-ammo -> GC-barlow-pyramid-booster
    - Boost player automatically for short period of time 

