#!/usr/bin/env python3
"""
Patch local 0x09B9 launch to keep the verified working physics and moby-side
sound, while repairing the imported level24 visual path.

That keeps:
  - the working player launch hook
  - the working moby-side sound relay

Also tries, unsuccessfully, to do the following (partical and pulsating ) 
  - force the visual threshold gate open at 0x54D89C
  - repoint the level24-only helpers to the relocated imported copies:
      0x338898 -> 0x54D94C
      0x338A80 -> 0x54D9F8
      
Use a clean, working, backup set of code.0006.bin
!NTSC HOVEN RAC3 ONLY. Run from root unpacked level folder
 
"""

from __future__ import annotations

import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

SOURCE_CODE6_PATH = ROOT / "bk_code_working_1/code.0006.bin"
SOURCE_CODE6_DEF_PATH = ROOT / "bk_code_working_1/code.0006.def"
TARGET_CODE6_PATH = ROOT / "code/code.0006.bin"
TARGET_CODE6_DEF_PATH = ROOT / "code/code.0006.def"

CODE6_BASE = 0x3C4980

MOON_JUMP_COMPARE_ADDR = 0x5235A0
OLD_HOOK_VMA = 0x554378
OLD_HOOK_FILE_OFF = OLD_HOOK_VMA - CODE6_BASE
OLD_HOOK_SIZE = 0x54

MOBY_SOUND_PATCH_ADDR = 0x54D620
MOBY_SOUND_PATCH_DELAY_ADDR = 0x54D624
MOBY_SOUND_CONTINUE_ADDR = 0x54D624
MOBY_SOUND_OLD_WORD = 0x92900020
MOBY_SOUND_DELAY_WORD = 0x12000006

STATE1_FORCE_FX_ADDR = 0x54D89C
STATE1_FORCE_FX_OLD_WORD = 0x45020008
STATE1_FORCE_FX_NEW_WORD = 0x00000000

STATE1_VISUAL_CALL_ADDR = 0x54D8A4
STATE1_VISUAL_CALL_OLD_WORD = 0x0C0CE226
STATE1_VISUAL_CALL_TARGET = 0x54D94C

STATE1_QUEUE_LUI_ADDR = 0x54D8AC
STATE1_QUEUE_LUI_OLD_WORD = 0x3C040034
STATE1_QUEUE_ADDIU_ADDR = 0x54D8B8
STATE1_QUEUE_ADDIU_OLD_WORD = 0x24848A80
STATE1_QUEUE_TARGET = 0x54D9F8

STATE_SET_RETURN_ADDR = 0x528650
ORIGINAL_NO_MATCH_ADDR = 0x5235BC
ORIGINAL_10C4_HANDLER_ADDR = 0x523670

SOUND_PLAY_ADDR = 0x004C5188

PLAYER_VTABLE_OFF = 0x0014
MOVE_BEHAVIOR_Z_OFF = 0x0128
MOVE_ACTUAL_Z_OFF = 0x0148
MOVE_ASCENT_OFF = 0x01AC
MOVE_ZSPEED_OFF = 0x01B0
GROUND_PMOBY_OFF = 0x02CC
GROUND_ONGOOD_OFF = 0x02D0
VTABLE_SET_STATE_OFF = 0x0034

LAUNCH_VELOCITY = 10.0
LAUNCH_VELOCITY_BITS = struct.unpack("<I", struct.pack("<f", LAUNCH_VELOCITY))[0]

STATE_FALL = 6
STATE_MOON_JUMP = 131

CLASS_10C4 = 0x10C4
CLASS_09B9 = 0x09B9

SOUND_VOLUME = 0x400
SOUND_DEF_MIN_RANGE = 0.0
SOUND_DEF_MAX_RANGE = 45.0
SOUND_DEF_MIN_VOLUME = 0
SOUND_DEF_MAX_VOLUME = 1228
SOUND_DEF_MIN_PITCH = -635
SOUND_DEF_MAX_PITCH = 635
SOUND_DEF_LOOP = 0
SOUND_DEF_FLAGS = 0x10
SOUND_DEF_INDEX = 0x009C
SOUND_DEF_BANK = 0


def p32(v: int) -> bytes:
    return struct.pack("<I", v & 0xFFFFFFFF)


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def encode_j(target: int) -> int:
    return 0x08000000 | ((target >> 2) & 0x03FFFFFF)


