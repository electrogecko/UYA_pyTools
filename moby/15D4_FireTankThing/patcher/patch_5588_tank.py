#!/usr/bin/env python3
"""
Patch Level41 NTSC (Hoven Gorge) to activate moby class 5588 (0x15D4) as a working vehicle.

What this does:
  1. Appends ~300 bytes of MIPS stub code to code.0006.bin
     - nop_callback: returns 0 (used for all 7 vehicle callback slots)
     - get_vehicle_base: returns Vehicle* from pvar+0x6D0
     - update_5588: state 0 initializes vehicle framework, state 1+ is idle
  2. Updates code.0006.def with new size
  3. Patches class table in code.0003.bin: dormant slot 0x16DB -> 0x15D4
     (class 0x16DB = SKIN_SNOWMAN had a null func, unused in MP) [todo, probably a better way]
  4. Expands pvar for instance 229 from 432 -> 2048 bytes (for Vehicle* at +0x6D0)
  5. Fixes vehicle pad (instance 230) pvar[0] to reference 229 (the tank)

Usage:
  tools/patch_5588_vehicle.py              # apply patch (idempotent)
  tools/patch_5588_vehicle.py --from-stock # reset from code_stock/ then patch
  tools/patch_5588_vehicle.py --restore    # restore code/ from code_stock/

Prerequisites (already done):
  - Instance 229 (class 0x15D4) placed in gameplay/moby/0229_05588_15D4/
  - Instance 230 (vehicle pad 0x1981) placed in gameplay/moby/0230_06529_1981/
    at same location as the tank
  - Assets for class 5588 imported (model, textures, sounds)
- A1: scan the 8-player table and prefer other players / occupied vehicles.
- A : if that finds nothing, walk the live moby list and pick the nearest
      forward-facing dynamic moby.

"""

try:
    import patch_5588_vehicle as base
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from . import patch_5588_vehicle as base

for _name in dir(base):
    if not _name.startswith("_"):
        globals()[_name] = getattr(base, _name)


PLAYER_STRUCT_ARRAY_ADDR = 0x002496B0  # Hoven NTSC
BEGIN_MOBY_PTR_ADDR = 0x002487DC       # Hoven NTSC
END_MOBY_PTR_ADDR = BEGIN_MOBY_PTR_ADDR + 0x8

GAME_MAX_PLAYERS = 8
PLAYER_MOBY_OFF = 0x2524
PLAYER_VEHICLE_OFF = 0x2528
VEHICLE_MOBY_OFF = 0x2D0
MOBY_ENTRY_SIZE = 0x100

TARGET_RANGE = 1000.0
TARGET_MAX_DIST2_U32 = float_to_u32(TARGET_RANGE * TARGET_RANGE)

EXCLUDE_CLASS_PAD = 0x1981
EXCLUDE_CLASS_ROCKET = 0x1B1E

# In spawnRocket1B1E (0x42A570), stock code only stores s5 -> rocketPvar+0x24
# if a secondary validator-byte gate passes. For the tank test that appears to
# discard otherwise-usable targets. Force the accept-target branch once
# 0x480870(target) itself succeeds.
FACTORY_TARGET_GATE_SITES = [
    (0x0042A6A8, 0x10600003, 0x10000003),   # beqz v1,+3 -> b +3
]
ADDR_QUERY_VECTOR_SCALE = 0x0045E1B8
ADDR_TARGET_VALIDATOR = 0x00480870
ADDR_CANDIDATE_CLASS9_FALLBACK = 0x00486BE8
WATCH_MOBY_PTR = 0x01AA7E40

base.ROCKET_DAMAGE_SITES = base.ROCKET_DAMAGE_SITES + FACTORY_TARGET_GATE_SITES

DEBUG_PICK_RESULT_OFF = 0x00
DEBUG_PICK_SOURCE_OFF = 0x04
DEBUG_PICK_DIST2_OFF = 0x08
DEBUG_PICK_CALLS_OFF = 0x0C
DEBUG_FIRST_HOSTILE_PTR_OFF = 0x10
DEBUG_FIRST_HOSTILE_CLASS_OFF = 0x14
DEBUG_FIRST_HOSTILE_STAGE_OFF = 0x18
DEBUG_FIRST_HOSTILE_PASS_PTR_OFF = 0x1C
DEBUG_FIRST_HOSTILE_PASS_CLASS_OFF = 0x20
DEBUG_STOCK_COUNT_OFF = 0x24
DEBUG_STOCK_LIST0_PTR_OFF = 0x28
DEBUG_STOCK_LIST0_CLASS_OFF = 0x2C
DEBUG_STOCK_LIST1_PTR_OFF = 0x30
DEBUG_STOCK_LIST1_CLASS_OFF = 0x34
DEBUG_STOCK_COLLOUT_PTR_OFF = 0x38
DEBUG_STOCK_COLLOUT_CLASS_OFF = 0x3C
DEBUG_WATCH_STAGE_OFF = 0x40
DEBUG_WATCH_GROUP_OFF = 0x44
DEBUG_WATCH_PARENT_OFF = 0x48
DEBUG_WATCH_CHAIN_OFF = 0x4C
DEBUG_WATCH_VALIDATOR_PTR_OFF = 0x50
DEBUG_WATCH_VALIDATOR_VAL_OFF = 0x54
DEBUG_WATCH_PCLASS46_OFF = 0x58
DEBUG_WATCH_MODEBITS_OFF = 0x5C
DEBUG_PLAYER_TEAM_OFF = 0x60
DEBUG_WATCH_TARGET_TEAM_OFF = 0x64
DEBUG_WATCH_LOCKON_OFF = 0x68
DEBUG_WATCH_NOAUTOTRACK_OFF = 0x6C
DEBUG_WATCH_INVALIDTARGET_OFF = 0x70
DEBUG_WATCH_CHAIN_CLASS_OFF = 0x74
DEBUG_WATCH_CHAIN_TEAM_OFF = 0x78
DEBUG_WATCH_PARENT_CLASS_OFF = 0x7C
DEBUG_WATCH_PARENT_TEAM_OFF = 0x80
DEBUG_BLOCK_SIZE = 0x84

HOSTILE_CLASS_BALL_BOT = 0x109A
HOSTILE_CLASS_DRONE_BOT = 0x109D
HOSTILE_CLASS_RANGER_TORSO = 0x109E
HOSTILE_CLASS_RANGER_FEET = 0x109F
HOSTILE_CLASS_SHOCK_DROID = 0x1A1B
HOSTILE_CLASS_SIEGE_NODE = 0x1A47
HOSTILE_CLASS_NODE_TURRET = 0x1A63
HOSTILE_CLASS_GATLING_TURRET = 0x1AD6
HOSTILE_CLASS_SHOCK_SPAWNER = 0x1A91

LAST_DEBUG_ADDR = None


def find_subsequence(haystack, needle):
    end = len(haystack) - len(needle) + 1
    for i in range(end):
        if haystack[i:i + len(needle)] == needle:
            return i
    return -1


def enc_lqc2(vf, o, rs):
    return 0xD8000000 | ((rs & 0x1F) << 21) | ((vf & 0x1F) << 16) | (o & 0xFFFF)


def enc_sqc2(vf, o, rs):
    return 0xF8000000 | ((rs & 0x1F) << 21) | ((vf & 0x1F) << 16) | (o & 0xFFFF)


VU_VADD_VF1_VF1_VF2 = 0x4BC20868


