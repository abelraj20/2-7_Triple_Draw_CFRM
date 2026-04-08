#!/usr/bin/env python3
# this is the code for the no-limit model

from __future__ import annotations

import argparse
import random
import numpy as np
from dataclasses import dataclass
from typing import List, Optional

from cfr_common_bucketgame import (
    SeedItem,
    reset_infosets,
    build_unique_seeds_and_weights_from_list,
    build_bucket_pair_matchups_seedmodel,
    BUCKETS_FULL_PAIRS,
    bucket_label_full_pairs,
    train_cfrplus_sweep,
    export_variant,
    A_CHECK, A_CALL, A_FOLD,
)

SEED = 42
ITERATIONS = 250_000

STARTING_PLAYER = 1
STARTING_POT = 5.0
STACK = 25.0

# exploration not used (CFR+ full sweep)
BIG_BLIND = 0.5
BR_POLICY_ITERS = 16
EXP_PRINT_STEP = 200
EV_SAMPLES_PER_BUCKET = 800

# bet sizes as pot fractions
BET_ACTIONS = ["b40", "b80", "b120", "ba"]   # 'ba' = all-in
ALL_RAISE_ACTIONS = ["r86", "r111", "ra"]    # 'ra' = all-in

RAISE_OPTIONS = {
    "b40":  {"r86": 0.86, "ra": "allin"},
    "b80":  {"r111": 1.11, "ra": "allin"},
    "b120": {"ra": "allin"},
    "r86":  {"ra": "allin"},
    "r111": {"ra": "allin"},
    "ba":   {},
    "ra":   {},
}

# report sequences MUST remain stable (frontend / analysis expects these)
REPORT_SEQS = [
    "",
    "k",
    "b40", "b80", "b120", "ba",
    "kb40", "kb80", "kb120", "kba",
    "b40r86", "b80r111",
    "b40ra", "b80ra", "b120ra",
    "b40r86ra", "b80r111ra",
    "kb40r86", "kb80r111",
    "kb40ra", "kb80ra", "kb120ra",
    "kb40r86ra", "kb80r111ra",
]

# seed grids (rank-only, no suits)

btn_4card_raw = [
    "2347", "2357", "2367", "2457", "2467", "2567", "3457", "3467", "3567", "4567",
    "2348", "2358", "2368", "2378", "2458", "2468", "2478", "2568", "2578", "2678",
    "3458", "3468", "3478", "3568", "3578", "3678", "4568", "4578", "4678", "5678",
    "2349", "2359", "2369", "2379", "2389", "2459", "2469", "2479", "2489", "2569",
    "2579", "2589", "2679", "2689", "2789",
    "3459", "3469", "3479", "3489", "3569", "3579", "3589", "3679", "3689", "4569",
    "4579", "4589", "5679", "5689", "6789",
    "234T", "235T", "245T", "236T", "246T", "256T", "237T", "247T", "257T", "267T",
    "238T", "248T", "258T", "345T", "346T",
]

bb_4card_raw = [
    "2348", "2358", "2368", "2378", "2458", "2468", "2478", "2568", "2578", "2678",
    "3458", "3468", "3478", "3568", "3578", "3678", "4568", "4578", "4678", "5678",
    "2349", "2359", "2369", "2379", "2389", "2459", "2469", "2479", "2489", "2569",
    "2579", "2589", "2679", "2689", "2789",
    "3459", "3469", "3479", "3489", "3569", "3579", "3589", "3679", "3689", "4569",
    "4579", "4589", "5679", "5689", "6789",
    "234T", "235T", "245T", "236T", "246T", "256T", "237T", "247T", "257T", "267T",
    "345T", "346T",
]

# NL game state
@dataclass
# helper for this part of the script
class NLState:
    to_act: int
    history: str
    pot: float
    to_call: float
    terminal: bool
    winner: Optional[int]
    showdown: bool
    invested_btn: float
    invested_bb: float
    stack_btn: float
    stack_bb: float
    last_action: str
    allin: bool


# creates the starting state for the no-limit tree
def initial_state(start_pot: float) -> NLState:
    return NLState(
        to_act=STARTING_PLAYER,
        history="",
        pot=float(start_pot),
        to_call=0.0,
        terminal=False,
        winner=None,
        showdown=False,
        invested_btn=0.0,
        invested_bb=0.0,
        stack_btn=float(STACK),
        stack_bb=float(STACK),
        last_action="",
        allin=False,
    )