def encode_jal(target: int) -> int:
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def encode_beq(rs: int, rt: int, pc: int, target: int) -> int:
    delta = (target - (pc + 4)) >> 2
    return 0x10000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (delta & 0xFFFF)


def encode_bne(rs: int, rt: int, pc: int, target: int) -> int:
    delta = (target - (pc + 4)) >> 2
    return 0x14000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (delta & 0xFFFF)


def encode_addiu(rt: int, rs: int, imm: int) -> int:
    return 0x24000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (imm & 0xFFFF)


def encode_lui(rt: int, imm: int) -> int:
    return 0x3C000000 | ((rt & 0x1F) << 16) | (imm & 0xFFFF)


def encode_lw(rt: int, rs: int, imm: int) -> int:
    return 0x8C000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (imm & 0xFFFF)


def encode_lbu(rt: int, rs: int, imm: int) -> int:
    return 0x90000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (imm & 0xFFFF)


def encode_sw(rt: int, rs: int, imm: int) -> int:
    return 0xAC000000 | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (imm & 0xFFFF)


def encode_swc1(ft: int, rs: int, imm: int) -> int:
    return 0xE4000000 | ((rs & 0x1F) << 21) | ((ft & 0x1F) << 16) | (imm & 0xFFFF)


def encode_mtc1(rt: int, fs: int) -> int:
    return 0x44800000 | ((rt & 0x1F) << 16) | ((fs & 0x1F) << 11)


def encode_move(rd: int, rs: int) -> int:
    return ((rs & 0x1F) << 21) | ((rd & 0x1F) << 11) | 0x2D


def split_hi_lo(addr: int) -> tuple[int, int]:
    hi = (addr + 0x8000) >> 16
    lo = addr - (hi << 16)
    return hi & 0xFFFF, lo & 0xFFFF


def build_sound_def() -> bytes:
    return struct.pack(
        "<ffiiiiBBhi",
        SOUND_DEF_MIN_RANGE,
        SOUND_DEF_MAX_RANGE,
        SOUND_DEF_MIN_VOLUME,
        SOUND_DEF_MAX_VOLUME,
        SOUND_DEF_MIN_PITCH,
        SOUND_DEF_MAX_PITCH,
        SOUND_DEF_LOOP,
        SOUND_DEF_FLAGS,
        SOUND_DEF_INDEX,
        SOUND_DEF_BANK,
    )


ZERO, AT, V0, V1, A0, A1, A2, A3 = 0, 1, 2, 3, 4, 5, 6, 7
T0, T1 = 8, 9
S0, S1, S4, SP = 16, 17, 20, 29


def build_launch_hook(start_addr: int, pending_ptr_addr: int) -> bytes:
    pending_hi, pending_lo = split_hi_lo(pending_ptr_addr)
    native_10c4 = start_addr + (27 * 4)
    no_match = start_addr + (31 * 4)
    skip_queue = start_addr + (10 * 4)

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
        encode_sw(ZERO, S1, GROUND_PMOBY_OFF),
        encode_sw(ZERO, S1, GROUND_ONGOOD_OFF),
        encode_lw(V1, S1, PLAYER_VTABLE_OFF),
        encode_move(A0, S1),
        encode_addiu(A1, ZERO, STATE_FALL),
        encode_addiu(A2, ZERO, 1),
        encode_move(A3, ZERO),
        encode_lw(V0, V1, VTABLE_SET_STATE_OFF),
        0x0040F809,
        encode_addiu(T0, ZERO, 1),
        encode_lui(AT, (LAUNCH_VELOCITY_BITS >> 16) & 0xFFFF),
        encode_mtc1(AT, 0),
        encode_swc1(0, S1, MOVE_BEHAVIOR_Z_OFF),
        encode_swc1(0, S1, MOVE_ACTUAL_Z_OFF),
        encode_swc1(0, S1, MOVE_ASCENT_OFF),
        encode_swc1(0, S1, MOVE_ZSPEED_OFF),
        encode_j(STATE_SET_RETURN_ADDR),
        encode_move(V0, ZERO),
        encode_lw(V1, S1, PLAYER_VTABLE_OFF),
        encode_move(A0, S1),
        encode_j(ORIGINAL_10C4_HANDLER_ADDR),
        encode_addiu(A1, ZERO, STATE_MOON_JUMP),
        encode_lbu(V0, S1, 0x19E4),
        encode_j(ORIGINAL_NO_MATCH_ADDR),
        0x00000000,
    ]

    return b"".join(p32(w) for w in words)


