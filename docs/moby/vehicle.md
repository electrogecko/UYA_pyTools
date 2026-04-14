The MP vehicle system works through a VehicleInterface struct with function pointers:
| Callback                   | Purpose                   |
|----------------------------|---------------------------|
| GetVehicleBase             | Returns Vehicle* pointer  |
| SetAsUnspawned             | Handle despawn            |
| ReinitPhysics              | Reset physics state       |
| UpdatePhysics              | Per-frame physics         |
| DamageReact                | Handle damage             |
| UpdateLocalDriverAttack    | Handle driver weapons     |
| UpdatePassenger            | Handle passengers         |

Hoven Level41 NTSC: 
  The turboslider registers these via 0x0053A568, then calls 0x00538890 (guber event create) which allocates a Vehicle
  struct (~832 bytes) with driver/passenger pointers, HP, guber sync, etc. The framework then handles
  enter/exit/camera/HUD/network automatically — PLAYER_STATE_VEHICLE = 49 (0x31).
