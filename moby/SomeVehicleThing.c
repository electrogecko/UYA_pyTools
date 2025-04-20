// BAKISI NTSC, captured at game load (black screen) 
// Hypothetical struct at candidate memory: 0x219EA3D0

// Initial bytes (positional floats)
float fPosX = 342.27f;     // E4 A3 AA 43
float fPosY = 307.98f;     // B7 BF 98 43
float fPosZ = 202.14f;     // 4E 9B 48 43
float fW   = 0.0f;         // 00 00 00 00

// Seat / camera / icon / logic flagging?
uint32_t seatFlags = 0x800DFF00;   // 00 FF 0D 80 (byte reversed)

// Pointer? (maybe to vehicle type/asset)
uint32_t unk1 = 0x013215E0;        // E0 15 32 01
uint32_t unk2 = 0x01529EC0;        // C0 A4 9E 01

// Pattern: 55 55 55 3E
uint32_t behaviorFlags = 0x3E555555;  // Little endian

// RGBA color or light state?
uint32_t colorMask = 0x01FF00FF;    // FF 00 FF 01

// Packed booleans or status fields?
uint32_t flagCombo1 = 0x80743030;   // 30 54 80 7F (guessing 0x80743030 masked?)

// Padding or timers?
uint32_t zero1 = 0x00000000;
uint32_t field1 = 0x002C3030;       // 30 30 2C 00 // This is def a pointer...
uint32_t field2 = 0x00000100;

// --- Fields below were observed to change camera behavior ---
float fZoomOrFOV1 = 1.0f;           // 00 00 80 3F
float fZoomOrFOV2 = 0.5f;           // 00 00 00 3F

// Movement / damping flags?
uint32_t field3 = 0x00000000;
uint32_t field4 = 0x00000000;

// Likely pointers (runtime adjusted)
uint32_t vptr1 = 0x01321B90;
uint32_t vptr2 = 0x01321D20;

// Boolean or index
uint32_t seatIndexOrState = 0x01201520;

// Vehicle mode data (speed, gravity, orientation?)
float controlParam1 = 0.147f;      // E8 10 3E 00
uint32_t color32 = 0x01A2FB60;

// Respawn or death flag area
uint32_t healthOrRespawn = 0x0018FFFF;  // FF FF 00 18

// New findings
uint32_t padding1 = 0x00000000;
uint32_t padding2 = 0x00000000;
uint32_t vecColor = 0x80787878;
uint32_t zeroBlock = 0x00000000;
float fGravityY = -1000.0f;         // C4B947F0
float fAccelX = 1261.84f;          // 459D6F28
float fAccelZ = 4245.35f;          // 468435F6

uint32_t zeros2[2] = { 0x00000000, 0x00000000 };
uint32_t pointerToMatrix = 0x013271E0;
uint32_t moreZeros[3] = { 0x00000000, 0x00000000, 0x00000000 };

// Joystick deadzones or camera bounds?
uint16_t deadzone1 = 0x141D;
uint16_t deadzone2 = 0x141D;
uint32_t unknownByteSet = 0x107C00FF;

uint16_t maybeSeatState = 0x0001;
uint16_t maybeInputCode = 0x000F;

uint32_t speedVecColor = 0x009A80FF;

// Following this may be the normalized direction vectors, float triplets
// Likely more vector data or camera target info follows
float camDir1X = 0.975f;           // 59 19 79 3F
float camDir1Y = 0.232f;           // D8 6C 6D 3E
float camDir1Z = 0.0f;
float unused1 = 0.0f;

float camDir2X = -0.232f;          // D8 6C 6D BE
float camDir2Y = 0.975f;           // 59 19 79 3F
float camDir2Z = 0.0f;
float unused2 = 0.0f;
 //! we are probably off the rails around here
float unused3 = 0.0f;
float unused4 = 0.0f;
float unused5 = 1.0f;              // 00 00 80 3F
float unused6 = 0.0f;


/////////////////////////////////////////////