def build_moby_sound_wrapper(start_addr: int, pending_ptr_addr: int, sound_def_addr: int) -> bytes:
    pending_hi, pending_lo = split_hi_lo(pending_ptr_addr)
    sound_def_hi, sound_def_lo = split_hi_lo(sound_def_addr)

    skip_sound = start_addr + (16 * 4)

    words = [
        encode_lui(T1, pending_hi),
        encode_lw(T0, T1, pending_lo),
        encode_bne(T0, S4, start_addr + 2 * 4, skip_sound),
        0x00000000,
        encode_sw(ZERO, T1, pending_lo),
        encode_addiu(SP, SP, -0x18),
        encode_lui(T0, sound_def_hi),
        encode_addiu(T0, T0, sound_def_lo),
        encode_addiu(T1, ZERO, SOUND_VOLUME),
        encode_sw(T1, SP, 0x10),
        encode_move(A0, T0),
        encode_move(A1, ZERO),
        encode_move(A2, S4),
        encode_jal(SOUND_PLAY_ADDR),
        encode_move(A3, ZERO),
        encode_addiu(SP, SP, 0x18),
        encode_j(MOBY_SOUND_CONTINUE_ADDR),
        encode_lbu(S0, S4, 0x20),
    ]

    return b"".join(p32(w) for w in words)