# helper for this part of the script
def calc_bet_amount(action: str, pot: float, stack_acting: float) -> float:
    if action in ("ba", "ra"):
        return float(stack_acting)
    if action.startswith("b"):
        pct = int(action[1:]) / 100.0
        return min(float(pot) * pct, float(stack_acting))
    if action.startswith("r"):
        pct = int(action[1:]) / 100.0
        return min(float(pot) * pct, float(stack_acting))
    return 0.0


# returns the legal actions for the current state
def legal_actions(s: NLState) -> List[str]:
    if s.terminal:
        return []

    if s.allin:
        if s.to_call > 0:
            return [A_FOLD, A_CALL]
        return []

    if s.to_call == 0:
        acts = [A_CHECK]
        stack = s.stack_btn if s.to_act == 0 else s.stack_bb
        if stack > 0:
            for ba in BET_ACTIONS:
                amt = calc_bet_amount(ba, s.pot, stack)
                if amt > 0:
                    acts.append(ba)
        return acts

    acts = [A_FOLD, A_CALL]
    stack = s.stack_btn if s.to_act == 0 else s.stack_bb
    remaining = stack - s.to_call
    if remaining > 0 and s.last_action in RAISE_OPTIONS:
        for ra in RAISE_OPTIONS[s.last_action]:
            amt = calc_bet_amount(ra, s.pot + s.to_call, remaining)
            if amt > 0:
                acts.append(ra)
    return acts


# helper for this part of the script
def step(s: NLState, a: str) -> NLState:
    t = NLState(**vars(s))
    t.history += a
    p = s.to_act
    opp = 1 - p
    stack_p = s.stack_btn if p == 0 else s.stack_bb

    if a == A_CHECK:
        if t.history.endswith("kk"):
            t.terminal = True
            t.showdown = True
        else:
            t.to_act = opp
        return t

    if a == A_FOLD:
        t.terminal = True
        t.winner = opp
        return t

    if a == A_CALL:
        call_amt = min(float(s.to_call), float(stack_p))
        t.pot += call_amt
        if p == 0:
            t.invested_btn += call_amt
            t.stack_btn -= call_amt
        else:
            t.invested_bb += call_amt
            t.stack_bb -= call_amt
        t.to_call = 0.0
        t.terminal = True
        t.showdown = True
        if t.stack_btn <= 0 or t.stack_bb <= 0:
            t.allin = True
        return t

    if a.startswith("b") or a.startswith("r"):
        pot_for_calc = s.pot + s.to_call if a.startswith("r") else s.pot
        bet_amt = calc_bet_amount(a, pot_for_calc, float(stack_p) - float(s.to_call))
        total_put_in = float(s.to_call) + float(bet_amt)

        if p == 0:
            t.invested_btn += total_put_in
            t.stack_btn -= total_put_in
        else:
            t.invested_bb += total_put_in
            t.stack_bb -= total_put_in

        t.pot += total_put_in
        t.to_call = float(bet_amt)
        t.last_action = a
        t.to_act = opp

        if (a in ("ba", "ra") or (p == 0 and t.stack_btn <= 0) or (p == 1 and t.stack_bb <= 0)):
            t.allin = True
        return t

    return t


# helper for this part of the script
def nl_state_from_history(h: str, start_pot: float) -> NLState:
    s = initial_state(start_pot)
    i = 0
    while i < len(h):
        if h[i] in ("k", "f", "c"):
            s = step(s, h[i])
            i += 1
        else:
            j = i + 1
            while j < len(h) and (h[j].isdigit() or h[j] == "a"):
                j += 1
            action = h[i:j]
            s = step(s, action)
            i = j
    return s


# helper for this part of the script
def ikey(p: int, bucket: str, s: NLState) -> tuple:
    return (p, bucket, s.history, round(float(s.to_call), 1), bool(s.allin))


# helper for this part of the script
def info_key_str(s: NLState) -> str:
    return f"h:{s.history}|tc:{round(float(s.to_call),1)}|ai:{int(bool(s.allin))}"


# keeps no-limit actions in a consistent order
def order_actions_nl(acts: List[str]) -> List[str]:
    order = [A_CHECK] + BET_ACTIONS + [A_CALL, A_FOLD] + ALL_RAISE_ACTIONS
    return [a for a in order if a in acts]