def build_pick_homing_target(debug_base):
    """Return a helper fn:

    Args:
      a0 = shooter moby
      a1 = shooter player

    Returns:
      v0 = target moby, or 0 if none found
    """
    F0, F1, F2, F3, F4, F5, F6, F7 = 0, 1, 2, 3, 4, 5, 6, 7
    F12 = 12
    F20, F21, F22, F25 = 20, 21, 22, 25
    AT = 1
    T8, T9 = 24, 25

    player_hi, player_lo = hi_lo(PLAYER_STRUCT_ARRAY_ADDR)
    moby_begin_hi, moby_begin_lo = hi_lo(BEGIN_MOBY_PTR_ADDR)
    moby_end_hi, moby_end_lo = hi_lo(END_MOBY_PTR_ADDR)
    coll_output_hi, coll_output_lo = hi_lo(ADDR_COLL_OUTPUT)
    watch_hi, watch_lo = hi_lo(WATCH_MOBY_PTR)
    debug_hi, debug_lo = hi_lo(debug_base)

    code = []

    # Stack:
    #   [sp+0x00] bestDist2
    #   [sp+0x04] bestTarget
    #   [sp+0x08] bestSource (0 none / 1 player / 2 moby)
    #   [sp+0x0C] trackFirstHostile (1 only for the first hostile candidate
    #              seen in the moby fallback this call)
    #   [sp+0x10] currentIsHostile (1 for the current fallback moby candidate)
    #   [sp+0x14] currentCandidate (preserved across stock jal helpers)
    #   [sp+0x20] currentIsWatched (1 for WATCH_MOBY_PTR)
    #   [sp+0x18] shooterMoby
    #   [sp+0x1C] shooterPlayer
    #   [sp+0x80] stock query point
    #   [sp+0x90] stock query offset
    code.append(enc_addiu(SP, SP, -0xC0))
    code.append(enc_sd(RA, 0xB8, SP))
    code.append(enc_sw(ZERO, 0x04, SP))
    code.append(enc_sw(ZERO, 0x08, SP))
    code.append(enc_sw(ZERO, 0x0C, SP))
    code.append(enc_sw(ZERO, 0x10, SP))
    code.append(enc_sw(ZERO, 0x20, SP))
    code.append(enc_sw(A0, 0x18, SP))
    code.append(enc_sw(A1, 0x1C, SP))
    code.append(enc_lui(AT, TARGET_MAX_DIST2_U32 >> 16))
    code.append(enc_ori(AT, AT, TARGET_MAX_DIST2_U32 & 0xFFFF))
    code.append(enc_mtc1(AT, F25))
    code.append(enc_swc1(F25, 0x00, SP))
    code.append(enc_mtc1(ZERO, F0))                  # 0.0f

    # Debug block: count calls and clear the per-call fields.
    code.append(enc_lui(T9, debug_hi))
    code.append(enc_addiu(T9, T9, debug_lo))
    code.append(enc_lw(T8, DEBUG_PICK_CALLS_OFF, T9))
    code.append(enc_addiu(T8, T8, 1))
    code.append(enc_sw(T8, DEBUG_PICK_CALLS_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_PICK_RESULT_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_PICK_SOURCE_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_PICK_DIST2_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_FIRST_HOSTILE_PTR_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_FIRST_HOSTILE_CLASS_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_FIRST_HOSTILE_STAGE_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_FIRST_HOSTILE_PASS_PTR_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_FIRST_HOSTILE_PASS_CLASS_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_STOCK_COUNT_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_STOCK_LIST0_PTR_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_STOCK_LIST0_CLASS_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_STOCK_LIST1_PTR_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_STOCK_LIST1_CLASS_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_STOCK_COLLOUT_PTR_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_STOCK_COLLOUT_CLASS_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_STAGE_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_GROUP_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_PARENT_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_CHAIN_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_VALIDATOR_PTR_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_VALIDATOR_VAL_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_PCLASS46_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_MODEBITS_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_PLAYER_TEAM_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_TARGET_TEAM_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_LOCKON_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_NOAUTOTRACK_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_INVALIDTARGET_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_CHAIN_CLASS_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_CHAIN_TEAM_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_PARENT_CLASS_OFF, T9))
    code.append(enc_sw(ZERO, DEBUG_WATCH_PARENT_TEAM_OFF, T9))
    code.append(enc_lw(T0, 0x1C, SP))
    player_team_skip_idx = len(code)
    code.append(0)                                   # beq T0, ZERO, .after_player_team
    code.append(enc_nop())
    code.append(enc_lw(T1, 0x2548, T0))
    code.append(enc_sw(T1, DEBUG_PLAYER_TEAM_OFF, T9))
    after_player_team = len(code)

    # --- Probe stock minirocket broadphase exactly ---
    code.append(enc_addiu(A0, SP, 0x80))
    code.append(enc_lui(AT, 0xBF80))                 # -1.0f
    code.append(enc_mtc1(AT, F12))
    code.append(enc_lw(T0, 0x18, SP))
    code.append(enc_jal(ADDR_QUERY_VECTOR_SCALE))
    code.append(enc_addiu(A1, T0, 0xD0))
    code.append(enc_lw(T0, 0x18, SP))
    code.append(enc_lqc2(1, 0x80, SP))
    code.append(enc_lqc2(2, 0x10, T0))
    code.append(VU_VADD_VF1_VF1_VF2)
    code.append(enc_lui(AT, 0x3E8C))                 # 0.275f
    code.append(enc_ori(AT, AT, 0xCCCD))
    code.append(enc_mtc1(AT, F12))
    code.append(enc_sqc2(1, 0x80, SP))
    code.append(enc_addiu(A0, SP, 0x90))
    code.append(enc_lw(T0, 0x18, SP))
    code.append(enc_jal(ADDR_QUERY_VECTOR_SCALE))
    code.append(enc_addiu(A1, T0, 0xC0))
    code.append(enc_lqc2(1, 0x80, SP))
    code.append(enc_lqc2(2, 0x90, SP))
    code.append(VU_VADD_VF1_VF1_VF2)
    code.append(enc_lui(AT, 0x3F80))                 # 1.0f
    code.append(enc_mtc1(AT, F12))
    code.append(enc_sqc2(1, 0x80, SP))
    code.append(enc_addiu(A0, SP, 0x80))
    code.append(enc_lw(T0, 0x1C, SP))
    stock_probe_no_player_idx = len(code)
    code.append(0)                                   # beq T0, ZERO, .stock_probe_no_player
    code.append(enc_nop())
    code.append(enc_lw(A2, PLAYER_MOBY_OFF, T0))
    stock_probe_after_filter_jump_idx = len(code)
    code.append(0)                                   # b .stock_probe_after_filter
    code.append(enc_nop())
    stock_probe_no_player = len(code)
    code.append(enc_daddu(A2, ZERO, ZERO))
    stock_probe_after_filter = len(code)
    code.append(enc_addiu(A1, ZERO, 1))
    code.append(enc_daddu(A3, ZERO, ZERO))
    code.append(enc_lui(AT, 0x3F80))                 # 1.0f
    code.append(enc_mtc1(AT, F12))
    code.append(enc_jal(ADDR_MOBY_CONE_QUERY))
    code.append(enc_nop())

    code.append(enc_lui(T9, debug_hi))
    code.append(enc_addiu(T9, T9, debug_lo))
    code.append(enc_sw(V0, DEBUG_STOCK_COUNT_OFF, T9))
    code.append(enc_lui(T0, SCAN_LIST_LUI))
    code.append(enc_lw(T1, SCAN_LIST_OFF & 0xFFFF, T0))
    code.append(enc_sw(T1, DEBUG_STOCK_LIST0_PTR_OFF, T9))
    stock_probe_list0_null_idx = len(code)
    code.append(0)                                   # beq T1, ZERO, .stock_probe_after_list0
    code.append(enc_nop())
    code.append(enc_lhu(T2, 0xAA, T1))
    code.append(enc_sw(T2, DEBUG_STOCK_LIST0_CLASS_OFF, T9))
    stock_probe_after_list0 = len(code)
    code.append(enc_lw(T1, (SCAN_LIST_OFF + 4) & 0xFFFF, T0))
    code.append(enc_sw(T1, DEBUG_STOCK_LIST1_PTR_OFF, T9))
    stock_probe_list1_null_idx = len(code)
    code.append(0)                                   # beq T1, ZERO, .stock_probe_after_list1
    code.append(enc_nop())
    code.append(enc_lhu(T2, 0xAA, T1))
    code.append(enc_sw(T2, DEBUG_STOCK_LIST1_CLASS_OFF, T9))
    stock_probe_after_list1 = len(code)
    code.append(enc_lui(T0, coll_output_hi))
    code.append(enc_addiu(T0, T0, coll_output_lo))
    code.append(enc_lw(T1, 0x18, T0))
    code.append(enc_sw(T1, DEBUG_STOCK_COLLOUT_PTR_OFF, T9))
    stock_probe_coll_null_idx = len(code)
    code.append(0)                                   # beq T1, ZERO, .stock_probe_after_coll
    code.append(enc_nop())
    code.append(enc_lhu(T2, 0xAA, T1))
    code.append(enc_sw(T2, DEBUG_STOCK_COLLOUT_CLASS_OFF, T9))
    stock_probe_after_coll = len(code)

    # Reload preserved shooter state after the stock probe clobbers caller-saved regs.
    code.append(enc_lw(T7, 0x18, SP))
    code.append(enc_lw(T6, 0x1C, SP))

    # Cache shooter pos in FPU regs.
    code.append(enc_lwc1(F20, 0x10, T7))             # shooter x
    code.append(enc_lwc1(F21, 0x14, T7))             # shooter y
    code.append(enc_lwc1(F22, 0x18, T7))             # shooter z

    # --- A1: scan player table ---
    code.append(enc_lui(T0, player_hi))
    code.append(enc_addiu(T0, T0, player_lo))        # cur = player table
    code.append(enc_addiu(T1, T0, GAME_MAX_PLAYERS * 4))  # end

    player_loop = len(code)
    code.append(enc_slt(T2, T0, T1))
    player_done_idx = len(code)
    code.append(0)                                   # beq T2, ZERO, .after_players
    code.append(enc_nop())

    code.append(enc_lw(T3, 0x00, T0))                # player*
    code.append(enc_addiu(T0, T0, 4))
    player_skip_null_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .player_loop
    code.append(enc_nop())
    player_skip_self_idx = len(code)
    code.append(0)                                   # beq T3, T6, .player_loop
    code.append(enc_nop())

    code.append(enc_lw(T4, PLAYER_VEHICLE_OFF, T3))
    player_no_vehicle_idx = len(code)
    code.append(0)                                   # beq T4, ZERO, .player_use_moby
    code.append(enc_nop())
    code.append(enc_lw(V1, VEHICLE_MOBY_OFF, T4))
    player_have_target_idx = len(code)
    code.append(0)                                   # b .player_got_target
    code.append(enc_nop())

    player_use_moby = len(code)
    code.append(enc_lw(V1, PLAYER_MOBY_OFF, T3))

    player_got_target = len(code)
    player_target_null_idx = len(code)
    code.append(0)                                   # beq V1, ZERO, .player_loop
    code.append(enc_nop())
    player_target_self_moby_idx = len(code)
    code.append(0)                                   # beq V1, T7, .player_loop
    code.append(enc_nop())

    code.append(enc_lbu(T4, 0x31, V1))               # drawn
    player_hidden_idx = len(code)
    code.append(0)                                   # beq T4, ZERO, .player_loop
    code.append(enc_nop())
    code.append(enc_lhu(T4, 0x32, V1))               # drawDist
    code.append(enc_slt(T5, ZERO, T4))               # drawDist > 0
    player_drawdist_idx = len(code)
    code.append(0)                                   # beq T5, ZERO, .player_loop
    code.append(enc_nop())

    code.append(enc_lbu(T4, 0x20, V1))               # state
    code.append(enc_addiu(AT, ZERO, 0x00FE))
    player_state_fe_idx = len(code)
    code.append(0)                                   # beq T4, AT, .player_loop
    code.append(enc_nop())
    code.append(enc_addiu(AT, ZERO, 0x00FD))
    player_state_fd_idx = len(code)
    code.append(0)                                   # beq T4, AT, .player_loop
    code.append(enc_nop())

    code.append(enc_lhu(T4, 0xAA, V1))               # oClass
    code.append(enc_addiu(AT, ZERO, EXCLUDE_CLASS_PAD))
    player_pad_idx = len(code)
    code.append(0)                                   # beq T4, AT, .player_loop
    code.append(enc_nop())
    code.append(enc_addiu(AT, ZERO, EXCLUDE_CLASS_ROCKET))
    player_rocket_idx = len(code)
    code.append(0)                                   # beq T4, AT, .player_loop
    code.append(enc_nop())

    code.append(enc_lw(T4, 0x68, V1))                # pVar
    player_pvar_idx = len(code)
    code.append(0)                                   # beq T4, ZERO, .player_loop
    code.append(enc_nop())
    code.append(enc_lhu(T5, 0x34, V1))               # modeBits
    code.append(0x30000000 | (T5 << 21) | (T5 << 16) | 0x0020)  # andi T5, T5, 0x20
    player_mode_idx = len(code)
    code.append(0)                                   # beq T5, ZERO, .player_loop
    code.append(enc_nop())
    code.append(enc_lw(T4, 0x00, T4))                # validator ptr = *(pVar+0)
    player_validator_ptr_idx = len(code)
    code.append(0)                                   # beq T4, ZERO, .player_loop
    code.append(enc_nop())
    code.append(enc_lwc1(F6, 0x00, T4))              # validator[0]
    code.append(enc_c_lt_s(F0, F6))                  # > 0
    player_validator_val_idx = len(code)
    code.append(0)                                   # bc1f .player_loop
    code.append(enc_nop())
    code.append(enc_lw(T4, 0x24, V1))                # pClass
    player_no_class_idx = len(code)
    code.append(0)                                   # beq T4, ZERO, .player_score
    code.append(enc_nop())
    code.append(enc_lbu(T5, 0x46, T4))
    code.append(enc_addiu(AT, ZERO, 5))
    player_class5_idx = len(code)
    code.append(0)                                   # beq T5, AT, .player_loop
    code.append(enc_nop())

    # Score candidate V1.
    player_score = len(code)
    code.append(enc_lwc1(F1, 0x10, V1))              # dx
    code.append(enc_sub_s(F1, F1, F20))
    code.append(enc_lwc1(F2, 0x14, V1))              # dy
    code.append(enc_sub_s(F2, F2, F21))
    code.append(enc_lwc1(F3, 0x18, V1))              # dz
    code.append(enc_sub_s(F3, F3, F22))
    code.append(enc_mul_s(F4, F1, F1))
    code.append(enc_mul_s(F5, F2, F2))
    code.append(enc_add_s(F4, F4, F5))
    code.append(enc_mul_s(F5, F3, F3))
    code.append(enc_add_s(F5, F4, F5))               # dist2
    code.append(enc_c_lt_s(F25, F5))                 # maxDist2 < dist2?
    player_range_skip_idx = len(code)
    code.append(0)                                   # bc1t .player_candidate_done
    code.append(enc_nop())
    code.append(enc_lwc1(F7, 0x00, SP))              # bestDist2
    code.append(enc_c_lt_s(F5, F7))                  # dist2 < bestDist2
    player_best_skip_idx = len(code)
    code.append(0)                                   # bc1f .player_candidate_done
    code.append(enc_nop())
    code.append(enc_swc1(F5, 0x00, SP))
    code.append(enc_sw(V1, 0x04, SP))
    code.append(enc_addiu(T8, ZERO, 1))
    code.append(enc_sw(T8, 0x08, SP))

    player_candidate_done = len(code)
    code.append(enc_beq(ZERO, ZERO, player_loop - (len(code) + 1)))
    code.append(enc_nop())

    after_players = len(code)
    code[player_done_idx] = enc_beq(T2, ZERO, after_players - (player_done_idx + 1))
    code[player_skip_null_idx] = enc_beq(T3, ZERO, player_loop - (player_skip_null_idx + 1))
    code[player_skip_self_idx] = enc_beq(T3, T6, player_loop - (player_skip_self_idx + 1))
    code[player_no_vehicle_idx] = enc_beq(T4, ZERO, player_use_moby - (player_no_vehicle_idx + 1))
    code[player_have_target_idx] = enc_beq(ZERO, ZERO, player_got_target - (player_have_target_idx + 1))
    code[player_target_null_idx] = enc_beq(V1, ZERO, player_loop - (player_target_null_idx + 1))
    code[player_target_self_moby_idx] = enc_beq(V1, T7, player_loop - (player_target_self_moby_idx + 1))
    code[player_hidden_idx] = enc_beq(T4, ZERO, player_loop - (player_hidden_idx + 1))
    code[player_drawdist_idx] = enc_beq(T5, ZERO, player_loop - (player_drawdist_idx + 1))
    code[player_state_fe_idx] = enc_beq(T4, AT, player_loop - (player_state_fe_idx + 1))
    code[player_state_fd_idx] = enc_beq(T4, AT, player_loop - (player_state_fd_idx + 1))
    code[player_pad_idx] = enc_beq(T4, AT, player_loop - (player_pad_idx + 1))
    code[player_rocket_idx] = enc_beq(T4, AT, player_loop - (player_rocket_idx + 1))
    code[player_pvar_idx] = enc_beq(T4, ZERO, player_loop - (player_pvar_idx + 1))
    code[player_mode_idx] = enc_beq(T5, ZERO, player_loop - (player_mode_idx + 1))
    code[player_validator_ptr_idx] = enc_beq(T4, ZERO, player_loop - (player_validator_ptr_idx + 1))
    code[player_validator_val_idx] = enc_bc1f(player_loop - (player_validator_val_idx + 1))
    code[player_no_class_idx] = enc_beq(T4, ZERO, player_score - (player_no_class_idx + 1))
    code[player_class5_idx] = enc_beq(T5, AT, player_loop - (player_class5_idx + 1))
    code[player_range_skip_idx] = enc_bc1t(player_candidate_done - (player_range_skip_idx + 1))
    code[player_best_skip_idx] = enc_bc1f(player_candidate_done - (player_best_skip_idx + 1))

    # If A1 found anything, return it now.
    code.append(enc_lw(V0, 0x04, SP))
    player_found_idx = len(code)
    code.append(0)                                   # bne V0, ZERO, .done
    code.append(enc_nop())

    # --- A: fallback direct moby walk ---
    code.append(enc_lui(T0, moby_begin_hi))
    code.append(enc_lw(T0, moby_begin_lo, T0))       # cur = *BEGIN_MOBY_PTR
    code.append(enc_lui(T1, moby_end_hi))
    code.append(enc_lw(T1, moby_end_lo, T1))         # end = *END_MOBY_PTR

    moby_loop = len(code)
    code.append(enc_slt(T2, T0, T1))
    moby_done_idx = len(code)
    code.append(0)                                   # beq T2, ZERO, .done
    code.append(enc_nop())

    code.append(enc_daddu(V1, T0, ZERO))             # candidate = cur
    code.append(enc_addiu(T0, T0, MOBY_ENTRY_SIZE))  # cur += 0x100
    moby_skip_self_idx = len(code)
    code.append(0)                                   # beq V1, T7, .moby_loop
    code.append(enc_nop())

    code.append(enc_sw(ZERO, 0x0C, SP))
    code.append(enc_sw(ZERO, 0x10, SP))
    code.append(enc_sw(ZERO, 0x20, SP))
    code.append(enc_lui(T3, watch_hi))
    code.append(enc_addiu(T3, T3, watch_lo))
    moby_watch_match_idx = len(code)
    code.append(0)                                   # beq V1, T3, .moby_mark_watch
    code.append(enc_nop())
    moby_skip_mark_watch_idx = len(code)
    code.append(0)                                   # b .moby_after_watch
    code.append(enc_nop())
    moby_mark_watch = len(code)
    code.append(enc_addiu(T8, ZERO, 1))
    code.append(enc_sw(T8, 0x20, SP))
    code.append(enc_sw(T8, DEBUG_WATCH_STAGE_OFF, T9))
    code.append(enc_lbu(T8, 0x21, V1))
    code.append(enc_sw(T8, DEBUG_WATCH_GROUP_OFF, T9))
    code.append(enc_lw(T8, 0xB8, V1))
    code.append(enc_sw(T8, DEBUG_WATCH_PARENT_OFF, T9))
    code.append(enc_lw(T8, 0x28, V1))
    code.append(enc_sw(T8, DEBUG_WATCH_CHAIN_OFF, T9))
    code.append(enc_lhu(T8, 0x34, V1))
    code.append(enc_sw(T8, DEBUG_WATCH_MODEBITS_OFF, T9))
    code.append(enc_lw(T8, 0x28, V1))
    moby_watch_chain_null_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_after_watch_chain
    code.append(enc_nop())
    code.append(enc_lhu(T3, 0xAA, T8))
    code.append(enc_sw(T3, DEBUG_WATCH_CHAIN_CLASS_OFF, T9))
    code.append(enc_sw(V1, 0x14, SP))
    code.append(enc_jal(ADDR_TARGET_VALIDATOR))
    code.append(enc_daddu(A0, T8, ZERO))
    code.append(enc_lw(V1, 0x14, SP))
    code.append(enc_lui(T9, debug_hi))
    code.append(enc_addiu(T9, T9, debug_lo))
    moby_watch_chain_team_null_idx = len(code)
    code.append(0)                                   # beq V0, ZERO, .moby_after_watch_chain
    code.append(enc_nop())
    code.append(enc_lhu(T3, 0x2E, V0))
    code.append(enc_sw(T3, DEBUG_WATCH_CHAIN_TEAM_OFF, T9))
    moby_after_watch_chain = len(code)
    code.append(enc_lw(T8, 0xB8, V1))
    moby_watch_parent_null_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_after_watch_parent
    code.append(enc_nop())
    code.append(enc_lhu(T3, 0xAA, T8))
    code.append(enc_sw(T3, DEBUG_WATCH_PARENT_CLASS_OFF, T9))
    code.append(enc_sw(V1, 0x14, SP))
    code.append(enc_jal(ADDR_TARGET_VALIDATOR))
    code.append(enc_daddu(A0, T8, ZERO))
    code.append(enc_lw(V1, 0x14, SP))
    code.append(enc_lui(T9, debug_hi))
    code.append(enc_addiu(T9, T9, debug_lo))
    moby_watch_parent_team_null_idx = len(code)
    code.append(0)                                   # beq V0, ZERO, .moby_after_watch_parent
    code.append(enc_nop())
    code.append(enc_lhu(T3, 0x2E, V0))
    code.append(enc_sw(T3, DEBUG_WATCH_PARENT_TEAM_OFF, T9))
    moby_after_watch_parent = len(code)
    moby_after_watch = len(code)
    code.append(enc_lhu(T4, 0xAA, V1))               # oClass
    code.append(enc_addiu(T5, ZERO, HOSTILE_CLASS_BALL_BOT))
    moby_hostile_ball_idx = len(code)
    code.append(0)                                   # beq T4, T5, .moby_mark_hostile
    code.append(enc_nop())
    code.append(enc_addiu(T5, ZERO, HOSTILE_CLASS_DRONE_BOT))
    moby_hostile_drone_idx = len(code)
    code.append(0)                                   # beq T4, T5, .moby_mark_hostile
    code.append(enc_nop())
    code.append(enc_addiu(T5, ZERO, HOSTILE_CLASS_RANGER_TORSO))
    moby_hostile_ranger_torso_idx = len(code)
    code.append(0)                                   # beq T4, T5, .moby_mark_hostile
    code.append(enc_nop())
    code.append(enc_addiu(T5, ZERO, HOSTILE_CLASS_RANGER_FEET))
    moby_hostile_ranger_feet_idx = len(code)
    code.append(0)                                   # beq T4, T5, .moby_mark_hostile
    code.append(enc_nop())
    code.append(enc_addiu(T5, ZERO, HOSTILE_CLASS_SHOCK_DROID))
    moby_hostile_shock_idx = len(code)
    code.append(0)                                   # beq T4, T5, .moby_mark_hostile
    code.append(enc_nop())
    code.append(enc_addiu(T5, ZERO, HOSTILE_CLASS_SIEGE_NODE))
    moby_hostile_siege_idx = len(code)
    code.append(0)                                   # beq T4, T5, .moby_mark_hostile
    code.append(enc_nop())
    code.append(enc_addiu(T5, ZERO, HOSTILE_CLASS_NODE_TURRET))
    moby_hostile_node_idx = len(code)
    code.append(0)                                   # beq T4, T5, .moby_mark_hostile
    code.append(enc_nop())
    code.append(enc_addiu(T5, ZERO, HOSTILE_CLASS_GATLING_TURRET))
    moby_hostile_gatling_idx = len(code)
    code.append(0)                                   # beq T4, T5, .moby_mark_hostile
    code.append(enc_nop())
    code.append(enc_addiu(T5, ZERO, HOSTILE_CLASS_SHOCK_SPAWNER))
    moby_hostile_spawner_idx = len(code)
    code.append(0)                                   # beq T4, T5, .moby_mark_hostile
    code.append(enc_nop())
    moby_skip_mark_hostile_idx = len(code)
    code.append(0)                                   # b .moby_after_hostile_check
    code.append(enc_nop())
    moby_mark_hostile = len(code)
    code.append(enc_addiu(T8, ZERO, 1))
    code.append(enc_sw(T8, 0x10, SP))
    code.append(enc_sw(T8, 0x0C, SP))
    code.append(enc_sw(V1, DEBUG_FIRST_HOSTILE_PTR_OFF, T9))
    code.append(enc_sw(T4, DEBUG_FIRST_HOSTILE_CLASS_OFF, T9))
    code.append(enc_sw(T8, DEBUG_FIRST_HOSTILE_STAGE_OFF, T9))
    moby_after_hostile_check = len(code)

    code.append(enc_lw(T8, 0x0C, SP))
    moby_stage2_skip_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_after_stage2
    code.append(enc_nop())
    code.append(enc_addiu(T8, ZERO, 2))
    code.append(enc_sw(T8, DEBUG_FIRST_HOSTILE_STAGE_OFF, T9))
    code.append(enc_lw(T3, 0x20, SP))
    moby_watch_stage2_skip_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .moby_after_watch_stage2
    code.append(enc_nop())
    code.append(enc_sw(T8, DEBUG_WATCH_STAGE_OFF, T9))
    moby_after_watch_stage2 = len(code)
    code.append(enc_sw(V1, DEBUG_FIRST_HOSTILE_PTR_OFF, T9))
    code.append(enc_lhu(T5, 0xAA, V1))
    code.append(enc_sw(T5, DEBUG_FIRST_HOSTILE_CLASS_OFF, T9))
    moby_after_stage2 = len(code)
    code.append(enc_lbu(T3, 0x31, V1))               # drawn
    moby_skip_hidden_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .moby_loop
    code.append(enc_nop())
    code.append(enc_lhu(T4, 0x32, V1))               # drawDist
    code.append(enc_slt(T5, ZERO, T4))               # drawDist > 0
    moby_skip_drawdist_idx = len(code)
    code.append(0)                                   # beq T5, ZERO, .moby_loop
    code.append(enc_nop())
    code.append(enc_lw(T8, 0x0C, SP))
    moby_stage3_skip_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_after_stage3
    code.append(enc_nop())
    code.append(enc_addiu(T8, ZERO, 3))
    code.append(enc_sw(T8, DEBUG_FIRST_HOSTILE_STAGE_OFF, T9))
    code.append(enc_lw(T3, 0x20, SP))
    moby_watch_stage3_skip_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .moby_after_watch_stage3
    code.append(enc_nop())
    code.append(enc_sw(T8, DEBUG_WATCH_STAGE_OFF, T9))
    moby_after_watch_stage3 = len(code)
    code.append(enc_sw(V1, DEBUG_FIRST_HOSTILE_PTR_OFF, T9))
    code.append(enc_lhu(T5, 0xAA, V1))
    code.append(enc_sw(T5, DEBUG_FIRST_HOSTILE_CLASS_OFF, T9))
    moby_after_stage3 = len(code)

    code.append(enc_lbu(T4, 0x20, V1))               # state
    code.append(enc_addiu(AT, ZERO, 0x00FE))
    moby_skip_fe_idx = len(code)
    code.append(0)                                   # beq T4, AT, .moby_loop
    code.append(enc_nop())
    code.append(enc_addiu(AT, ZERO, 0x00FD))
    moby_skip_fd_idx = len(code)
    code.append(0)                                   # beq T4, AT, .moby_loop
    code.append(enc_nop())

    code.append(enc_lhu(T4, 0xAA, V1))               # oClass
    code.append(enc_addiu(AT, ZERO, EXCLUDE_CLASS_PAD))
    moby_skip_pad_idx = len(code)
    code.append(0)                                   # beq T4, AT, .moby_loop
    code.append(enc_nop())
    code.append(enc_addiu(AT, ZERO, EXCLUDE_CLASS_ROCKET))
    moby_skip_rocket_idx = len(code)
    code.append(0)                                   # beq T4, AT, .moby_loop
    code.append(enc_nop())
    code.append(enc_lw(T8, 0x0C, SP))
    moby_stage4_skip_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_after_stage4
    code.append(enc_nop())
    code.append(enc_addiu(T8, ZERO, 4))
    code.append(enc_sw(T8, DEBUG_FIRST_HOSTILE_STAGE_OFF, T9))
    code.append(enc_lw(T3, 0x20, SP))
    moby_watch_stage4_skip_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .moby_after_watch_stage4
    code.append(enc_nop())
    code.append(enc_sw(T8, DEBUG_WATCH_STAGE_OFF, T9))
    moby_after_watch_stage4 = len(code)
    code.append(enc_sw(V1, DEBUG_FIRST_HOSTILE_PTR_OFF, T9))
    code.append(enc_lhu(T5, 0xAA, V1))
    code.append(enc_sw(T5, DEBUG_FIRST_HOSTILE_CLASS_OFF, T9))
    moby_after_stage4 = len(code)
    code.append(enc_sw(V1, 0x14, SP))
    code.append(enc_jal(ADDR_TARGET_VALIDATOR))
    code.append(enc_daddu(A0, V1, ZERO))
    moby_skip_validator_null_idx = len(code)
    code.append(0)                                   # beq V0, ZERO, .moby_loop
    code.append(enc_nop())
    code.append(enc_daddu(T4, V0, ZERO))             # validator ptr
    code.append(enc_lw(V1, 0x14, SP))
    code.append(enc_lui(T9, debug_hi))
    code.append(enc_addiu(T9, T9, debug_lo))
    code.append(enc_lw(T8, 0x0C, SP))
    moby_stage5_skip_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_after_stage5
    code.append(enc_nop())
    code.append(enc_addiu(T8, ZERO, 5))
    code.append(enc_sw(T8, DEBUG_FIRST_HOSTILE_STAGE_OFF, T9))
    code.append(enc_lw(T3, 0x20, SP))
    moby_watch_stage5_skip_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .moby_after_watch_stage5
    code.append(enc_nop())
    code.append(enc_sw(T8, DEBUG_WATCH_STAGE_OFF, T9))
    moby_after_watch_stage5 = len(code)
    code.append(enc_sw(V1, DEBUG_FIRST_HOSTILE_PTR_OFF, T9))
    code.append(enc_lhu(T5, 0xAA, V1))
    code.append(enc_sw(T5, DEBUG_FIRST_HOSTILE_CLASS_OFF, T9))
    moby_after_stage5 = len(code)
    code.append(enc_lwc1(F6, 0x00, T4))              # validator[0]
    code.append(enc_lw(T3, 0x20, SP))
    moby_watch_validator_skip_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .moby_after_watch_validator
    code.append(enc_nop())
    code.append(enc_sw(T4, DEBUG_WATCH_VALIDATOR_PTR_OFF, T9))
    code.append(enc_lw(T3, 0x00, T4))
    code.append(enc_sw(T3, DEBUG_WATCH_VALIDATOR_VAL_OFF, T9))
    code.append(enc_lhu(T3, 0x2E, T4))
    code.append(enc_sw(T3, DEBUG_WATCH_TARGET_TEAM_OFF, T9))
    code.append(enc_lbu(T3, 0x35, T4))
    code.append(enc_sw(T3, DEBUG_WATCH_LOCKON_OFF, T9))
    code.append(enc_lbu(T3, 0x38, T4))
    code.append(enc_sw(T3, DEBUG_WATCH_NOAUTOTRACK_OFF, T9))
    code.append(enc_lbu(T3, 0x47, T4))
    code.append(enc_sw(T3, DEBUG_WATCH_INVALIDTARGET_OFF, T9))
    moby_after_watch_validator = len(code)
    code.append(enc_c_lt_s(F0, F6))                  # > 0
    moby_validator_positive_idx = len(code)
    code.append(0)                                   # bc1t .moby_validator_ok
    code.append(enc_nop())
    code.append(enc_sw(V1, 0x14, SP))
    code.append(enc_jal(ADDR_CANDIDATE_CLASS9_FALLBACK))
    code.append(enc_daddu(A0, V1, ZERO))
    moby_skip_validator_val_idx = len(code)
    code.append(0)                                   # beq V0, ZERO, .moby_loop
    code.append(enc_nop())
    code.append(enc_lw(V1, 0x14, SP))
    moby_validator_ok = len(code)
    code.append(enc_lui(T9, debug_hi))
    code.append(enc_addiu(T9, T9, debug_lo))
    code.append(enc_lw(T8, 0x0C, SP))
    moby_stage6_skip_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_after_stage6
    code.append(enc_nop())
    code.append(enc_addiu(T8, ZERO, 6))
    code.append(enc_sw(T8, DEBUG_FIRST_HOSTILE_STAGE_OFF, T9))
    code.append(enc_lw(T3, 0x20, SP))
    moby_watch_stage6_skip_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .moby_after_watch_stage6
    code.append(enc_nop())
    code.append(enc_sw(T8, DEBUG_WATCH_STAGE_OFF, T9))
    moby_after_watch_stage6 = len(code)
    code.append(enc_sw(V1, DEBUG_FIRST_HOSTILE_PTR_OFF, T9))
    code.append(enc_lhu(T5, 0xAA, V1))
    code.append(enc_sw(T5, DEBUG_FIRST_HOSTILE_CLASS_OFF, T9))
    moby_after_stage6 = len(code)
    code.append(enc_lw(T4, 0x24, V1))                # pClass
    moby_no_class_idx = len(code)
    code.append(0)                                   # beq T4, ZERO, .moby_score
    code.append(enc_nop())
    code.append(enc_lbu(T5, 0x46, T4))
    code.append(enc_lw(T3, 0x20, SP))
    moby_watch_pclass_skip_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .moby_after_watch_pclass
    code.append(enc_nop())
    code.append(enc_sw(T5, DEBUG_WATCH_PCLASS46_OFF, T9))
    moby_after_watch_pclass = len(code)
    code.append(enc_addiu(AT, ZERO, 5))
    moby_class5_not5_idx = len(code)
    code.append(0)                                   # bne T5, AT, .moby_after_class5
    code.append(enc_nop())
    code.append(enc_lw(T8, 0x10, SP))               # currentIsHostile
    moby_class5_hostile_allow_idx = len(code)
    code.append(0)                                   # bne T8, ZERO, .moby_after_class5
    code.append(enc_nop())
    moby_skip_class5_idx = len(code)
    code.append(0)                                   # b .moby_loop
    code.append(enc_nop())
    moby_after_class5 = len(code)
    code.append(enc_lw(T8, 0x0C, SP))
    moby_stage7_skip_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_after_stage7
    code.append(enc_nop())
    code.append(enc_addiu(T8, ZERO, 7))
    code.append(enc_sw(T8, DEBUG_FIRST_HOSTILE_STAGE_OFF, T9))
    code.append(enc_lw(T3, 0x20, SP))
    moby_watch_stage7_skip_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .moby_after_watch_stage7
    code.append(enc_nop())
    code.append(enc_sw(T8, DEBUG_WATCH_STAGE_OFF, T9))
    moby_after_watch_stage7 = len(code)
    code.append(enc_sw(V1, DEBUG_FIRST_HOSTILE_PTR_OFF, T9))
    code.append(enc_lhu(T5, 0xAA, V1))
    code.append(enc_sw(T5, DEBUG_FIRST_HOSTILE_CLASS_OFF, T9))
    moby_after_stage7 = len(code)

    # Score candidate V1.
    moby_score = len(code)
    code.append(enc_lw(T8, 0x0C, SP))
    moby_stage8_skip_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_after_stage8
    code.append(enc_nop())
    code.append(enc_addiu(T8, ZERO, 8))
    code.append(enc_sw(T8, DEBUG_FIRST_HOSTILE_STAGE_OFF, T9))
    code.append(enc_lw(T3, 0x20, SP))
    moby_watch_stage8_skip_idx = len(code)
    code.append(0)                                   # beq T3, ZERO, .moby_after_watch_stage8
    code.append(enc_nop())
    code.append(enc_sw(T8, DEBUG_WATCH_STAGE_OFF, T9))
    moby_after_watch_stage8 = len(code)
    code.append(enc_sw(V1, DEBUG_FIRST_HOSTILE_PTR_OFF, T9))
    code.append(enc_lhu(T5, 0xAA, V1))
    code.append(enc_sw(T5, DEBUG_FIRST_HOSTILE_CLASS_OFF, T9))
    moby_after_stage8 = len(code)
    code.append(enc_lw(T8, 0x10, SP))
    moby_pass_nonhostile_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_after_pass_record
    code.append(enc_nop())
    code.append(enc_lw(T8, DEBUG_FIRST_HOSTILE_PASS_PTR_OFF, T9))
    moby_pass_already_idx = len(code)
    code.append(0)                                   # bne T8, ZERO, .moby_after_pass_record
    code.append(enc_nop())
    code.append(enc_sw(V1, DEBUG_FIRST_HOSTILE_PASS_PTR_OFF, T9))
    code.append(enc_lhu(T8, 0xAA, V1))
    code.append(enc_sw(T8, DEBUG_FIRST_HOSTILE_PASS_CLASS_OFF, T9))
    moby_after_pass_record = len(code)
    code.append(enc_lwc1(F1, 0x10, V1))              # dx
    code.append(enc_sub_s(F1, F1, F20))
    code.append(enc_lwc1(F2, 0x14, V1))              # dy
    code.append(enc_sub_s(F2, F2, F21))
    code.append(enc_lwc1(F3, 0x18, V1))              # dz
    code.append(enc_sub_s(F3, F3, F22))
    code.append(enc_mul_s(F4, F1, F1))
    code.append(enc_mul_s(F5, F2, F2))
    code.append(enc_add_s(F4, F4, F5))
    code.append(enc_mul_s(F5, F3, F3))
    code.append(enc_add_s(F5, F4, F5))               # dist2
    code.append(enc_c_lt_s(F25, F5))                 # maxDist2 < dist2?
    moby_range_skip_idx = len(code)
    code.append(0)                                   # bc1t .moby_candidate_done
    code.append(enc_nop())
    code.append(enc_lw(T8, 0x10, SP))               # currentIsHostile
    moby_nonhostile_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_nonhostile
    code.append(enc_nop())
    code.append(enc_lw(T5, 0x08, SP))               # bestSource
    code.append(enc_addiu(AT, ZERO, 3))
    moby_hostile_compare_idx = len(code)
    code.append(0)                                   # beq T5, AT, .moby_hostile_compare
    code.append(enc_nop())
    code.append(enc_swc1(F5, 0x00, SP))             # first hostile beats any generic fallback
    code.append(enc_sw(V1, 0x04, SP))
    code.append(enc_addiu(T8, ZERO, 3))
    code.append(enc_sw(T8, 0x08, SP))
    moby_accept_hostile_idx = len(code)
    code.append(0)                                   # b .moby_candidate_done
    code.append(enc_nop())
    moby_nonhostile = len(code)
    code.append(enc_lw(T5, 0x08, SP))               # bestSource
    code.append(enc_addiu(AT, ZERO, 3))
    moby_nonhostile_skip_idx = len(code)
    code.append(0)                                   # beq T5, AT, .moby_candidate_done
    code.append(enc_nop())
    moby_compare_distance = len(code)
    code.append(enc_lwc1(F7, 0x00, SP))              # bestDist2
    code.append(enc_c_lt_s(F5, F7))                  # dist2 < bestDist2
    moby_best_skip_idx = len(code)
    code.append(0)                                   # bc1f .moby_candidate_done
    code.append(enc_nop())
    code.append(enc_lw(T8, 0x10, SP))
    moby_generic_source_idx = len(code)
    code.append(0)                                   # beq T8, ZERO, .moby_store_generic
    code.append(enc_nop())
    code.append(enc_swc1(F5, 0x00, SP))
    code.append(enc_sw(V1, 0x04, SP))
    code.append(enc_addiu(T8, ZERO, 3))
    code.append(enc_sw(T8, 0x08, SP))
    moby_accept_hostile2_idx = len(code)
    code.append(0)                                   # b .moby_candidate_done
    code.append(enc_nop())
    moby_store_generic = len(code)
    code.append(enc_swc1(F5, 0x00, SP))
    code.append(enc_sw(V1, 0x04, SP))
    code.append(enc_addiu(T8, ZERO, 2))
    code.append(enc_sw(T8, 0x08, SP))

    moby_candidate_done = len(code)
    code.append(enc_beq(ZERO, ZERO, moby_loop - (len(code) + 1)))
    code.append(enc_nop())

    done = len(code)
    code[player_team_skip_idx] = enc_beq(T0, ZERO, after_player_team - (player_team_skip_idx + 1))
    code[stock_probe_no_player_idx] = enc_beq(T0, ZERO, stock_probe_no_player - (stock_probe_no_player_idx + 1))
    code[stock_probe_after_filter_jump_idx] = enc_beq(ZERO, ZERO, stock_probe_after_filter - (stock_probe_after_filter_jump_idx + 1))
    code[stock_probe_list0_null_idx] = enc_beq(T1, ZERO, stock_probe_after_list0 - (stock_probe_list0_null_idx + 1))
    code[stock_probe_list1_null_idx] = enc_beq(T1, ZERO, stock_probe_after_list1 - (stock_probe_list1_null_idx + 1))
    code[stock_probe_coll_null_idx] = enc_beq(T1, ZERO, stock_probe_after_coll - (stock_probe_coll_null_idx + 1))
    code[moby_watch_match_idx] = enc_beq(V1, T3, moby_mark_watch - (moby_watch_match_idx + 1))
    code[moby_skip_mark_watch_idx] = enc_beq(ZERO, ZERO, moby_after_watch - (moby_skip_mark_watch_idx + 1))
    code[moby_hostile_ball_idx] = enc_beq(T4, T5, moby_mark_hostile - (moby_hostile_ball_idx + 1))
    code[moby_hostile_drone_idx] = enc_beq(T4, T5, moby_mark_hostile - (moby_hostile_drone_idx + 1))
    code[moby_hostile_ranger_torso_idx] = enc_beq(T4, T5, moby_mark_hostile - (moby_hostile_ranger_torso_idx + 1))
    code[moby_hostile_ranger_feet_idx] = enc_beq(T4, T5, moby_mark_hostile - (moby_hostile_ranger_feet_idx + 1))
    code[moby_hostile_shock_idx] = enc_beq(T4, T5, moby_mark_hostile - (moby_hostile_shock_idx + 1))
    code[moby_hostile_siege_idx] = enc_beq(T4, T5, moby_mark_hostile - (moby_hostile_siege_idx + 1))
    code[moby_hostile_node_idx] = enc_beq(T4, T5, moby_mark_hostile - (moby_hostile_node_idx + 1))
    code[moby_hostile_gatling_idx] = enc_beq(T4, T5, moby_mark_hostile - (moby_hostile_gatling_idx + 1))
    code[moby_hostile_spawner_idx] = enc_beq(T4, T5, moby_mark_hostile - (moby_hostile_spawner_idx + 1))
    code[moby_skip_mark_hostile_idx] = enc_beq(ZERO, ZERO, moby_after_hostile_check - (moby_skip_mark_hostile_idx + 1))
    code[moby_watch_chain_null_idx] = enc_beq(T8, ZERO, moby_after_watch_chain - (moby_watch_chain_null_idx + 1))
    code[moby_watch_chain_team_null_idx] = enc_beq(V0, ZERO, moby_after_watch_chain - (moby_watch_chain_team_null_idx + 1))
    code[moby_watch_parent_null_idx] = enc_beq(T8, ZERO, moby_after_watch_parent - (moby_watch_parent_null_idx + 1))
    code[moby_watch_parent_team_null_idx] = enc_beq(V0, ZERO, moby_after_watch_parent - (moby_watch_parent_team_null_idx + 1))
    code[moby_watch_stage2_skip_idx] = enc_beq(T3, ZERO, moby_after_watch_stage2 - (moby_watch_stage2_skip_idx + 1))
    code[moby_watch_stage3_skip_idx] = enc_beq(T3, ZERO, moby_after_watch_stage3 - (moby_watch_stage3_skip_idx + 1))
    code[moby_watch_stage4_skip_idx] = enc_beq(T3, ZERO, moby_after_watch_stage4 - (moby_watch_stage4_skip_idx + 1))
    code[moby_watch_stage5_skip_idx] = enc_beq(T3, ZERO, moby_after_watch_stage5 - (moby_watch_stage5_skip_idx + 1))
    code[moby_watch_validator_skip_idx] = enc_beq(T3, ZERO, moby_after_watch_validator - (moby_watch_validator_skip_idx + 1))
    code[moby_watch_stage6_skip_idx] = enc_beq(T3, ZERO, moby_after_watch_stage6 - (moby_watch_stage6_skip_idx + 1))
    code[moby_watch_pclass_skip_idx] = enc_beq(T3, ZERO, moby_after_watch_pclass - (moby_watch_pclass_skip_idx + 1))
    code[moby_watch_stage7_skip_idx] = enc_beq(T3, ZERO, moby_after_watch_stage7 - (moby_watch_stage7_skip_idx + 1))
    code[moby_watch_stage8_skip_idx] = enc_beq(T3, ZERO, moby_after_watch_stage8 - (moby_watch_stage8_skip_idx + 1))
    code[moby_stage2_skip_idx] = enc_beq(T8, ZERO, moby_after_stage2 - (moby_stage2_skip_idx + 1))
    code[moby_stage3_skip_idx] = enc_beq(T8, ZERO, moby_after_stage3 - (moby_stage3_skip_idx + 1))
    code[moby_stage4_skip_idx] = enc_beq(T8, ZERO, moby_after_stage4 - (moby_stage4_skip_idx + 1))
    code[moby_stage5_skip_idx] = enc_beq(T8, ZERO, moby_after_stage5 - (moby_stage5_skip_idx + 1))
    code[moby_stage6_skip_idx] = enc_beq(T8, ZERO, moby_after_stage6 - (moby_stage6_skip_idx + 1))
    code[moby_stage7_skip_idx] = enc_beq(T8, ZERO, moby_after_stage7 - (moby_stage7_skip_idx + 1))
    code[moby_stage8_skip_idx] = enc_beq(T8, ZERO, moby_after_stage8 - (moby_stage8_skip_idx + 1))
    code[moby_pass_nonhostile_idx] = enc_beq(T8, ZERO, moby_after_pass_record - (moby_pass_nonhostile_idx + 1))
    code[moby_pass_already_idx] = enc_bne(T8, ZERO, moby_after_pass_record - (moby_pass_already_idx + 1))
    code[moby_done_idx] = enc_beq(T2, ZERO, done - (moby_done_idx + 1))
    code[moby_skip_self_idx] = enc_beq(V1, T7, moby_loop - (moby_skip_self_idx + 1))
    code[moby_skip_hidden_idx] = enc_beq(T3, ZERO, moby_loop - (moby_skip_hidden_idx + 1))
    code[moby_skip_drawdist_idx] = enc_beq(T5, ZERO, moby_loop - (moby_skip_drawdist_idx + 1))
    code[moby_skip_fe_idx] = enc_beq(T4, AT, moby_loop - (moby_skip_fe_idx + 1))
    code[moby_skip_fd_idx] = enc_beq(T4, AT, moby_loop - (moby_skip_fd_idx + 1))
    code[moby_skip_pad_idx] = enc_beq(T4, AT, moby_loop - (moby_skip_pad_idx + 1))
    code[moby_skip_rocket_idx] = enc_beq(T4, AT, moby_loop - (moby_skip_rocket_idx + 1))
    code[moby_skip_validator_null_idx] = enc_beq(V0, ZERO, moby_loop - (moby_skip_validator_null_idx + 1))
    code[moby_validator_positive_idx] = enc_bc1t(moby_validator_ok - (moby_validator_positive_idx + 1))
    code[moby_skip_validator_val_idx] = enc_beq(V0, ZERO, moby_loop - (moby_skip_validator_val_idx + 1))
    code[moby_no_class_idx] = enc_beq(T4, ZERO, moby_score - (moby_no_class_idx + 1))
    code[moby_class5_not5_idx] = enc_bne(T5, AT, moby_after_class5 - (moby_class5_not5_idx + 1))
    code[moby_class5_hostile_allow_idx] = enc_bne(T8, ZERO, moby_after_class5 - (moby_class5_hostile_allow_idx + 1))
    code[moby_skip_class5_idx] = enc_beq(ZERO, ZERO, moby_loop - (moby_skip_class5_idx + 1))
    code[moby_range_skip_idx] = enc_bc1t(moby_candidate_done - (moby_range_skip_idx + 1))
    code[moby_nonhostile_idx] = enc_beq(T8, ZERO, moby_nonhostile - (moby_nonhostile_idx + 1))
    code[moby_hostile_compare_idx] = enc_beq(T5, AT, moby_compare_distance - (moby_hostile_compare_idx + 1))
    code[moby_accept_hostile_idx] = enc_beq(ZERO, ZERO, moby_candidate_done - (moby_accept_hostile_idx + 1))
    code[moby_nonhostile_skip_idx] = enc_beq(T5, AT, moby_candidate_done - (moby_nonhostile_skip_idx + 1))
    code[moby_best_skip_idx] = enc_bc1f(moby_candidate_done - (moby_best_skip_idx + 1))
    code[moby_generic_source_idx] = enc_beq(T8, ZERO, moby_store_generic - (moby_generic_source_idx + 1))
    code[moby_accept_hostile2_idx] = enc_beq(ZERO, ZERO, moby_candidate_done - (moby_accept_hostile2_idx + 1))

    code.append(enc_lw(V0, 0x04, SP))
    code.append(enc_sw(V0, DEBUG_PICK_RESULT_OFF, T9))
    code.append(enc_lw(T8, 0x08, SP))
    code.append(enc_sw(T8, DEBUG_PICK_SOURCE_OFF, T9))
    code.append(enc_lw(T8, 0x00, SP))
    code.append(enc_sw(T8, DEBUG_PICK_DIST2_OFF, T9))
    code.append(enc_ld(RA, 0xB8, SP))
    code.append(enc_addiu(SP, SP, 0xC0))
    code.append(enc_jr(RA))
    code.append(enc_nop())

    code[player_found_idx] = enc_bne(V0, ZERO, done - (player_found_idx + 1))

    return code


