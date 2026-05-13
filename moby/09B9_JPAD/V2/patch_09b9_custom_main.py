#!/usr/bin/env python3
"""
Custom-main pivot for the level44 0x09B9 jump pad.

No donor (level24) code is imported. We register our OWN tiny per-frame
update routine ("custom_main") as the 09B9 primary. Behavior we care
about lives entirely in functions we wrote:

    custom_main          per-frame update; calls visual_update_helper
    launch_hook          intercepts level44 stock compare site for 09B9
    velocity_wrapper     applies launch velocity from pvar
    visual_update_helper writes pulse color to moby+0x78, intensity to pvar+0x04

The engine dispatches class methods as `primary + fixed_offset` (e.g.
+0x3A4). custom_main is padded with `jr $ra; nop` stubs to absorb every
such offset within stock 10C4's primary footprint, so the engine sees a
"do nothing" handler at every method offset other than the one we
implement at +0.

Registry slot setup mirrors the working --registry-blob-10c4 mode:
hijack a 16DB slot, copy stock 10C4's secondary blob into it, set
class=09B9 and primary=custom_main_vma.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants

CLASS_10C4 = 0x10C4
CLASS_09B9 = 0x09B9
REGISTRY_REUSE_CLASS = 0x16DB

# Player struct offsets
PLAYER_VTABLE_OFF       = 0x0014
MOVE_BEHAVIOR_Z_OFF     = 0x0128
MOVE_ACTUAL_Z_OFF       = 0x0148
MOVE_ASCENT_OFF         = 0x01AC
MOVE_ZSPEED_OFF         = 0x01B0
GROUND_PMOBY_OFF        = 0x02CC
GROUND_ONGOOD_OFF       = 0x02D0
VTABLE_SET_STATE_OFF    = 0x0034
PLAYER_WIND_OFF         = 0x15A0
PLAYER_WIND_VEL_X_OFF   = PLAYER_WIND_OFF + 0x00
PLAYER_WIND_VEL_Y_OFF   = PLAYER_WIND_OFF + 0x04
PLAYER_WIND_SPEED_OFF   = PLAYER_WIND_OFF + 0x10
PLAYER_FALL_OFF         = 0x15C0
PLAYER_FALL_GRAVITY_OFF = PLAYER_FALL_OFF + 0x00

STATE_FALL      = 6
STATE_MOON_JUMP = 131

# Moby struct offsets
MOBY_PVAR_OFF = 0x68

# Pvar layout
PVAR_UP_VELOCITY_OFF    = 0x08
PVAR_FORWARD_BOOST_OFF  = 0x0C
PVAR_SIZE               = 0x40
PVAR_GLOB               = "gameplay/moby/*_02489_09B9/pvar.bin"

# Tunables (overridable via CLI)
DEFAULT_FALL_GRAVITY_SCALE = 1.0
DEFAULT_UP_VELOCITY        = 10.0
LAUNCH_VELOCITY            = 10.0
TEST_HORIZONTAL_SCALE      = 10.0
LAUNCH_VELOCITY_BITS       = struct.unpack("<I", struct.pack("<f", LAUNCH_VELOCITY))[0]
TEST_HORIZONTAL_SCALE_BITS = struct.unpack("<I", struct.pack("<f", TEST_HORIZONTAL_SCALE))[0]

# Level44 stock entry points
SOUND_PLAY_ADDR = 0x004B7608
SOUND_MOBY_PLAY_ADDR = 0x004B78B0
GAME_TIME_ADDR  = 0x001A5F78

# Sound def
SOUND_VOLUME         = 0x400
SOUND_DEF_MIN_RANGE  = 0.0
SOUND_DEF_MAX_RANGE  = 45.0
SOUND_DEF_MIN_VOLUME = 0
SOUND_DEF_MAX_VOLUME = 1228
SOUND_DEF_MIN_PITCH  = -635
SOUND_DEF_MAX_PITCH  = 635
SOUND_DEF_LOOP       = 0
SOUND_DEF_FLAGS      = 0x10
SOUND_DEF_INDEX      = 0x0090
SOUND_DEF_BANK       = 0

# Pulse table
PULSE_SHIFT = 6
PULSE_MASK  = 0x000F
PULSE_VALUES = (
    0.74, 0.76, 0.78, 0.80, 0.84, 0.87, 0.90, 0.93,
    0.96, 0.98, 1.00, 0.90, 0.84, 0.80, 0.76, 0.74,
)
PULSE_COLORS = tuple(
    0x80000000 | (c << 16) | (c << 8) | c
    for c in (
        140, 146, 153, 163, 176, 190, 205, 222,
        238, 250, 255, 220, 195, 174, 156, 140,
    )
)

# Compare-site signature in level44 stock code.0006 (where 09B9 ground
# type would be matched). The launch_hook is patched in here.
COMPARE_SIG_WORDS = (
    0x54620006, 0x922219E4, 0x8E230014,
    0x0220202D, 0x1000002F, 0x24050083,
)

# Custom main pad size: must be at least as large as the largest engine
# method-offset dispatch from primary. Stock 10C4's primary at 0x408958
# extends well past +0x3A4; pad to 0x800 to be safe.
CUSTOM_MAIN_PAD_SIZE = 0x800

# Index inside launch_hook where the velocity-init lui+mtc1 lives, to be
# patched into a `j velocity_wrapper; nop` so velocity comes from pvar.
VELOCITY_PATCH_INDEX            = 32
VELOCITY_PATCH_ADDR_DELTA       = VELOCITY_PATCH_INDEX * 4
VELOCITY_PATCH_OLD_WORD         = 0x3C014120  # lui $1, 0x4120 (10.0f hi)
VELOCITY_PATCH_DELAY_OLD_WORD   = 0x44810000  # mtc1 $1, $f0

# Register aliases
ZERO, AT, V0, V1, A0, A1, A2, A3 = 0, 1, 2, 3, 4, 5, 6, 7
T0, T1 = 8, 9
S0, S1, S4, S5, SP, RA = 16, 17, 20, 21, 29, 31
F0, F2, F4, F6, F12 = 0, 2, 4, 6, 12

# ---------------------------------------------------------------------------
# Tiny encoding helpers

def p32(v: int) -> bytes: return struct.pack("<I", v & 0xFFFFFFFF)
def u32(buf: bytes, off: int) -> int: return struct.unpack_from("<I", buf, off)[0]

def sign16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v

def split_hi_lo(addr: int) -> tuple[int, int]:
    hi = (addr + 0x8000) >> 16
    lo = addr - (hi << 16)
    return hi & 0xFFFF, lo & 0xFFFF

def encode_j(target):       return 0x08000000 | ((target >> 2) & 0x03FFFFFF)
def encode_jal(target):     return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)
def encode_jr(rs):          return ((rs & 0x1F) << 21) | 0x08
def encode_addiu(rt,rs,im): return 0x24000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (im & 0xFFFF)
def encode_lui(rt,im):      return 0x3C000000 | ((rt & 0x1F) << 16) | (im & 0xFFFF)
def encode_lw(rt,rs,im):    return 0x8C000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (im & 0xFFFF)
def encode_lhu(rt,rs,im):   return 0x94000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (im & 0xFFFF)
def encode_lbu(rt,rs,im):   return 0x90000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (im & 0xFFFF)
def encode_sw(rt,rs,im):    return 0xAC000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (im & 0xFFFF)
def encode_sb(rt,rs,im):    return 0xA0000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (im & 0xFFFF)
def encode_sh(rt,rs,im):    return 0xA4000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (im & 0xFFFF)
def encode_swc1(ft,rs,im):  return 0xE4000000 | ((rs & 0x1F) << 21) | ((ft & 0x1F) << 16) | (im & 0xFFFF)
def encode_lwc1(ft,rs,im):  return 0xC4000000 | ((rs & 0x1F) << 21) | ((ft & 0x1F) << 16) | (im & 0xFFFF)
def encode_mtc1(rt,fs):     return 0x44800000 | ((rt & 0x1F) << 16) | ((fs & 0x1F) << 11)
def encode_mul_s(fd,fs,ft): return 0x46000002 | ((ft & 0x1F) << 16) | ((fs & 0x1F) << 11) | ((fd & 0x1F) << 6)
def encode_addu(rd,rs,rt):  return ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | ((rd & 0x1F) << 11) | 0x21
def encode_move(rd,rs):     return ((rs & 0x1F) << 21) | ((rd & 0x1F) << 11) | 0x2D
def encode_andi(rt,rs,im):  return 0x30000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (im & 0xFFFF)
def encode_ori(rt,rs,im):   return 0x34000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (im & 0xFFFF)
def encode_sll(rd,rt,sa):   return ((rt & 0x1F) << 16) | ((rd & 0x1F) << 11) | ((sa & 0x1F) << 6)
def encode_srl(rd,rt,sa):   return 0x00000002 | ((rt & 0x1F) << 16) | ((rd & 0x1F) << 11) | ((sa & 0x1F) << 6)

def encode_beq(rs, rt, pc, target):
    delta = (target - (pc + 4)) >> 2
    if not -0x8000 <= delta <= 0x7FFF:
        raise ValueError(f"branch out of range pc=0x{pc:08X} target=0x{target:08X}")
    return 0x10000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (delta & 0xFFFF)

def encode_bne(rs, rt, pc, target):
    delta = (target - (pc + 4)) >> 2
    if not -0x8000 <= delta <= 0x7FFF:
        raise ValueError(f"branch out of range pc=0x{pc:08X} target=0x{target:08X}")
    return 0x14000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (delta & 0xFFFF)

def stub_pair() -> bytes:
    return p32(encode_jr(RA)) + p32(0)

# ---------------------------------------------------------------------------
# Stock-code search helpers

def find_compare_site(code6: bytes, code6_base: int) -> tuple[int, int, int, int]:
    sig = b"".join(p32(w) for w in COMPARE_SIG_WORDS)
    idx = code6.find(sig)
    if idx < 0:
        raise RuntimeError("failed to locate stock 10C4 compare site")
    compare_addr = code6_base + idx
    match_addr = compare_addr + 0xD0
    no_match_addr = compare_addr + 0x1C
    branch_addr = match_addr + 0x14
    branch_word = u32(code6, branch_addr - code6_base)
    op = (branch_word >> 26) & 0x3F
    rs = (branch_word >> 21) & 0x1F
    rt = (branch_word >> 16) & 0x1F
    if op != 0x04 or rs != 0 or rt != 0:
        raise RuntimeError(f"unexpected branch at 0x{branch_addr:08X}: 0x{branch_word:08X}")
    state_set_return_addr = branch_addr + 4 + (sign16(branch_word & 0xFFFF) << 2)
    return compare_addr, match_addr, no_match_addr, state_set_return_addr

def find_class_slot(code3: bytes, code3_base: int, class_id: int) -> tuple[int, int, int]:
    for off in range(0, len(code3) - 12 + 1, 4):
        klass, primary, secondary = struct.unpack_from("<III", code3, off)
        if klass == class_id:
            return code3_base + off, primary, secondary
    raise RuntimeError(f"failed to find registry slot for 0x{class_id:04X}")

def find_reuse_slot(code3: bytes, code3_base: int) -> tuple[int, int]:
    """Find a 16DB slot with primary=0 and a secondary inside code.0003 to hijack."""
    for off in range(0, len(code3) - 12 + 1, 4):
        klass, primary, secondary = struct.unpack_from("<III", code3, off)
        if (klass == REGISTRY_REUSE_CLASS and primary == 0
                and code3_base <= secondary < code3_base + len(code3)):
            return code3_base + off, secondary
    raise RuntimeError("failed to find reusable 0x16DB registry slot with primary=0")

# ---------------------------------------------------------------------------
# Backups / IO

def ensure_backups(root: Path) -> None:
    backup_dir = root / "backups/09b9_custom_main"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for rel in ["code/code.0003.bin", "code/code.0003.def",
                "code/code.0006.bin", "code/code.0006.def"]:
        src = root / rel
        dst = backup_dir / Path(rel).name
        if not dst.exists() and src.exists():
            shutil.copy2(src, dst)

def restore_from_backup_code(root: Path) -> tuple[bytearray, bytearray, bytearray, bytearray]:
    backup_dir = root / "backup_code"
    if not backup_dir.is_dir():
        raise RuntimeError(f"missing stock baseline directory: {backup_dir}")
    code_dir = root / "code"
    code_dir.mkdir(parents=True, exist_ok=True)
    for name in ["code.0003.bin", "code.0003.def",
                 "code.0006.bin", "code.0006.def"]:
        shutil.copy2(backup_dir / name, code_dir / name)
    return (
        bytearray((code_dir / "code.0003.bin").read_bytes()),
        bytearray((code_dir / "code.0003.def").read_bytes()),
        bytearray((code_dir / "code.0006.bin").read_bytes()),
        bytearray((code_dir / "code.0006.def").read_bytes()),
    )

def load_def_base(def_bytes: bytes) -> int:
    return struct.unpack_from("<I", def_bytes, 0)[0]

# ---------------------------------------------------------------------------
# Builders

def build_sound_def() -> bytes:
    return struct.pack(
        "<ffiiiiBBhi",
        SOUND_DEF_MIN_RANGE, SOUND_DEF_MAX_RANGE,
        SOUND_DEF_MIN_VOLUME, SOUND_DEF_MAX_VOLUME,
        SOUND_DEF_MIN_PITCH,  SOUND_DEF_MAX_PITCH,
        SOUND_DEF_LOOP, SOUND_DEF_FLAGS,
        SOUND_DEF_INDEX, SOUND_DEF_BANK,
    )

def build_pulse_table() -> bytes:
    return b"".join(struct.pack("<f", v) for v in PULSE_VALUES)

def build_pulse_color_table() -> bytes:
    return b"".join(p32(c) for c in PULSE_COLORS)

def build_visual_update_helper(start_addr: int, pulse_table_addr: int,
                               pulse_color_table_addr: int) -> bytes:
    """
    Per-frame visual update. Caller must set up:
       $s4 = moby pointer
       $s5 = pvar pointer
    Writes:
       moby+0x32 (alpha byte = 0xFF)
       moby+0x34 |= 0x100 (visibility flag)
       moby+0x78 (pulse color word)
       pvar+0x04 (pulse intensity float)
    """
    game_time_hi, game_time_lo = split_hi_lo(GAME_TIME_ADDR)
    pt_hi, pt_lo = split_hi_lo(pulse_table_addr)
    pc_hi, pc_lo = split_hi_lo(pulse_color_table_addr)
    words = [
        encode_lhu(T0, S4, 0x0034),
        encode_ori(T0, T0, 0x0104),
        encode_sh (T0, S4, 0x0034),
        encode_addiu(T0, ZERO, 0x00FF),
        encode_sh (T0, S4, 0x0032),
        encode_lui(T0, game_time_hi),
        encode_lw (T0, T0, game_time_lo),
        encode_srl(T0, T0, PULSE_SHIFT),
        encode_andi(T0, T0, PULSE_MASK),
        encode_sll(T0, T0, 2),
        encode_lui(T1, pt_hi),
        encode_addiu(T1, T1, pt_lo),
        encode_addu(T1, T1, T0),
        encode_lw (AT, T1, 0),
        encode_mtc1(AT, F12),
        encode_swc1(F12, S5, 0x0004),
        encode_lui(T1, pc_hi),
        encode_addiu(T1, T1, pc_lo),
        encode_addu(T1, T1, T0),
        encode_lw (V0, T1, 0),
        encode_sw (V0, S4, 0x0078),
        encode_jr (RA),
        0x00000000,
    ]
    return b"".join(p32(w) for w in words)

def build_custom_main(start_addr: int, visual_helper_addr: int,
                      pending_ptr_addr: int, sound_def_addr: int,
                      pad_size: int = CUSTOM_MAIN_PAD_SIZE) -> bytes:
    """
    The 09B9 primary callback. Engine calls custom_main(moby) per frame.
    The remainder of the function pad is `jr $ra; nop` so that any
    `primary + offset` method dispatch the engine performs lands on a
    no-op return.

    Per-frame work at offset 0:
      - always set visibility/render flags (moby+0x34 |= 0x104) and alpha (moby+0x32 = 0xFF)
        so the moby is rendered regardless of pvar state
      - always write a fixed bright color to moby+0x78 as a diagnostic
        (overwritten by helper when pvar is valid)
      - if pending_ptr == this moby: play sound from moby context (audible to all
        players), clear pending_ptr. This is the moby-side sound trigger — fires on
        all consoles regardless of which player activated the pad.
      - if pvar is non-null, call visual_update_helper for pulsed look
      - return
    """
    # Diagnostic fixed color (bright cyan, opaque): A=0x80, R=0xC0, G=0xFF, B=0xFF
    DIAG_COLOR = 0x80FFFFC0
    words: list[int] = []

    def pc() -> int:
        return start_addr + len(words) * 4

    def emit(word: int) -> None:
        words.append(word)

    def patch_branch(index: int, word: int) -> None:
        words[index] = word

    emit(encode_addiu(SP, SP, -0x20))
    emit(encode_sw(RA, SP, 0x00))
    emit(encode_sw(S4, SP, 0x04))
    emit(encode_sw(S5, SP, 0x08))
    emit(encode_move(S4, A0))

    # Always set visibility flag and alpha (don't depend on pvar).
    emit(encode_lhu(T0, S4, 0x0034))
    emit(encode_ori(T0, T0, 0x0104))
    emit(encode_sh(T0, S4, 0x0034))
    emit(encode_addiu(T0, ZERO, 0x00FF))
    emit(encode_sh(T0, S4, 0x0032))

    # Always write diagnostic color to moby+0x78.
    emit(encode_lui(T0, (DIAG_COLOR >> 16) & 0xFFFF))
    emit(encode_ori(T0, T0, DIAG_COLOR & 0xFFFF))
    emit(encode_sw(T0, S4, 0x0078))

    emit(encode_lw(S5, S4, MOBY_PVAR_OFF))
    emit(encode_lbu(T0, S4, 0x0020))
    already_seeded_branch = len(words)
    emit(0)  # bne T0, ZERO, after_seed
    emit(0)

    # Donor state0 seeds moby/pvar visual state before state1 can visibly pulse.
    # Replicate only those local writes; avoid donor callbacks and imported state machine.
    emit(encode_lbu(T0, S4, 0x00BE))
    emit(encode_andi(T0, T0, 0x00FE))
    emit(encode_addiu(T1, ZERO, 1))
    emit(encode_sb(T1, S4, 0x0020))
    emit(encode_sh(ZERO, S4, 0x0096))
    emit(encode_sb(T0, S4, 0x00BE))
    pvar_seed_skip_branch = len(words)
    emit(0)  # beq S5, ZERO, after_seed
    emit(0)
    emit(encode_sw(ZERO, S5, 0x0010))
    emit(encode_sw(ZERO, S5, 0x0014))
    emit(encode_sw(ZERO, S5, 0x0018))
    emit(encode_sw(ZERO, S5, 0x001C))
    emit(encode_sw(ZERO, S5, 0x0020))
    emit(encode_lui(T0, 0x3E80))  # 0.25f
    emit(encode_sw(T0, S5, 0x0024))
    emit(encode_lui(T0, 0x3F00))  # 0.5f
    emit(encode_sw(T0, S5, 0x0028))
    emit(encode_lui(T0, 0x3F40))  # 0.75f
    emit(encode_sw(T0, S5, 0x002C))
    emit(encode_sw(ZERO, S5, 0x0030))
    emit(encode_sw(ZERO, S5, 0x0034))
    emit(encode_sw(ZERO, S5, 0x0038))
    emit(encode_sw(ZERO, S5, 0x003C))

    after_seed = pc()
    patch_branch(already_seeded_branch, encode_bne(T0, ZERO, start_addr + already_seeded_branch * 4, after_seed))
    patch_branch(pvar_seed_skip_branch, encode_beq(S5, ZERO, start_addr + pvar_seed_skip_branch * 4, after_seed))

    # Moby-side sound trigger. Check pending_ptr == S4 (this moby). If so, play
    # sound from the moby's update context so all consoles hear it (not just the
    # console whose player activated the pad), then clear the pending_ptr.
    pending_hi, pending_lo = split_hi_lo(pending_ptr_addr)
    emit(encode_lui(T1, pending_hi))
    emit(encode_lw(T0, T1, pending_lo))
    sound_skip_branch = len(words)
    emit(0)  # bne T0, S4, skip_sound
    emit(0)
    emit(encode_sw(ZERO, T1, pending_lo))         # clear pending_ptr
    emit(encode_move(A0, ZERO))                   # slot 0 = 09B9's first sound
    emit(encode_move(A1, ZERO))
    emit(encode_jal(SOUND_MOBY_PLAY_ADDR))
    emit(encode_move(A2, S4))                     # delay slot: moby ptr
    emit(0)
    skip_sound = pc()
    patch_branch(sound_skip_branch, encode_bne(T0, S4, start_addr + sound_skip_branch * 4, skip_sound))

    helper_skip_branch = len(words)
    emit(0)  # beq S5, ZERO, epilogue
    emit(0)
    emit(encode_jal(visual_helper_addr))
    emit(0)

    epilogue = pc()
    patch_branch(helper_skip_branch, encode_beq(S5, ZERO, start_addr + helper_skip_branch * 4, epilogue))
    emit(encode_lw(RA, SP, 0x00))
    emit(encode_lw(S4, SP, 0x04))
    emit(encode_lw(S5, SP, 0x08))
    emit(encode_addiu(SP, SP, 0x20))
    emit(encode_jr(RA))
    emit(0)
    real_code = b"".join(p32(w) for w in words)
    needed = pad_size - len(real_code)
    if needed < 0:
        raise RuntimeError(f"custom_main real code ({len(real_code)} bytes) exceeds pad size ({pad_size})")
    if needed % 8 != 0:
        raise RuntimeError("pad size must align to 8 bytes")
    return real_code + (stub_pair() * (needed // 8))

def build_launch_hook(start_addr: int, pending_ptr_addr: int, sound_def_addr: int,
                     state_set_return_addr: int, original_10c4_handler_addr: int,
                     original_no_match_addr: int) -> bytes:
    """
    Patched into the level44 stock compare site. When player is on a
    moby of class 09B9, store the moby pointer in pending_ptr, transition
    player to FALL state, then bounce out to velocity_wrapper.

    Sound is NOT played here. It fires instead from custom_main (moby-side)
    on the next frame when it detects pending_ptr == this moby. That way all
    consoles hear the sound regardless of which player activated the pad.
    """
    pending_hi, pending_lo = split_hi_lo(pending_ptr_addr)
    native_10c4 = start_addr + (40 * 4)
    no_match    = start_addr + (44 * 4)
    skip_queue  = start_addr + ( 9 * 4)
    skip_sound  = start_addr + (22 * 4)
    words = [
        encode_beq(V1, V0, start_addr + 0 * 4, native_10c4),
        encode_addiu(V0, ZERO, CLASS_09B9),
        encode_bne(V1, V0, start_addr + 2 * 4, no_match),
        0x00000000,
        encode_lw(A2, S1, GROUND_PMOBY_OFF),
        encode_beq(A2, ZERO, start_addr + 5 * 4, skip_queue),
        0x00000000,
        encode_lui(T0, pending_hi),
        encode_sw(A2, T0, pending_lo),
        encode_move(A2, A2),
        encode_beq(A2, ZERO, start_addr + 10 * 4, skip_sound),
        0x00000000,
        # indices 12-21: was sound call, now NOPs (sound moved to custom_main)
        0x00000000,
        0x00000000,
        0x00000000,
        0x00000000,
        0x00000000,
        0x00000000,
        0x00000000,
        0x00000000,
        0x00000000,
        0x00000000,
        encode_sw(ZERO, S1, GROUND_PMOBY_OFF),
        encode_sw(ZERO, S1, GROUND_ONGOOD_OFF),
        encode_lw(V1, S1, PLAYER_VTABLE_OFF),
        encode_move(A0, S1),
        encode_addiu(A1, ZERO, STATE_FALL),
        encode_addiu(A2, ZERO, 1),
        encode_move(A3, ZERO),
        encode_lw(V0, V1, VTABLE_SET_STATE_OFF),
        0x0040F809,                                             # jalr $v0
        encode_addiu(T0, ZERO, 1),                              # delay slot
        # 32: lui $1, 0x4120  (will be patched to `j velocity_wrapper`)
        encode_lui(AT, (LAUNCH_VELOCITY_BITS >> 16) & 0xFFFF),
        encode_mtc1(AT, F0),
        encode_swc1(F0, S1, MOVE_BEHAVIOR_Z_OFF),
        encode_swc1(F0, S1, MOVE_ACTUAL_Z_OFF),
        encode_swc1(F0, S1, MOVE_ASCENT_OFF),
        encode_swc1(F0, S1, MOVE_ZSPEED_OFF),
        encode_j(state_set_return_addr),
        encode_move(V0, ZERO),
        # native_10c4 path:
        encode_lw(V1, S1, PLAYER_VTABLE_OFF),
        encode_move(A0, S1),
        encode_j(original_10c4_handler_addr),
        encode_addiu(A1, ZERO, STATE_MOON_JUMP),
        # no_match path:
        encode_lbu(V0, S1, 0x19E4),
        encode_j(original_no_match_addr),
        0x00000000,
    ]
    return b"".join(p32(w) for w in words)

def build_velocity_wrapper(start_addr: int, pending_ptr_addr: int,
                          default_params_addr: int, state_set_return_addr: int) -> bytes:
    """
    Reads pending_ptr to find the touched moby, pulls up_velocity and
    forward_boost from its pvar, applies launch-related player fields,
    then jumps back into the stock setState dispatch.
    """
    pending_hi, pending_lo = split_hi_lo(pending_ptr_addr)
    default_hi, default_lo = split_hi_lo(default_params_addr)
    use_default  = start_addr + (12 * 4)
    apply_launch = start_addr + (18 * 4)
    words = [
        encode_lui(T1, pending_hi),
        encode_lw(T0, T1, pending_lo),
        encode_beq(T0, ZERO, start_addr + 2 * 4, use_default),
        0x00000000,
        encode_lw(T0, T0, MOBY_PVAR_OFF),
        encode_beq(T0, ZERO, start_addr + 5 * 4, use_default),
        0x00000000,
        encode_lw(AT, T0, PVAR_UP_VELOCITY_OFF),
        encode_mtc1(AT, F2),
        encode_lw(AT, T0, PVAR_FORWARD_BOOST_OFF),
        encode_mtc1(AT, F0),
        encode_j(apply_launch),
        0x00000000,
        encode_lui(T1, default_hi),
        encode_lw(AT, T1, default_lo),
        encode_mtc1(AT, F2),
        encode_lw(AT, T1, default_lo + 4),
        encode_mtc1(AT, F0),
        encode_lwc1(F4, S1, PLAYER_FALL_GRAVITY_OFF),
        encode_mul_s(F4, F4, F2),
        encode_swc1(F4, S1, PLAYER_FALL_GRAVITY_OFF),
        encode_lui(AT, (TEST_HORIZONTAL_SCALE_BITS >> 16) & 0xFFFF),
        encode_mtc1(AT, F6),
        encode_lwc1(F4, S1, PLAYER_WIND_VEL_X_OFF),
        encode_mul_s(F4, F4, F6),
        encode_swc1(F4, S1, PLAYER_WIND_VEL_X_OFF),
        encode_lwc1(F4, S1, PLAYER_WIND_VEL_Y_OFF),
        encode_mul_s(F4, F4, F6),
        encode_swc1(F4, S1, PLAYER_WIND_VEL_Y_OFF),
        encode_lwc1(F4, S1, PLAYER_WIND_SPEED_OFF),
        encode_mul_s(F4, F4, F6),
        encode_swc1(F4, S1, PLAYER_WIND_SPEED_OFF),
        encode_swc1(F0, S1, MOVE_BEHAVIOR_Z_OFF),
        encode_swc1(F0, S1, MOVE_ACTUAL_Z_OFF),
        encode_swc1(F0, S1, MOVE_ASCENT_OFF),
        encode_swc1(F0, S1, MOVE_ZSPEED_OFF),
        encode_j(state_set_return_addr),
        encode_move(V0, ZERO),
    ]
    return b"".join(p32(w) for w in words)

def patch_instance_pvars(root: Path, fall_gravity_scale: float, up_velocity: float) -> list[Path]:
    patched: list[Path] = []
    for path in sorted(root.glob(PVAR_GLOB)):
        blob = bytearray(path.read_bytes())
        if len(blob) != PVAR_SIZE:
            continue
        blob[PVAR_UP_VELOCITY_OFF:PVAR_UP_VELOCITY_OFF + 4]   = struct.pack("<f", fall_gravity_scale)
        blob[PVAR_FORWARD_BOOST_OFF:PVAR_FORWARD_BOOST_OFF+4] = struct.pack("<f", up_velocity)
        path.write_bytes(blob)
        patched.append(path)
    return patched

# ---------------------------------------------------------------------------
# Main

def main() -> None:
    parser = argparse.ArgumentParser(description="Custom-main pivot for level44 0x09B9 jump pad.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--fall-gravity-scale", type=float, default=DEFAULT_FALL_GRAVITY_SCALE)
    parser.add_argument("--up-velocity",        type=float, default=DEFAULT_UP_VELOCITY)
    parser.add_argument("--pad-size", type=lambda s: int(s, 0), default=CUSTOM_MAIN_PAD_SIZE,
                        help="Total bytes for custom_main (real code + jr $ra; nop stubs). Default 0x800.")
    args = parser.parse_args()

    root = args.root.resolve()
    ensure_backups(root)
    code3, code3_def, code6, code6_def = restore_from_backup_code(root)
    code3_base = load_def_base(code3_def)
    code6_base = load_def_base(code6_def)

    # Anchors
    compare_addr, match_addr, no_match_addr, state_set_return_addr = find_compare_site(code6, code6_base)
    _, _, stock_10c4_secondary = find_class_slot(code3, code3_base, CLASS_10C4)
    if not (code3_base <= stock_10c4_secondary < code3_base + len(code3)):
        raise RuntimeError(f"0x10C4 secondary outside code.0003: 0x{stock_10c4_secondary:08X}")
    stock_10c4_secondary_off = stock_10c4_secondary - code3_base

    registry_slot_addr, registry_secondary_addr = find_reuse_slot(code3, code3_base)
    registry_slot_off      = registry_slot_addr - code3_base
    registry_secondary_off = registry_secondary_addr - code3_base

    # Layout (everything appended at end of code.0006):
    #   custom_main (0x800 bytes, padded with stubs)
    #   launch_hook
    #   velocity_wrapper
    #   visual_update_helper
    #   pending_ptr  (4 bytes)
    #   sound_def    (constant)
    #   pulse_table  (16 floats)
    #   pulse_color_table (16 words)
    #   default_params (2 floats)

    # Pre-measure to compute addresses.
    custom_main_vma     = code6_base + len(code6)
    custom_main_len     = args.pad_size
    launch_hook_vma     = custom_main_vma + custom_main_len
    launch_hook_len     = len(build_launch_hook(launch_hook_vma, 0, 0,
                                                state_set_return_addr,
                                                match_addr, no_match_addr))
    velocity_wrapper_vma = launch_hook_vma + launch_hook_len
    velocity_wrapper_len = len(build_velocity_wrapper(velocity_wrapper_vma, 0, 0, state_set_return_addr))
    visual_helper_vma   = velocity_wrapper_vma + velocity_wrapper_len
    visual_helper_len   = len(build_visual_update_helper(visual_helper_vma, 0, 0))
    pending_ptr_addr    = visual_helper_vma + visual_helper_len
    sound_def_addr      = pending_ptr_addr + 4
    pulse_table_addr    = sound_def_addr + len(build_sound_def())
    pulse_color_addr    = pulse_table_addr + len(build_pulse_table())
    default_params_addr = pulse_color_addr + len(build_pulse_color_table())

    # Real builds with resolved addresses.
    custom_main_bytes  = build_custom_main(custom_main_vma, visual_helper_vma,
                                           pending_ptr_addr, sound_def_addr, args.pad_size)
    launch_hook_bytes  = bytearray(build_launch_hook(launch_hook_vma, pending_ptr_addr, sound_def_addr,
                                                     state_set_return_addr, match_addr, no_match_addr))
    # Patch the launch_hook lui+mtc1 to "j velocity_wrapper; nop"
    old_word  = u32(launch_hook_bytes, VELOCITY_PATCH_ADDR_DELTA)
    old_delay = u32(launch_hook_bytes, VELOCITY_PATCH_ADDR_DELTA + 4)
    if old_word != VELOCITY_PATCH_OLD_WORD or old_delay != VELOCITY_PATCH_DELAY_OLD_WORD:
        raise RuntimeError(f"unexpected launch velocity words: 0x{old_word:08X} / 0x{old_delay:08X}")
    launch_hook_bytes[VELOCITY_PATCH_ADDR_DELTA    :VELOCITY_PATCH_ADDR_DELTA + 4] = p32(encode_j(velocity_wrapper_vma))
    launch_hook_bytes[VELOCITY_PATCH_ADDR_DELTA + 4:VELOCITY_PATCH_ADDR_DELTA + 8] = p32(0)

    velocity_wrapper_bytes = build_velocity_wrapper(velocity_wrapper_vma, pending_ptr_addr,
                                                    default_params_addr, state_set_return_addr)
    visual_helper_bytes    = build_visual_update_helper(visual_helper_vma, pulse_table_addr, pulse_color_addr)

    # Append everything to code.0006.
    code6.extend(custom_main_bytes)
    code6.extend(launch_hook_bytes)
    code6.extend(velocity_wrapper_bytes)
    code6.extend(visual_helper_bytes)
    code6.extend(p32(0))                                                 # pending_ptr
    code6.extend(build_sound_def())
    code6.extend(build_pulse_table())
    code6.extend(build_pulse_color_table())
    code6.extend(struct.pack("<ff", args.fall_gravity_scale, args.up_velocity))  # default_params

    # Patch the compare site in stock code.0006 to jump to our launch_hook.
    compare_off = compare_addr - code6_base
    code6[compare_off:compare_off + 4] = p32(encode_j(launch_hook_vma))
    code6[compare_off + 4:compare_off + 8] = p32(0)

    # Copy stock 10C4 secondary blob into the hijacked slot's secondary location.
    code3[registry_secondary_off:registry_secondary_off + 48] = code3[stock_10c4_secondary_off:stock_10c4_secondary_off + 48]

    # Update registry slot: class=09B9, primary=custom_main, secondary unchanged.
    code3[registry_slot_off:registry_slot_off + 12] = (
        p32(CLASS_09B9) + p32(custom_main_vma) + p32(registry_secondary_addr)
    )

    # Update code.0006 def with new size.
    code6_def[4:8] = p32(len(code6))

    code_dir = root / "code"
    (code_dir / "code.0003.bin").write_bytes(bytes(code3))
    (code_dir / "code.0003.def").write_bytes(bytes(code3_def))
    (code_dir / "code.0006.bin").write_bytes(bytes(code6))
    (code_dir / "code.0006.def").write_bytes(bytes(code6_def))

    patched_pvars = patch_instance_pvars(root, args.fall_gravity_scale, args.up_velocity)

    print("patched level44 0x09B9 with custom-main pivot")
    print(f"  custom_main:        0x{custom_main_vma:08X}  (size 0x{custom_main_len:X})")
    print(f"  launch_hook:        0x{launch_hook_vma:08X}")
    print(f"  velocity_wrapper:   0x{velocity_wrapper_vma:08X}")
    print(f"  visual_helper:      0x{visual_helper_vma:08X}")
    print(f"  pending_ptr:        0x{pending_ptr_addr:08X}")
    print(f"  sound_def:          0x{sound_def_addr:08X}")
    print(f"  pulse_table:        0x{pulse_table_addr:08X}")
    print(f"  pulse_color_table:  0x{pulse_color_addr:08X}")
    print(f"  default_params:     0x{default_params_addr:08X}")
    print(f"  registry slot:      0x{registry_slot_addr:08X}  class=09B9 primary->custom_main")
    print(f"  compare hook:       0x{compare_addr:08X} -> 0x{launch_hook_vma:08X}")
    print(f"  state_set_return:   0x{state_set_return_addr:08X}")
    print(f"  patched pvars:      {len(patched_pvars)}")

if __name__ == "__main__":
    main()