# runs the full script from the command line
def main():
    global SEED, ITERATIONS, BR_POLICY_ITERS, EXP_PRINT_STEP, EV_SAMPLES_PER_BUCKET, STACK, STARTING_POT

    ap = argparse.ArgumentParser(description="CFR+ NL (FULL chance sweep bucket-game)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--iters", type=int, default=ITERATIONS)
    ap.add_argument("--exploit-step", type=int, default=None)
    ap.add_argument("--tracking-step", type=int, default=None)
    ap.add_argument("--exploit-samples", type=int, default=None)
    ap.add_argument("--br-policy-iters", type=int, default=BR_POLICY_ITERS)
    ap.add_argument("--exp-print-step", type=int, default=EXP_PRINT_STEP)
    ap.add_argument("--ev-samples", type=int, default=EV_SAMPLES_PER_BUCKET)
    ap.add_argument("--stack", type=float, default=STACK)
    ap.add_argument("--start-pot", type=float, default=STARTING_POT)
    args = ap.parse_args()

    SEED = int(args.seed)
    ITERATIONS = int(args.iters)
    BR_POLICY_ITERS = int(args.br_policy_iters)
    EXP_PRINT_STEP = int(args.exp_print_step)
    EV_SAMPLES_PER_BUCKET = int(args.ev_samples)

    STACK = float(args.stack)
    STARTING_POT = float(args.start_pot)

    random.seed(SEED)
    np.random.seed(SEED)

    print(
        f"nl CFR+ FULL: iters={ITERATIONS:,} seed={SEED} "
        f"BB={BIG_BLIND} stack={STACK} pot={STARTING_POT}"
    )

    btn_items: List[SeedItem] = []
    bb_items: List[SeedItem] = []

    seeds, w = build_unique_seeds_and_weights_from_list(btn_4card_raw)
    btn_items.extend(
        [SeedItem(seed=s, draws=1, weight=float(wi)) for s, wi in zip(seeds, w)]
    )

    seeds, w = build_unique_seeds_and_weights_from_list(bb_4card_raw)
    bb_items.extend(
        [SeedItem(seed=s, draws=1, weight=float(wi)) for s, wi in zip(seeds, w)]
    )

    print("building bucket-pair chance distribution (exact draws 1 only)...")
    matchups, bucket_freq_by_player = build_bucket_pair_matchups_seedmodel(
        btn_items, bb_items, BUCKETS_FULL_PAIRS, bucket_label_full_pairs
    )
    print(f"done: {len(matchups)} nonzero bucket-pairs")

    pot = float(STARTING_POT)
    random.seed(SEED)
    np.random.seed(SEED)
    reset_infosets()

    tracked_iters, regret_data, evo_data, node_actions, ex_i, ex_mbb, ex_bb, ex_chip = train_cfrplus_sweep(
        matchups=matchups,
        buckets=BUCKETS_FULL_PAIRS,
        report_seqs=REPORT_SEQS,
        iterations=ITERATIONS,
        pot=pot,
        initial_state_fn=initial_state,
        state_from_history_fn=nl_state_from_history,
        legal_actions_fn=legal_actions,
        step_fn=step,
        ikey_fn=ikey,
        info_key_str_fn=info_key_str,
        br_policy_iters=BR_POLICY_ITERS,
        big_blind=BIG_BLIND,
        exp_print_step=EXP_PRINT_STEP,
    )

    export_variant(
        prefix="nl",
        pot=pot,
        iterations=ITERATIONS,
        buckets=BUCKETS_FULL_PAIRS,
        report_seqs=REPORT_SEQS,
        bucket_freq_by_player=bucket_freq_by_player,
        tracked_iters=tracked_iters,
        regret_data=regret_data,
        evo_data=evo_data,
        node_actions=node_actions,
        exploit_iters=ex_i,
        expl_mbb=ex_mbb,
        expl_bb=ex_bb,
        expl_chip=ex_chip,
        initial_state_fn=initial_state,
        state_from_history_fn=nl_state_from_history,
        legal_actions_fn=legal_actions,
        step_fn=step,
        ikey_fn=ikey,
        order_actions_fn=order_actions_nl,
        matchups=matchups,
        ev_samples_per_bucket=EV_SAMPLES_PER_BUCKET,
        extra_meta={
            "stack": float(STACK),
            "start_pot": float(STARTING_POT),
            "bet_actions": BET_ACTIONS,
            "raise_options": {k: list(v.keys()) for k, v in RAISE_OPTIONS.items()},
            "btn_grid_type": "4card_only",
            "bb_grid_type": "4card_only",
        },
    )

    print("\nnl done!")


if __name__ == "__main__":
    main()