def build_update_physics(pick_target_addr):
    """Reuse the base physics stub but swap in the A1/A target helper."""
    code = base.build_update_physics()

    old_block = [
        enc_ld(A0, 8, SP),
        enc_addiu(A0, A0, 0xD0),
        enc_addiu(A1, ZERO, 1),
        enc_lw(A2, SCAN_GP_FILTER_OFF, GP),
        enc_addiu(A3, ZERO, 0),
        enc_lui(1, 0x3F80),
        enc_mtc1(1, 12),
        enc_jal(ADDR_MOBY_CONE_QUERY),
        enc_nop(),
        enc_lui(T1, SCAN_LIST_LUI),
        enc_lw(T1, SCAN_LIST_OFF & 0xFFFF, T1),
        enc_ld(A0, 8, SP),
        enc_lw(T0, 0x68, A0),
    ]

    new_block = [
        enc_ld(A0, 8, SP),                  # shooter moby
        enc_ld(A1, 16, SP),                 # shooter player
        enc_jal(pick_target_addr),
        enc_nop(),
        enc_sw(V0, 0x24, SP),               # stash target moby
        enc_ld(A0, 8, SP),                  # restore shooter moby
        enc_nop(),
        enc_nop(),
        enc_nop(),
        enc_nop(),
        enc_nop(),
        enc_nop(),
        enc_lw(T1, 0x24, SP),               # target for 0x42A570
    ]

    if len(old_block) != len(new_block):
        raise RuntimeError("homing block replacement changed length")

    at = find_subsequence(code, old_block)
    if at < 0:
        raise RuntimeError("couldn't locate stock M5 homing block in build_update_physics()")
    code[at:at + len(old_block)] = new_block

    # Base tank patch passes f13 = 0.0 into spawnRocket1B1E. Rocket update uses
    # pvar+0x28 as the turn-rate clamp; with zero the homing factor collapses to
    # zero and the rocket flies straight even with a valid target. Reuse F11
    # (still holding 2.0f from MUZZLE_Z setup) as a temporary nonzero turn
    # clamp so we can verify the rest of the homing path visually.
    zero_turn_block = [
        enc_addiu(A3, ZERO, 0),
        enc_mtc1(ZERO, 12),
        enc_mtc1(ZERO, 13),
    ]
    nonzero_turn_block = [
        enc_addiu(A3, ZERO, 0),
        enc_mtc1(ZERO, 12),
        enc_mov_s(13, 11),
    ]
    at = find_subsequence(code, zero_turn_block)
    if at < 0:
        raise RuntimeError("couldn't locate zero-turn spawn setup in build_update_physics()")
    code[at:at + len(zero_turn_block)] = nonzero_turn_block

    return code


