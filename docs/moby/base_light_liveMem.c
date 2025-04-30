// Live memory instance (blue base, Korg level 43, NTSC) 
struct BaseLightPVar_korgBlueActive
{
    /* 0x000 */ uint32_t flags_or_unused0;       //       Unknwon 0s 
    /* 0x004 */ float polarityOrOffsetA;         //       Unknown ~3.07f
    /* 0x008 */ float decayOrOffsetB;            //       Unknown ~0.93f
    /* 0x00C */ uint32_t unk;                    //       unk (May trace to base entry) 
    /* 0x010 */ uint32_t reserved10;             //       Unknown
    /* 0x014 */ uint32_t reserved14;             //       Unknown
    /* 0x018 */ float dynamic18;                 //       Possibly relating to light effect (usually 0.X–3.X) 
    /* 0x01C */ uint32_t lightStyle;             // in packed pvar, its Usually 0x38 or 0x3A, in live mem, its 0 = default; 1 = red; 2–7 = white; 8–F = bright; 10–11 = brown

    /* 0x020 */ uint32_t sentinel1;              //       Usually 0xFFFFFFFF
    /* 0x024 */ uint32_t reserved24;             //       Unknown
    /* 0x028 */ uint32_t unk;                    //       Set to 1
    /* 0x02C */ uint32_t TeleControllerID;       //       Possibly sets ownership of teleport ID in korg, 56 or 58. No apparent effect on change in live memory

    /* 0x030 */ uint32_t unk;                    //         Unknown Sentinel 
    /* 0x034 */ uint32_t unk;                    //         Unknown zeros
    /* 0x038 */ uint32_t spawnCuboidID;          // Appears to be team's spawn cuboid ID (In korg 35, for blue, 0 for red, no effect on change in live memory) 
    /* 0x03C */ uint32_t sentinel2;              // Sentinel 0xFFFFFFFF

    /* 0x040 */ uint32_t baseOpenFlag;           // [confirmed] 1 = base open (post-gattling phase). Forced to 1 with no gatts. 
    /* 0x044 */ uint32_t unknown044;             // 

    /* 0x068 */ uint32_t damageCountdown;        // [Confirmed] sentinel initially. Sets to pointer (e.g. ID 0x0070CB64 ) when base computer is destroyed 

    /* 0x0B0 */ uint32_t baseDefensesGroupRef;   // [Confirmed] Group ID (in korg, 09 for Blue team, 11 for Red team ) 
    /* 0x0B4 */ uint32_t baseComputerIdx;        // [Confirmed] Moby ID of Base Computer (in korg, BA for blue team  ) 
    /* 0x0B8 */ unk32    unk;                    // Always 0, but if 1st byte cleared after being set, increment 2nd byte of 0xBC timer 
    /* 0x0BC */ uint16 unkTimer;                 // Inactive always. Increments if active. Resets after 0xFF19 To activate, change 0xB0 
    /* 0x0BE */ unk16 unk;                       // Affects 0xBC timer in multiple ways
    /* 0x0B8 */ unk
    /* 0x0BC */ unk
    /* 0x0C0 */ uint32_t damageCountdown;        // [Confirmed] Starts at gat hit; resets if both destroyed

    /* 0x0C4–0x0EC */ uint8_t reservedD4[0x1C];  // Unused or padding
    /* 0x0F0 */ uint32_t takeoverTimer;          // Appears ~1s after loading enemy base


    /* 0x17C */ uint32_t countUpTimer;           // Increments after 0x180 + 0x1BC triggered
    /* 0x180 */ uint32_t triggerSeed;            // Required for triggering 0x1BC timer
    /* 0x1BC */ uint32_t countTriggerLatch;      // If seed set, this starts 0x17C ticking
};