def main() -> None:
    code6 = bytearray(SOURCE_CODE6_PATH.read_bytes())
    code6_def = bytearray(SOURCE_CODE6_DEF_PATH.read_bytes())

    redirect_off = MOON_JUMP_COMPARE_ADDR - CODE6_BASE
    redirect_word = u32(code6, redirect_off)
    redirect_target = ((MOON_JUMP_COMPARE_ADDR + 4) & 0xF0000000) | (
        (redirect_word & 0x03FFFFFF) << 2
    )
    if redirect_target != OLD_HOOK_VMA:
        print(
            f"WARNING: redirect at 0x{MOON_JUMP_COMPARE_ADDR:08X} points to "
            f"0x{redirect_target:08X}, expected 0x{OLD_HOOK_VMA:08X}"
        )
        print("Proceeding anyway (will update redirect).")

    if len(code6) < OLD_HOOK_FILE_OFF + OLD_HOOK_SIZE:
        raise RuntimeError(
            f"code6 is too small (0x{len(code6):x}), expected old hook at 0x{OLD_HOOK_FILE_OFF:x}"
        )

    moby_patch_off = MOBY_SOUND_PATCH_ADDR - CODE6_BASE
    moby_delay_off = MOBY_SOUND_PATCH_DELAY_ADDR - CODE6_BASE
    state1_fx_off = STATE1_FORCE_FX_ADDR - CODE6_BASE
    state1_visual_call_off = STATE1_VISUAL_CALL_ADDR - CODE6_BASE
    state1_queue_lui_off = STATE1_QUEUE_LUI_ADDR - CODE6_BASE
    state1_queue_addiu_off = STATE1_QUEUE_ADDIU_ADDR - CODE6_BASE

    found = u32(code6, moby_patch_off)
    delay_found = u32(code6, moby_delay_off)
    fx_found = u32(code6, state1_fx_off)
    visual_call_found = u32(code6, state1_visual_call_off)
    queue_lui_found = u32(code6, state1_queue_lui_off)
    queue_addiu_found = u32(code6, state1_queue_addiu_off)
    if found != MOBY_SOUND_OLD_WORD:
        raise RuntimeError(
            f"unexpected word at 0x{MOBY_SOUND_PATCH_ADDR:08X}: found 0x{found:08X}, expected 0x{MOBY_SOUND_OLD_WORD:08X}"
        )
    if delay_found != MOBY_SOUND_DELAY_WORD:
        raise RuntimeError(
            f"unexpected delay-slot word at 0x{MOBY_SOUND_PATCH_DELAY_ADDR:08X}: found 0x{delay_found:08X}, expected 0x{MOBY_SOUND_DELAY_WORD:08X}"
        )
    if fx_found != STATE1_FORCE_FX_OLD_WORD:
        raise RuntimeError(
            f"unexpected state1 word at 0x{STATE1_FORCE_FX_ADDR:08X}: found 0x{fx_found:08X}, expected 0x{STATE1_FORCE_FX_OLD_WORD:08X}"
        )
    if visual_call_found != STATE1_VISUAL_CALL_OLD_WORD:
        raise RuntimeError(
            f"unexpected visual call at 0x{STATE1_VISUAL_CALL_ADDR:08X}: found 0x{visual_call_found:08X}, expected 0x{STATE1_VISUAL_CALL_OLD_WORD:08X}"
        )
    if queue_lui_found != STATE1_QUEUE_LUI_OLD_WORD:
        raise RuntimeError(
            f"unexpected queue lui at 0x{STATE1_QUEUE_LUI_ADDR:08X}: found 0x{queue_lui_found:08X}, expected 0x{STATE1_QUEUE_LUI_OLD_WORD:08X}"
        )
    if queue_addiu_found != STATE1_QUEUE_ADDIU_OLD_WORD:
        raise RuntimeError(
            f"unexpected queue addiu at 0x{STATE1_QUEUE_ADDIU_ADDR:08X}: found 0x{queue_addiu_found:08X}, expected 0x{STATE1_QUEUE_ADDIU_OLD_WORD:08X}"
        )

    code6 = bytearray(code6[:OLD_HOOK_FILE_OFF])

    launch_hook_vma = CODE6_BASE + len(code6)
    launch_hook_len = len(build_launch_hook(launch_hook_vma, 0))
    moby_wrapper_vma = launch_hook_vma + launch_hook_len
    moby_wrapper_len = len(build_moby_sound_wrapper(moby_wrapper_vma, 0, 0))
    pending_ptr_addr = moby_wrapper_vma + moby_wrapper_len
    sound_def_addr = pending_ptr_addr + 4

    launch_hook = build_launch_hook(launch_hook_vma, pending_ptr_addr)
    moby_wrapper = build_moby_sound_wrapper(moby_wrapper_vma, pending_ptr_addr, sound_def_addr)
    code6.extend(launch_hook)
    code6.extend(moby_wrapper)
    code6.extend(p32(0))
    code6.extend(build_sound_def())

    queue_hi, queue_lo = split_hi_lo(STATE1_QUEUE_TARGET)

    code6[redirect_off:redirect_off + 4] = p32(encode_j(launch_hook_vma))
    code6[redirect_off + 4:redirect_off + 8] = p32(0x00000000)
    code6[moby_patch_off:moby_patch_off + 4] = p32(encode_j(moby_wrapper_vma))
    code6[state1_fx_off:state1_fx_off + 4] = p32(STATE1_FORCE_FX_NEW_WORD)
    code6[state1_visual_call_off:state1_visual_call_off + 4] = p32(encode_jal(STATE1_VISUAL_CALL_TARGET))
    code6[state1_queue_lui_off:state1_queue_lui_off + 4] = p32(encode_lui(A0, queue_hi))
    code6[state1_queue_addiu_off:state1_queue_addiu_off + 4] = p32(encode_addiu(A0, A0, queue_lo))

    code6_def[4:8] = p32(len(code6))

    TARGET_CODE6_PATH.write_bytes(code6)
    TARGET_CODE6_DEF_PATH.write_bytes(code6_def)

    print("patched local 0x09B9 launch hook (moby_sound_visuals)")
    print(f"  source code6:     {SOURCE_CODE6_PATH}")
    print(f"  launch hook:      0x{launch_hook_vma:08X} ({len(launch_hook)} bytes)")
    print(f"  moby wrapper:     0x{moby_wrapper_vma:08X} ({len(moby_wrapper)} bytes)")
    print(f"  player redirect:  0x{MOON_JUMP_COMPARE_ADDR:08X} -> 0x{launch_hook_vma:08X}")
    print(f"  moby redirect:    0x{MOBY_SOUND_PATCH_ADDR:08X} -> 0x{moby_wrapper_vma:08X}")
    print(f"  pending ptr:      0x{pending_ptr_addr:08X}")
    print(f"  sound call:       soundPlay(index=0x{SOUND_DEF_INDEX:04X}, bank={SOUND_DEF_BANK}, volume=0x{SOUND_VOLUME:X})")
    print(f"  state1 FX gate:   0x{STATE1_FORCE_FX_ADDR:08X} = nop")
    print(f"  visual helper:    0x{STATE1_VISUAL_CALL_ADDR:08X} -> 0x{STATE1_VISUAL_CALL_TARGET:08X}")
    print(f"  queued callback:  0x{STATE1_QUEUE_LUI_ADDR:08X}/0x{STATE1_QUEUE_ADDIU_ADDR:08X} -> 0x{STATE1_QUEUE_TARGET:08X}")


if __name__ == "__main__":
    main()