def build_stub(inject_base, physics_slot):
    """Same stub layout as the base patcher, plus a target-picker helper."""
    global LAST_DEBUG_ADDR

    code = []

    # --- nop_callback (+0x000) ---
    nop_cb_addr = inject_base + 0x000
    code.append(enc_jr(RA))
    code.append(enc_addiu(V0, ZERO, 0))

    # --- get_vehicle_base (+0x008) ---
    code.append(enc_lw(V0, 0x68, A0))
    code.append(enc_jr(RA))
    code.append(enc_lw(V0, PVAR_VEHICLE_PTR, V0))
    code.append(enc_nop())

    # --- update_5588 (+0x018) ---
    update_addr = inject_base + 0x018

    code.append(enc_addiu(SP, SP, -64))
    code.append(enc_sd(S0, 0, SP))
    code.append(enc_sd(S1, 8, SP))
    code.append(enc_sd(S2, 16, SP))
    code.append(enc_sd(RA, 24, SP))
    code.append(enc_daddu(S1, A0, ZERO))
    code.append(enc_lw(S0, 0x68, S1))

    code.append(enc_lbu(V0, 0x20, S1))
    bne_slot = len(code)
    code.append(0)
    code.append(enc_nop())

    code.append(enc_lhu(V0, 0x34, S1))
    code.append(enc_ori(V0, V0, 0x5020))
    code.append(enc_sh(V0, 0x34, S1))
    code.append(enc_addiu(V0, ZERO, 0xFF))
    code.append(enc_sb(V0, 0x30, S1))

    code.append(enc_daddu(A0, S1, ZERO))
    code.append(enc_jal(ADDR_BIND_ENTITY))
    code.append(enc_addiu(A1, ZERO, -1))

    code.append(enc_addiu(A1, S1, 0x10))
    code.append(enc_jal(ADDR_REGISTER_CONFIG))
    code.append(enc_daddu(A0, S1, ZERO))

    physics_lui_idx = len(code)
    code.append(enc_nop())
    physics_addiu_idx = len(code)
    code.append(enc_nop())

    slot_regs = [A1, A2, A3, T0, T1, T2, T3]
    for reg in slot_regs:
        hi, lo = hi_lo(nop_cb_addr)
        code.append(enc_lui(reg, hi))
        code.append(enc_addiu(reg, reg, lo))

    code.append(enc_jal(ADDR_REGISTER_CALLBACKS))
    code.append(enc_addiu(A0, ZERO, VEHICLE_TYPE))

    code.append(enc_addiu(A0, ZERO, VEHICLE_TYPE))
    code.append(enc_daddu(A1, S1, ZERO))
    code.append(enc_lui(A2, 0xFFFF))
    code.append(enc_ori(A2, A2, 0xFFFF))
    code.append(enc_addiu(A3, ZERO, PVAR_NEW_SIZE))
    code.append(enc_lui(T0, 0x0800))
    code.append(enc_jal(ADDR_GUBER_CREATE))
    code.append(enc_nop())

    code.append(enc_sw(V0, PVAR_VEHICLE_PTR, S0))
    code.append(enc_sw(V0, 0x90, S1))

    code.append(enc_daddu(A0, S1, ZERO))
    code.append(enc_addiu(A1, ZERO, 1))
    code.append(enc_jal(ADDR_MOBY_SET_STATE))
    code.append(enc_addiu(A2, ZERO, -1))

    state0_jump_idx = len(code)
    code.append(0)
    code.append(enc_nop())

    state1_index = len(code)
    code.append(enc_daddu(A0, S1, ZERO))
    update_physics_jal_idx = len(code)
    code.append(0)
    code.append(enc_nop())

    epilogue_index = len(code)
    code.append(enc_ld(S0, 0, SP))
    code.append(enc_ld(S1, 8, SP))
    code.append(enc_ld(S2, 16, SP))
    code.append(enc_ld(RA, 24, SP))
    code.append(enc_jr(RA))
    code.append(enc_addiu(SP, SP, 64))

    branch_offset = state1_index - (bne_slot + 1)
    code[bne_slot] = enc_bne(V0, ZERO, branch_offset)

    epilogue_va = inject_base + epilogue_index * 4
    code[state0_jump_idx] = 0x08000000 | ((epilogue_va >> 2) & 0x03FFFFFF)

    debug_addr = inject_base + len(code) * 4
    LAST_DEBUG_ADDR = debug_addr
    code.extend([0] * (DEBUG_BLOCK_SIZE // 4))

    pick_target_addr = inject_base + len(code) * 4
    pick_target_code = build_pick_homing_target(debug_addr)
    code.extend(pick_target_code)

    physics_addr = inject_base + len(code) * 4
    physics_code = build_update_physics(pick_target_addr)
    code.extend(physics_code)

    code[update_physics_jal_idx] = enc_jal(physics_addr)
    code[physics_lui_idx] = enc_nop()
    code[physics_addiu_idx] = enc_nop()

    return b"".join(p32(w) for w in code), update_addr, physics_addr


base.build_stub = build_stub
base.__doc__ = __doc__


if __name__ == "__main__":
    base.main()
    if LAST_DEBUG_ADDR is not None:
        print(f"  debug_pick_result: 0x{LAST_DEBUG_ADDR + DEBUG_PICK_RESULT_OFF:08x}")
        print(f"  debug_pick_source: 0x{LAST_DEBUG_ADDR + DEBUG_PICK_SOURCE_OFF:08x}")
        print(f"  debug_pick_dist2:  0x{LAST_DEBUG_ADDR + DEBUG_PICK_DIST2_OFF:08x}")
        print(f"  debug_pick_calls:  0x{LAST_DEBUG_ADDR + DEBUG_PICK_CALLS_OFF:08x}")
        print(f"  debug_hostile_ptr: 0x{LAST_DEBUG_ADDR + DEBUG_FIRST_HOSTILE_PTR_OFF:08x}")
        print(f"  debug_hostile_cls: 0x{LAST_DEBUG_ADDR + DEBUG_FIRST_HOSTILE_CLASS_OFF:08x}")
        print(f"  debug_hostile_stg: 0x{LAST_DEBUG_ADDR + DEBUG_FIRST_HOSTILE_STAGE_OFF:08x}")
        print(f"  debug_hostile_okp: 0x{LAST_DEBUG_ADDR + DEBUG_FIRST_HOSTILE_PASS_PTR_OFF:08x}")
        print(f"  debug_hostile_okc: 0x{LAST_DEBUG_ADDR + DEBUG_FIRST_HOSTILE_PASS_CLASS_OFF:08x}")
        print(f"  debug_stock_count: 0x{LAST_DEBUG_ADDR + DEBUG_STOCK_COUNT_OFF:08x}")
        print(f"  debug_stock_l0p:  0x{LAST_DEBUG_ADDR + DEBUG_STOCK_LIST0_PTR_OFF:08x}")
        print(f"  debug_stock_l0c:  0x{LAST_DEBUG_ADDR + DEBUG_STOCK_LIST0_CLASS_OFF:08x}")
        print(f"  debug_stock_l1p:  0x{LAST_DEBUG_ADDR + DEBUG_STOCK_LIST1_PTR_OFF:08x}")
        print(f"  debug_stock_l1c:  0x{LAST_DEBUG_ADDR + DEBUG_STOCK_LIST1_CLASS_OFF:08x}")
        print(f"  debug_stock_cop:  0x{LAST_DEBUG_ADDR + DEBUG_STOCK_COLLOUT_PTR_OFF:08x}")
        print(f"  debug_stock_coc:  0x{LAST_DEBUG_ADDR + DEBUG_STOCK_COLLOUT_CLASS_OFF:08x}")
        print(f"  debug_watch_stg: 0x{LAST_DEBUG_ADDR + DEBUG_WATCH_STAGE_OFF:08x}")
        print(f"  debug_watch_grp: 0x{LAST_DEBUG_ADDR + DEBUG_WATCH_GROUP_OFF:08x}")
        print(f"  debug_watch_par: 0x{LAST_DEBUG_ADDR + DEBUG_WATCH_PARENT_OFF:08x}")
        print(f"  debug_watch_chn: 0x{LAST_DEBUG_ADDR + DEBUG_WATCH_CHAIN_OFF:08x}")
        print(f"  debug_watch_vp:  0x{LAST_DEBUG_ADDR + DEBUG_WATCH_VALIDATOR_PTR_OFF:08x}")
        print(f"  debug_watch_vf:  0x{LAST_DEBUG_ADDR + DEBUG_WATCH_VALIDATOR_VAL_OFF:08x}")
        print(f"  debug_watch_c46: 0x{LAST_DEBUG_ADDR + DEBUG_WATCH_PCLASS46_OFF:08x}")
        print(f"  debug_watch_mdb: 0x{LAST_DEBUG_ADDR + DEBUG_WATCH_MODEBITS_OFF:08x}")
        print(f"  debug_player_tm: 0x{LAST_DEBUG_ADDR + DEBUG_PLAYER_TEAM_OFF:08x}")
        print(f"  debug_watch_tm:  0x{LAST_DEBUG_ADDR + DEBUG_WATCH_TARGET_TEAM_OFF:08x}")
        print(f"  debug_watch_lck: 0x{LAST_DEBUG_ADDR + DEBUG_WATCH_LOCKON_OFF:08x}")
        print(f"  debug_watch_nat: 0x{LAST_DEBUG_ADDR + DEBUG_WATCH_NOAUTOTRACK_OFF:08x}")
        print(f"  debug_watch_inv: 0x{LAST_DEBUG_ADDR + DEBUG_WATCH_INVALIDTARGET_OFF:08x}")
        print(f"  debug_watch_cc:  0x{LAST_DEBUG_ADDR + DEBUG_WATCH_CHAIN_CLASS_OFF:08x}")
        print(f"  debug_watch_ct:  0x{LAST_DEBUG_ADDR + DEBUG_WATCH_CHAIN_TEAM_OFF:08x}")
        print(f"  debug_watch_pc:  0x{LAST_DEBUG_ADDR + DEBUG_WATCH_PARENT_CLASS_OFF:08x}")
        print(f"  debug_watch_pt:  0x{LAST_DEBUG_ADDR + DEBUG_WATCH_PARENT_TEAM_OFF:08x}")