// --- Start of vptr1 block ---
float blendWeight1 = 0.5f;          // 00 00 00 3F
uint32_t packedType1 = 0x00180000;
uint32_t timingLogic1 = 0x00010070;
uint32_t gateInfo1 = 0x00000178;

uint64_t unknownZeroPtr1 = 0x0000000000000000;
float vectorClamp1[8] = {            // Series of 0xFF7F000000000000
    NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN
};

uint32_t table1[3] = { 0xA5AB05A6, 0x5A55A605, 0x00483D96 };
uint32_t zeroPack1 = 0x00000000;
uint32_t negBound1 = 0x80000000;
uint32_t pad1 = 0x00000000;

uint32_t table2[3] = { 0xA5AB05A6, 0x5A55A605, 0x00483D96 };
uint64_t unknownClear1 = 0x0000000000000000;
float boundsVecs1[3] = { NAN, NAN, NAN };

// --- Start of vptr2 block ---
float blendWeight2 = 0.5f;          // 00 00 00 3F
uint32_t packedType2 = 0x00180010;
uint32_t timingLogic2 = 0x00010070;
uint32_t gateInfo2 = 0x00000178;

uint64_t unknownZeroPtr2 = 0x0000000000000000;
float vectorClamp2[8] = {
    NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN
};

uint32_t table3[3] = { 0xA5AB05A6, 0x5A55A605, 0x00483D96 };
uint32_t negBound2 = 0x80000000;
uint32_t pad2 = 0x00000000;

uint32_t table4[3] = { 0xA5AB05A6, 0x5A55A605, 0x00483D96 };
uint64_t unknownClear2 = 0x0000000000000000;
float boundsVecs2[3] = { NAN, NAN, NAN };

float unknownNegZ = -11726.92f;    // C1 9D 6D 80
float paddingF = 0.0f;

///// This is an intuitive 'guess' at the unknown pointers. Could be entirely wrong. 
// --- Start of unk1 block ---
uint32_t unk1_a = 0x01326B40;
uint32_t unk1_b = 0x32011121;
uint32_t unk1_c = 0x0028282E;
uint32_t unk1_d = 0x0B011E20;
uint32_t unk1_e = 0x013271E0;
uint32_t unk1_f = 0x01327560;
uint32_t unk1_g = 0x013280E0;
uint32_t unk1_h = 0x013283C0;
uint32_t unk1_i = 0x01356CA0;
float unk1_j = 0.333f;             // 55 55 55 3E  //This is interesting, it matches normalized max turbo speed
uint32_t unk1_k = 0x01328570;
uint32_t unk1_l = 0x00143206;
float gravityCheck = -1000.0f;     // in Korg, there is a -4000.0f near veh constants possibly related to turn accel
uint32_t zeroA = 0x00000000;
float accelXCheck = 1261.84f;
float accelZCheck = 4245.35f;
uint32_t unk1_pad0 = 0x80787878;
uint32_t unk1_unknown1 = 0x00054020;
uint32_t unk1_ptrMatrix = 0x01321AA0;
uint32_t unk1_null[6] = {0};

// --- Start of unk2 block ---
uint32_t guidHeader = 0x1BA20713;
uint32_t controllerHash1 = 0x7B9BEEF1;
uint32_t controllerHash2 = 0x025DDE9B;
uint32_t blendHash = 0x7929E7DE;
float logicWeight = 0.975f;
uint32_t pathBits = 0x07F36D00;
uint32_t pathHash = 0x3BE070B6;
uint32_t routePointer = 0x0113EA4F;
uint32_t routeFlags = 0x0FDC0FFF;
uint32_t gateParam = 0x00107980;
uint32_t logicGate1 = 0x00100000;
uint32_t logicGate2 = 0x800C1000;
uint32_t logicGate3 = 0x00100000;
uint32_t logicGate4 = 0x800D098E;
uint32_t logicGate5 = 0x00100000;
uint32_t logicGate6 = 0x800F09C9;

uint32_t routeInfo1 = 0x01560000;
uint32_t encounterId = 0x00010A4B;
