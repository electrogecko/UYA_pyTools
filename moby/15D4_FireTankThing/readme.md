# Update Function (Level 24)

Function address: 0x0034F640 in level24 code.0006

---

## 7-State State Machine

| State | Behavior |
|------|----------|
| 0 | Initialization |
| 1 | Idle / interpolation — smoothly scales toward target |
| 2 | Active / proximity — countdown timer, checks for teleport pad (class 0x0F51), distance check to player, waits for triangle button press |
| 3 | Activated — sets timer, spawns effects, transitions |
| 4 | Animating — timer counting up, playing animation |
| 5 | Winding down — timer counting down |
| 6 | Cleanup — particle effects, calls teardown helpers |

---


## Code Extent

| Metric                         | Value                         |
|--------------------------------|-------------------------------|
| Local functions (full closure) | 21 functions                  |
| Total local code               | ~9,600 bytes (0x2580)         |
| Engine dependencies            | 64 unique functions           |
| Engine matches found in lvl41  | 31 / 64 (48%)                 |
| Code range                     | 0x0034D870 — 0x003504C0       |

| Metric                     | Value                                      |
|---------------------------|--------------------------------------------|
| Local code size           | ~9,600 bytes                               |
| Internal relocations      | Many dozens                                |
| Engine dependencies       | 64 functions                               |
| Engine matches (level41)  | 31 / 64 (48%)                              |
| SP-specific globals       | Multiple (hero struct, gameplay globals)   |
| SP-only class references  | Checks for class 0x0F51 (SP teleport pad)  |

---
