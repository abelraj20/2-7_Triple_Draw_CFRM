#!/usr/bin/env python3
# this is the code for the card-removal model

from __future__ import annotations

import os
import json
import random
import bisect
import time
import argparse
from dataclasses import dataclass
from collections import Counter
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from math import comb

import numpy as np

# Rank / deck helpers

RANKS: List[int] = list(range(2, 15))  # 2..14 (A)
_COPIES_PER_RANK: int = 4
_DECK_COUNTS_BASE: Tuple[int, ...] = tuple([_COPIES_PER_RANK] * len(RANKS))  # 13-long

_RANK_TO_IDX = {r: r - 2 for r in RANKS}
_IDX_TO_RANK = {i: i + 2 for i in range(len(RANKS))}


# starts the deck counts with the removed twos already taken out
def make_deck_counts_base(discarded_twos: int) -> Tuple[int, ...]:
    """
    Start from a full rank-only deck, but remove `discarded_twos` copies of rank 2
    before any seeds / draws are dealt.

    Max is 3 because BTN always has a 2 in its seed.
    """
    discarded_twos = int(discarded_twos)
    if not (0 <= discarded_twos <= 3):
        raise ValueError(
            f"discarded_twos must be between 0 and 3, got {discarded_twos}"
        )

    c = list(_DECK_COUNTS_BASE)
    c[_RANK_TO_IDX[2]] = _COPIES_PER_RANK - discarded_twos
    return tuple(c)


# turns one rank character into the integer version
def parse_rank_char(ch: str) -> int:
    ch = ch.strip().upper()
    if ch == "T":
        return 10
    if ch == "J":
        return 11
    if ch == "Q":
        return 12
    if ch == "K":
        return 13
    if ch == "A":
        return 14
    return int(ch)


# reads a seed string and sorts it into rank order
def parse_seed_str(s: str) -> Tuple[int, ...]:
    s = s.strip()
    return tuple(sorted(parse_rank_char(ch) for ch in s))


# counts repeated seeds in the grid so they can be weighted properly
def build_unique_seeds_and_weights_from_grid(
    grid: Sequence[Sequence[str]],
) -> Tuple[List[Tuple[int, ...]], np.ndarray]:
    """Counts multiplicity in the grid (range weights)."""
    flat = [h for row in grid for h in row]
    counts = Counter(parse_seed_str(h) for h in flat)
    seeds = list(counts.keys())
    weights = np.array([counts[s] for s in seeds], dtype=float)
    return seeds, weights


# removes seeds that contain a blocked rank
def filter_out_seeds_containing_rank(
    seeds: Sequence[Tuple[int, ...]],
    weights: np.ndarray,
    blocked_rank: int,
) -> Tuple[List[Tuple[int, ...]], np.ndarray]:
    kept = [(s, float(w)) for s, w in zip(seeds, weights) if blocked_rank not in s]
    if not kept:
        raise RuntimeError(f"All seeds were removed when filtering out rank {blocked_rank}.")
    out_seeds = [s for s, _ in kept]
    out_weights = np.array([w for _, w in kept], dtype=float)
    return out_seeds, out_weights


# keeps only seeds that contain the required rank
def filter_to_seeds_containing_rank(
    seeds: Sequence[Tuple[int, ...]],
    weights: np.ndarray,
    required_rank: int,
) -> Tuple[List[Tuple[int, ...]], np.ndarray]:
    kept = [(s, float(w)) for s, w in zip(seeds, weights) if required_rank in s]
    if not kept:
        raise RuntimeError(f"All seeds were removed when requiring rank {required_rank}.")
    out_seeds = [s for s, _ in kept]
    out_weights = np.array([w for _, w in kept], dtype=float)
    return out_seeds, out_weights


# removes the seed cards from the rank deck before drawing
def _counts_after_seeds(
    btn_seed: Tuple[int, ...],
    bb_seed: Tuple[int, ...],
    discarded_twos: int,
) -> Optional[Tuple[int, ...]]:
    # In this model, BTN must always have a 2 in seed.
    if 2 not in btn_seed:
        return None

    c = list(make_deck_counts_base(discarded_twos))

    for r in btn_seed:
        i = _RANK_TO_IDX.get(r)
        if i is None:
            return None
        c[i] -= 1
        if c[i] < 0:
            return None

    for r in bb_seed:
        i = _RANK_TO_IDX.get(r)
        if i is None:
            return None
        c[i] -= 1
        if c[i] < 0:
            return None

    return tuple(c)


# 2-7 Lowball eval (rank-only, NO wheel special-case)
# Category order (lower is better):
#   0 high-card, 1 pair, 2 two pair, 3 trips, 4 straight, 5 full house, 6 quads
# For high-card, compare by descending ranks (lex), smaller is better.

def is_straight(vals: Tuple[int, ...]) -> bool:
    sv = sorted(set(vals))
    if len(sv) < 5:
        return False
    for i in range(len(sv) - 4):
        if sv[i + 4] - sv[i] == 4:
            return True
    return False


# classifies a rank-only 2-7 hand into its hand type
def classify_27(hand: Tuple[int, ...]) -> Tuple[int, Tuple[int, ...]]:
    c = Counter(hand)
    f = sorted(c.values(), reverse=True)
    desc = tuple(sorted(hand, reverse=True))

    if 4 in f:
        return 6, desc
    if 3 in f and 2 in f:
        return 5, desc
    if is_straight(hand) and max(f) == 1:
        return 4, desc
    if 3 in f:
        return 3, desc
    if f.count(2) == 2:
        return 2, desc
    if 2 in f:
        return 1, desc
    return 0, desc


# compares btn and bb hands and returns who wins
def compare(btn: Tuple[int, ...], bb: Tuple[int, ...]) -> int:
    """
    Returns:
      +1 if BTN wins (better low hand),
      -1 if BTN loses,
       0 if tie.
    """
    c1, v1 = classify_27(btn)
    c2, v2 = classify_27(bb)

    if c1 < c2:
        return +1
    if c1 > c2:
        return -1
    if v1 < v2:
        return +1
    if v1 > v2:
        return -1
    return 0


# Buckets (same "Extra" logic you use) + Straight bucket

_EXTRA_BUCKET = "Extra"
STRAIGHT_BUCKET = "Straight"

BUCKETS_1DRAW: List[str] = [
    "75", "76", "85", "86", "87", "95", "96", "97", "98",
    "T5", "T6", "T7", "T8", "T9", "J8", "J9", "Q", "K", "A",
    "22", "33", "44", "55", "66", "77", "88", "99",
    STRAIGHT_BUCKET,
]


# maps a high-card hand into the right bucket label
def _highcard_bucket_label(hi: int, sh: int) -> str:
    if hi == 7:
        if sh <= 5:
            return "75"
        if sh == 6:
            return "76"
        return _EXTRA_BUCKET

    if hi == 8:
        if sh == 5:
            return "85"
        if sh == 6:
            return "86"
        if sh == 7:
            return "87"
        return _EXTRA_BUCKET

    if hi == 9:
        if sh == 5:
            return "95"
        if sh == 6:
            return "96"
        if sh == 7:
            return "97"
        if sh == 8:
            return "98"
        return _EXTRA_BUCKET

    if hi == 10:
        if sh <= 5:
            return "T5"
        if sh == 6:
            return "T6"
        if sh == 7:
            return "T7"
        if sh == 8:
            return "T8"
        if sh == 9:
            return "T9"
        return _EXTRA_BUCKET

    if hi == 11:
        return "J8" if sh <= 8 else "J9"

    if hi == 12:
        return "Q"
    if hi == 13:
        return "K"
    if hi == 14:
        return "A"

    return _EXTRA_BUCKET


# bucket logic for the 1-draw abstraction
def bucket_label_1draw(hand: Tuple[int, ...]) -> str:
    """
    Pairs are only 22..99 (TT+ => Extra).
    TwoPair/Trips/FullHouse/Quads => Extra.
    Straight (pure) => "Straight".
    """
    cat, _ = classify_27(hand)

    if cat == 4:
        return STRAIGHT_BUCKET

    if cat >= 2:
        return _EXTRA_BUCKET

    if cat == 1:
        pr = next(r for r, cnt in Counter(hand).items() if cnt == 2)
        if 2 <= pr <= 9:
            return f"{pr}{pr}"
        return _EXTRA_BUCKET

    s = sorted(hand)
    hi, sh = s[-1], s[-2]
    return _highcard_bucket_label(hi, sh)


# Chance model: seed ranges + exact completions

@dataclass(frozen=True)
# helper for this part of the script
class SeedItem:
    seed: Tuple[int, ...]
    draws: int
    weight: float


@dataclass(frozen=True)
# helper for this part of the script
class Matchup:
    btn_bucket: str
    bb_bucket: str
    prob: float
    win_p: float
    tie_p: float
    lose_p: float


_DRAW_CACHE: Dict[
    Tuple[Tuple[int, ...], int],
    List[Tuple[Tuple[int, ...], float, Tuple[int, ...]]]
] = {}


# lists all possible draws from the remaining rank deck with their weights
def _draw_outcomes(
    counts: Tuple[int, ...],
    k: int,
) -> List[Tuple[Tuple[int, ...], float, Tuple[int, ...]]]:
    """
    Unordered draw from a multiset deck with distinct card instances.
    Only used here for k in {0,1,2}.
    """
    key = (counts, k)
    cached = _DRAW_CACHE.get(key)
    if cached is not None:
        return cached

    n = sum(counts)
    if k < 0 or k > n:
        _DRAW_CACHE[key] = []
        return _DRAW_CACHE[key]

    if k == 0:
        out = [((), 1.0, counts)]
        _DRAW_CACHE[key] = out
        return out

    if k == 1:
        denom = float(n)
        out = []
        for i, c in enumerate(counts):
            if c <= 0:
                continue
            r = _IDX_TO_RANK[i]
            p = float(c) / denom
            nxt = list(counts)
            nxt[i] -= 1
            out.append(((r,), p, tuple(nxt)))
        _DRAW_CACHE[key] = out
        return out

    if k == 2:
        denom = comb(n, 2)
        if denom <= 0:
            _DRAW_CACHE[key] = []
            return _DRAW_CACHE[key]
        denom = float(denom)
        out = []

        for i, c in enumerate(counts):
            if c >= 2:
                ways = comb(c, 2)
                p = float(ways) / denom
                r = _IDX_TO_RANK[i]
                nxt = list(counts)
                nxt[i] -= 2
                out.append(((r, r), p, tuple(nxt)))

        for i, ci in enumerate(counts):
            if ci <= 0:
                continue
            for j in range(i + 1, len(counts)):
                cj = counts[j]
                if cj <= 0:
                    continue
                ways = ci * cj
                p = float(ways) / denom
                r1 = _IDX_TO_RANK[i]
                r2 = _IDX_TO_RANK[j]
                nxt = list(counts)
                nxt[i] -= 1
                nxt[j] -= 1
                out.append(((r1, r2), p, tuple(nxt)))

        _DRAW_CACHE[key] = out
        return out

    raise ValueError(f"Unsupported k={k} (only 0/1/2 supported).")


# SIM root bucket frequencies

def _sample_index_weighted(w: np.ndarray) -> int:
    w = np.asarray(w, dtype=float)
    s = float(w.sum())
    if s <= 0:
        return 0

    r = random.random() * s
    acc = 0.0
    for i, wi in enumerate(w):
        acc += float(wi)
        if r <= acc:
            return i
    return len(w) - 1


# samples one rank from the remaining deck counts
def _sample_one_from_counts(counts: List[int]) -> int:
    n = sum(counts)
    if n <= 0:
        raise RuntimeError("empty deck")

    r = random.randrange(n)
    acc = 0
    for i, c in enumerate(counts):
        acc += c
        if r < acc:
            counts[i] -= 1
            return i

    i = len(counts) - 1
    counts[i] -= 1
    return i


# monte carlo estimate of the starting bucket frequencies
def estimate_bucket_freqs_sim_seedmodel(
    n: int,
    btn_items: List[SeedItem],
    bb_items: List[SeedItem],
    buckets: List[str],
    bucket_label_fn: Callable[[Tuple[int, ...]], str],
    discarded_twos: int,
) -> Dict[str, Dict[str, float]]:
    """
    Monte Carlo ROOT marginals:
      - sample BTN seed by weight
      - sample BB seed by weight
      - sample completion draws from remaining multiset deck
      - bucket each completed hand
      - exclude Extra
      - normalize over counted hands per player
    """
    btn_ct = Counter()
    bb_ct = Counter()

    btn_w = np.array([float(it.weight) for it in btn_items], dtype=float)
    bb_w = np.array([float(it.weight) for it in bb_items], dtype=float)

    buckets = [b for b in buckets if b != _EXTRA_BUCKET]

    for _ in range(int(n)):
        bi = btn_items[_sample_index_weighted(btn_w)]
        oi = bb_items[_sample_index_weighted(bb_w)]

        counts0 = _counts_after_seeds(
            bi.seed,
            oi.seed,
            discarded_twos=discarded_twos,
        )
        if counts0 is None:
            continue

        counts = list(counts0)

        btn_draw: List[int] = []
        ok = True
        for _k in range(int(bi.draws)):
            try:
                idx = _sample_one_from_counts(counts)
            except RuntimeError:
                ok = False
                break
            btn_draw.append(_IDX_TO_RANK[idx])
        if not ok:
            continue

        bb_draw: List[int] = []
        for _k in range(int(oi.draws)):
            try:
                idx = _sample_one_from_counts(counts)
            except RuntimeError:
                ok = False
                break
            bb_draw.append(_IDX_TO_RANK[idx])
        if not ok:
            continue

        btn_hand = tuple(sorted(bi.seed + tuple(btn_draw)))
        bb_hand = tuple(sorted(oi.seed + tuple(bb_draw)))

        b0 = bucket_label_fn(btn_hand)
        b1 = bucket_label_fn(bb_hand)

        if b0 != _EXTRA_BUCKET:
            btn_ct[b0] += 1
        if b1 != _EXTRA_BUCKET:
            bb_ct[b1] += 1

    def norm(ct: Counter) -> Dict[str, float]:
        s = float(sum(ct.values()))
        out = {b: 0.0 for b in buckets}
        if s <= 0:
            return out
        for b in buckets:
            out[b] = float(ct.get(b, 0)) / s
        return out

    return {
        "BTN": norm(btn_ct),
        "BB": norm(bb_ct),
    }


# builds the btn vs bb bucket matchup table used by training
def build_bucket_pair_matchups_seedmodel(
    btn_items: List[SeedItem],
    bb_items: List[SeedItem],
    buckets: List[str],
    bucket_label_fn: Callable[[Tuple[int, ...]], str],
    sim_init_freq_n: int,
    discarded_twos: int,
) -> Tuple[List[Matchup], Dict[str, Dict[str, float]]]:
    """
    Build the exact bucket-pair distribution + showdown win/tie/lose rates (for training),
    but return ROOT bucket frequencies computed by SIM (for reporting / UI).
    """
    b2i = {b: i for i, b in enumerate(buckets)}
    nB = len(buckets)

    joint = np.zeros((nB, nB), dtype=float)
    win = np.zeros((nB, nB), dtype=float)
    tie = np.zeros((nB, nB), dtype=float)
    lose = np.zeros((nB, nB), dtype=float)

    s_btn = float(sum(it.weight for it in btn_items))
    s_bb = float(sum(it.weight for it in bb_items))
    if s_btn <= 0 or s_bb <= 0:
        raise RuntimeError("seed weights sum to zero")

    total_mass = 0.0

    _cls_cache: Dict[Tuple[int, ...], Tuple[int, Tuple[int, ...]]] = {}

    def _classify_cached(h: Tuple[int, ...]) -> Tuple[int, Tuple[int, ...]]:
        v = _cls_cache.get(h)
        if v is not None:
            return v
        v = classify_27(h)
        _cls_cache[h] = v
        return v

    def _compare_cached(h1: Tuple[int, ...], h2: Tuple[int, ...]) -> int:
        c1, v1 = _classify_cached(h1)
        c2, v2 = _classify_cached(h2)

        if c1 < c2:
            return +1
        if c1 > c2:
            return -1
        if v1 < v2:
            return +1
        if v1 > v2:
            return -1
        return 0

    for bi in btn_items:
        p_btn_seed = float(bi.weight) / s_btn
        btn_seed = bi.seed

        for oi in bb_items:
            p_bb_seed = float(oi.weight) / s_bb
            bb_seed = oi.seed

            p_seed = p_btn_seed * p_bb_seed
            if p_seed <= 0:
                continue

            counts0 = _counts_after_seeds(
                btn_seed,
                bb_seed,
                discarded_twos=discarded_twos,
            )
            if counts0 is None:
                continue

            btn_out = _draw_outcomes(counts0, bi.draws)
            if not btn_out:
                continue

            for d_btn, p_btn, counts1 in btn_out:
                if p_btn <= 0:
                    continue

                btn_hand = tuple(sorted(btn_seed + d_btn))
                b0 = bucket_label_fn(btn_hand)
                if b0 == _EXTRA_BUCKET:
                    continue
                i0 = b2i.get(b0)
                if i0 is None:
                    continue

                bb_out = _draw_outcomes(counts1, oi.draws)
                if not bb_out:
                    continue

                for d_bb, p_bb, _counts2 in bb_out:
                    if p_bb <= 0:
                        continue

                    bb_hand = tuple(sorted(bb_seed + d_bb))
                    b1 = bucket_label_fn(bb_hand)
                    if b1 == _EXTRA_BUCKET:
                        continue
                    i1 = b2i.get(b1)
                    if i1 is None:
                        continue

                    mass = p_seed * p_btn * p_bb
                    total_mass += mass
                    joint[i0, i1] += mass

                    cmpv = _compare_cached(btn_hand, bb_hand)
                    if cmpv > 0:
                        win[i0, i1] += mass
                    elif cmpv < 0:
                        lose[i0, i1] += mass
                    else:
                        tie[i0, i1] += mass

    if total_mass <= 0:
        raise RuntimeError("bucket-pair mass is zero (check seeds/draws / bucket definition)")

    joint /= total_mass
    win /= total_mass
    tie /= total_mass
    lose /= total_mass

    matchups: List[Matchup] = []
    for i0, b0 in enumerate(buckets):
        for i1, b1 in enumerate(buckets):
            p = float(joint[i0, i1])
            if p <= 0:
                continue
            wp = float(win[i0, i1] / p)
            tp = float(tie[i0, i1] / p)
            lp = float(lose[i0, i1] / p)
            matchups.append(Matchup(b0, b1, p, wp, tp, lp))

    bucket_freq_by_player = estimate_bucket_freqs_sim_seedmodel(
        int(sim_init_freq_n),
        btn_items=btn_items,
        bb_items=bb_items,
        buckets=buckets,
        bucket_label_fn=bucket_label_fn,
        discarded_twos=discarded_twos,
    )

    return matchups, bucket_freq_by_player


# Game-independent CFR primitives (bucket-game)

A_CHECK, A_BET, A_CALL, A_FOLD, A_RAISE = "k", "b", "c", "f", "r"


# helper for this part of the script
class InfoSet:
    __slots__ = ("acts", "regrets", "strat_sum")

    def __init__(self, acts: List[str]):
        self.acts = acts[:]
        self.regrets = np.zeros(len(acts), dtype=float)  # CFR+: clipped at zero
        self.strat_sum = np.zeros(len(acts), dtype=float)

    def rm_plus(self) -> np.ndarray:
        pos = np.maximum(self.regrets, 0.0)
        s = float(pos.sum())
        if s <= 0.0:
            return np.ones(len(pos), dtype=float) / max(1, len(pos))
        return pos / s

    def record_avg_plus(self, probs: np.ndarray, weight: float) -> None:
        if weight <= 0.0:
            return
        self.strat_sum += float(weight) * probs

    def avg_strategy(self) -> np.ndarray:
        s = float(self.strat_sum.sum())
        if s > 0.0:
            out = self.strat_sum / s
            t = float(out.sum())
            if t > 0.0:
                return out / t
        return self.rm_plus()


# helper for this part of the script
def payoff_chip_btn_terminal_bucketgame(
    s,
    m: Matchup,
    root_pot: float,
    root_inv_btn: float,
    root_inv_bb: float,
) -> float:
    dI0 = float(s.invested_btn) - float(root_inv_btn)
    dI1 = float(s.invested_bb) - float(root_inv_bb)

    if getattr(s, "showdown", False):
        win = float(root_pot) + dI1
        lose = -dI0
        tie = 0.5 * float(root_pot) + 0.5 * (dI1 - dI0)
        return float(m.win_p) * win + float(m.lose_p) * lose + float(m.tie_p) * tie

    return (float(root_pot) + dI1) if getattr(s, "winner", None) == 0 else (-dI0)


# helper for this part of the script
def payoff_zero_sum_btn_terminal(
    s,
    m: Matchup,
    root_pot: float,
    root_inv_btn: float,
    root_inv_bb: float,
) -> float:
    return payoff_chip_btn_terminal_bucketgame(
        s, m, root_pot, root_inv_btn, root_inv_bb
    ) - (float(root_pot) / 2.0)


# helper for this part of the script
def terminal_utility(
    s,
    m: Matchup,
    perspective: int,
    root_pot: float,
    root_inv_btn: float,
    root_inv_bb: float,
) -> float:
    u0 = payoff_zero_sum_btn_terminal(s, m, root_pot, root_inv_btn, root_inv_bb)
    return u0 if perspective == 0 else -u0


infosets: Dict[tuple, InfoSet] = {}


# clears the infosets so a fresh run starts cleanly
def reset_infosets() -> None:
    global infosets
    infosets = {}


# helper for this part of the script
def cfr_traverse(
    m: Matchup,
    s,
    r0: float,
    r1: float,
    perspective: int,
    iter_weight: float,
    root_pot: float,
    root_inv_btn: float,
    root_inv_bb: float,
    legal_actions_fn: Callable[[object], List[str]],
    step_fn: Callable[[object, str], object],
    ikey_fn: Callable[[int, str, object], tuple],
) -> float:
    if getattr(s, "terminal", False):
        return terminal_utility(s, m, perspective, root_pot, root_inv_btn, root_inv_bb)

    p = int(s.to_act)
    acts = legal_actions_fn(s)
    if not acts:
        return 0.0

    b = m.btn_bucket if p == 0 else m.bb_bucket
    k = ikey_fn(p, b, s)

    node = infosets.get(k)
    if node is None:
        node = InfoSet(acts)
        infosets[k] = node

    sigma = node.rm_plus()
    utils = np.zeros(len(acts), dtype=float)
    node_util = 0.0

    if p == perspective:
        for i, a in enumerate(acts):
            ns = step_fn(s, a)
            if p == 0:
                utils[i] = cfr_traverse(
                    m, ns, r0 * float(sigma[i]), r1, perspective, iter_weight,
                    root_pot, root_inv_btn, root_inv_bb,
                    legal_actions_fn, step_fn, ikey_fn
                )
            else:
                utils[i] = cfr_traverse(
                    m, ns, r0, r1 * float(sigma[i]), perspective, iter_weight,
                    root_pot, root_inv_btn, root_inv_bb,
                    legal_actions_fn, step_fn, ikey_fn
                )
            node_util += float(sigma[i]) * utils[i]

        opp_reach = r1 if p == 0 else r0
        node.regrets = np.maximum(
            node.regrets + float(opp_reach) * (utils - node_util),
            0.0,
        )
        return float(node_util)

    opp_reach_current = r1 if p == 0 else r0
    if iter_weight > 0.0:
        node.record_avg_plus(sigma, float(iter_weight) * float(opp_reach_current))

    for i, a in enumerate(acts):
        ns = step_fn(s, a)
        if p == 0:
            utils[i] = cfr_traverse(
                m, ns, r0 * float(sigma[i]), r1, perspective, iter_weight,
                root_pot, root_inv_btn, root_inv_bb,
                legal_actions_fn, step_fn, ikey_fn
            )
        else:
            utils[i] = cfr_traverse(
                m, ns, r0, r1 * float(sigma[i]), perspective, iter_weight,
                root_pot, root_inv_btn, root_inv_bb,
                legal_actions_fn, step_fn, ikey_fn
            )
        node_util += float(sigma[i]) * utils[i]

    return float(node_util)


# small helper used by the main parts of the script
def _avg_probs_for_state(
    p: int,
    b: str,
    s,
    legal_actions_fn: Callable[[object], List[str]],
    ikey_fn: Callable[[int, str, object], tuple],
) -> Tuple[List[str], np.ndarray]:
    acts = legal_actions_fn(s)
    node = infosets.get(ikey_fn(p, b, s))
    if node is None:
        return acts, np.ones(len(acts), dtype=float) / max(1, len(acts))

    avg = node.avg_strategy()
    if len(avg) != len(acts):
        return acts, np.ones(len(acts), dtype=float) / max(1, len(acts))

    return acts, avg


# evaluates the state value from the button perspective
def eval_chip_btn(
    m: Matchup,
    s,
    root_pot: float,
    root_inv_btn: float,
    root_inv_bb: float,
    legal_actions_fn: Callable[[object], List[str]],
    step_fn: Callable[[object, str], object],
    ikey_fn: Callable[[int, str, object], tuple],
) -> float:
    if getattr(s, "terminal", False):
        return payoff_chip_btn_terminal_bucketgame(s, m, root_pot, root_inv_btn, root_inv_bb)

    p = int(s.to_act)
    b = m.btn_bucket if p == 0 else m.bb_bucket
    acts, probs = _avg_probs_for_state(p, b, s, legal_actions_fn, ikey_fn)
    if not acts:
        return 0.0

    total = 0.0
    for i, a in enumerate(acts):
        total += float(probs[i]) * eval_chip_btn(
            m,
            step_fn(s, a),
            root_pot,
            root_inv_btn,
            root_inv_bb,
            legal_actions_fn,
            step_fn,
            ikey_fn,
        )
    return float(total)


# helper for this part of the script
def eval_ev_btn(
    root_state,
    matchups: List[Matchup],
    legal_actions_fn: Callable[[object], List[str]],
    step_fn: Callable[[object, str], object],
    ikey_fn: Callable[[int, str, object], tuple],
) -> float:
    root_pot = float(root_state.pot)
    root_inv_btn = float(root_state.invested_btn)
    root_inv_bb = float(root_state.invested_bb)
    return sum(
        float(m.prob) * eval_chip_btn(
            m,
            root_state,
            root_pot,
            root_inv_btn,
            root_inv_bb,
            legal_actions_fn,
            step_fn,
            ikey_fn,
        )
        for m in matchups
    )


# Exact best response / exploitability

def terminal_chip_target(
    s,
    m: Matchup,
    target: int,
    root_pot: float,
    root_inv_btn: float,
    root_inv_bb: float,
) -> float:
    btn_chip = payoff_chip_btn_terminal_bucketgame(s, m, root_pot, root_inv_btn, root_inv_bb)
    return btn_chip if target == 0 else (float(root_pot) - btn_chip)


# small helper used by the main parts of the script
def _exact_br_total(
    s,
    weighted_matchups: List[Tuple[Matchup, float]],
    target: int,
    root_pot: float,
    root_inv_btn: float,
    root_inv_bb: float,
    legal_actions_fn: Callable[[object], List[str]],
    step_fn: Callable[[object, str], object],
    ikey_fn: Callable[[int, str, object], tuple],
) -> float:
    if not weighted_matchups:
        return 0.0

    if getattr(s, "terminal", False):
        total = 0.0
        for m, w in weighted_matchups:
            total += float(w) * terminal_chip_target(
                s, m, target, root_pot, root_inv_btn, root_inv_bb
            )
        return float(total)

    p = int(s.to_act)
    acts = legal_actions_fn(s)
    if not acts:
        return 0.0

    if p == target:
        groups: Dict[str, List[Tuple[Matchup, float]]] = {}
        for m, w in weighted_matchups:
            b = m.btn_bucket if target == 0 else m.bb_bucket
            groups.setdefault(b, []).append((m, float(w)))

        total = 0.0
        for group in groups.values():
            best = None
            for a in acts:
                v = _exact_br_total(
                    step_fn(s, a),
                    group,
                    target,
                    root_pot,
                    root_inv_btn,
                    root_inv_bb,
                    legal_actions_fn,
                    step_fn,
                    ikey_fn,
                )
                if best is None or v > best:
                    best = v
            total += 0.0 if best is None else float(best)
        return float(total)

    child_lists: Dict[str, List[Tuple[Matchup, float]]] = {a: [] for a in acts}
    for m, w in weighted_matchups:
        opp_bucket = m.btn_bucket if p == 0 else m.bb_bucket
        node_acts, probs = _avg_probs_for_state(p, opp_bucket, s, legal_actions_fn, ikey_fn)
        if len(node_acts) != len(acts):
            node_acts = acts
            probs = np.ones(len(acts), dtype=float) / max(1, len(acts))
        for i, a in enumerate(acts):
            pr = float(probs[i])
            if pr > 0.0:
                child_lists[a].append((m, float(w) * pr))

    total = 0.0
    for a in acts:
        child = child_lists[a]
        if child:
            total += _exact_br_total(
                step_fn(s, a),
                child,
                target,
                root_pot,
                root_inv_btn,
                root_inv_bb,
                legal_actions_fn,
                step_fn,
                ikey_fn,
            )
    return float(total)


# helper for this part of the script
def compute_best_response_ev_exact(
    root_state,
    matchups: List[Matchup],
    target: int,
    legal_actions_fn: Callable[[object], List[str]],
    step_fn: Callable[[object, str], object],
    ikey_fn: Callable[[int, str, object], tuple],
) -> Tuple[float, float]:
    root_pot = float(root_state.pot)
    root_inv_btn = float(root_state.invested_btn)
    root_inv_bb = float(root_state.invested_bb)

    weighted = [(m, float(m.prob)) for m in matchups if float(m.prob) > 0.0]
    total_target = _exact_br_total(
        root_state,
        weighted,
        target,
        root_pot,
        root_inv_btn,
        root_inv_bb,
        legal_actions_fn,
        step_fn,
        ikey_fn,
    )

    if target == 0:
        ev_btn = float(total_target)
        ev_bb = float(root_pot) - float(ev_btn)
    else:
        ev_bb = float(total_target)
        ev_btn = float(root_pot) - float(ev_bb)

    return ev_btn, ev_bb


# Training (CFR+ sweep) + TIMING

def should_recalc_exploit_default(it: int, total_iters: int) -> bool:
    if it <= 500:
        return True
    if it <= 10_000:
        return (it % 10 == 0)
    return (it % 100 == 0) or (it == total_iters)


# helper for this part of the script
def should_track_regret_default(it: int, total_iters: int) -> bool:
    return (it % 10 == 0) or (it == total_iters)


# main training loop for the full chance sweep cfr+ run
def train_cfrplus_sweep(
    *,
    matchups: List[Matchup],
    buckets: List[str],
    report_seqs: List[str],
    iterations: int,
    pot: float,
    initial_state_fn: Callable[[float], object],
    state_from_history_fn: Callable[[str, float], object],
    legal_actions_fn: Callable[[object], List[str]],
    step_fn: Callable[[object, str], object],
    ikey_fn: Callable[[int, str, object], tuple],
    avg_delay: int,
    big_blind: float,
    exp_print_step: int,
    stop_expl_mbb: Optional[float] = None,
    dense_expl_below_mbb: Optional[float] = None,
) -> Tuple[
    List[int], dict, dict, dict,
    List[int], List[float], List[float], List[float]
]:
    global infosets

    regret_data: Dict[tuple, Dict[str, List[float]]] = {}
    evo_data: Dict[tuple, Dict[str, List[float]]] = {}
    node_actions: Dict[tuple, List[str]] = {}

    for seq in report_seqs:
        s0 = state_from_history_fn(seq, float(pot))
        if getattr(s0, "terminal", False):
            continue
        p = int(s0.to_act)
        acts = legal_actions_fn(s0)
        for bucket in buckets:
            key = ikey_fn(p, bucket, s0)
            regret_data[key] = {a: [] for a in acts}
            evo_data[key] = {a: [] for a in acts}
            node_actions[key] = acts[:]

    tracked_iters: List[int] = []
    exploit_iters: List[int] = []
    expl_mbb: List[float] = []
    expl_bb: List[float] = []
    expl_chip: List[float] = []

    root = initial_state_fn(float(pot))
    root_pot = float(root.pot)
    root_inv_btn = float(root.invested_btn)
    root_inv_bb = float(root.invested_bb)

    last_chip = 0.0
    last_bb = 0.0
    last_mbb = 0.0

    BB_UNIT = float(big_blind)
    MBB_UNIT = float(big_blind) / 1000.0
    print_step = max(int(iterations) // 5, 1)

    stop_target = None if stop_expl_mbb is None else float(stop_expl_mbb)
    dense_target = None if dense_expl_below_mbb is None else float(dense_expl_below_mbb)

    if stop_target is not None and dense_target is None:
        dense_target = stop_target * 1.25 if stop_target > 0 else 0.0

    if stop_target is not None and dense_target is not None and dense_target < stop_target:
        dense_target = stop_target

    dense_expl_mode = False
    stop_hit = False

    t_start = time.perf_counter()
    t_sweep = 0.0
    t_track = 0.0
    t_expl = 0.0

    for it in range(1, int(iterations) + 1):
        t0 = time.perf_counter()
        iter_weight = float(max(it - int(avg_delay), 0))
        for m in matchups:
            w = float(m.prob)
            if w <= 0.0:
                continue
            cfr_traverse(
                m, root, w, w, 0, iter_weight,
                root_pot, root_inv_btn, root_inv_bb,
                legal_actions_fn, step_fn, ikey_fn
            )
            cfr_traverse(
                m, root, w, w, 1, iter_weight,
                root_pot, root_inv_btn, root_inv_bb,
                legal_actions_fn, step_fn, ikey_fn
            )
        t_sweep += (time.perf_counter() - t0)

        if should_track_regret_default(it, int(iterations)):
            t1 = time.perf_counter()
            tracked_iters.append(it)

            for key, acts in node_actions.items():
                node = infosets.get(key)
                if node is None:
                    uni = 100.0 / max(1, len(acts))
                    for a in acts:
                        regret_data[key][a].append(0.0)
                        evo_data[key][a].append(round(uni, 4))
                    continue

                rd = {a: float(node.regrets[j]) for j, a in enumerate(node.acts)}
                base = node.rm_plus()
                aidx = {a: j for j, a in enumerate(node.acts)}
                for a in acts:
                    regret_data[key][a].append(round(rd.get(a, 0.0), 6))
                    evo_data[key][a].append(round(100.0 * float(base[aidx[a]]), 4))

            t_track += (time.perf_counter() - t1)

        recalc_expl = dense_expl_mode or should_recalc_exploit_default(it, int(iterations))
        if recalc_expl:
            t2 = time.perf_counter()

            ev_btn = eval_ev_btn(root, matchups, legal_actions_fn, step_fn, ikey_fn)
            ev_bb = float(root_pot) - float(ev_btn)

            br_btn_ev_btn, _ = compute_best_response_ev_exact(
                root, matchups, 0, legal_actions_fn, step_fn, ikey_fn
            )
            _, br_bb_ev_bb = compute_best_response_ev_exact(
                root, matchups, 1, legal_actions_fn, step_fn, ikey_fn
            )

            delta_btn = max(0.0, float(br_btn_ev_btn) - float(ev_btn))
            delta_bb = max(0.0, float(br_bb_ev_bb) - float(ev_bb))
            total = 0.5 * (delta_btn + delta_bb)

            last_chip = float(total)
            last_bb = float(total / BB_UNIT) if BB_UNIT > 0.0 else 0.0
            last_mbb = float(total / MBB_UNIT) if MBB_UNIT > 0.0 else 0.0

            exploit_iters.append(it)
            expl_chip.append(abs(last_chip))
            expl_bb.append(abs(last_bb))
            expl_mbb.append(abs(last_mbb))

            t_expl += (time.perf_counter() - t2)

            if (not dense_expl_mode) and dense_target is not None and last_mbb <= dense_target:
                dense_expl_mode = True
                print(
                    f"[INFO] dense exploit checks enabled @ iter {it}: "
                    f"{last_mbb:.6f} mbb/g <= {dense_target:.6f} mbb/g"
                )

            if stop_target is not None and last_mbb <= stop_target:
                stop_hit = True

        if it % print_step == 0 or it == int(iterations):
            elapsed = time.perf_counter() - t_start
            ips = (float(it) / elapsed) if elapsed > 0 else 0.0
            total_t = max(elapsed, 1e-12)
            ps = 100.0 * t_sweep / total_t
            pt = 100.0 * t_track / total_t
            pe = 100.0 * t_expl / total_t
            print(
                f"iter {it:7d}/{int(iterations):,} nodes={len(infosets):6d} "
                f"expl={last_mbb:9.3f} mbb/g | "
                f"{elapsed:8.1f}s ({ips:6.1f} it/s) | "
                f"sweep {t_sweep:7.1f}s ({ps:5.1f}%) "
                f"track {t_track:7.1f}s ({pt:5.1f}%) "
                f"expl {t_expl:7.1f}s ({pe:5.1f}%)"
            )

        if exp_print_step > 0 and recalc_expl and (it % int(exp_print_step) == 0 or it == int(iterations)):
            print(
                f"  exploit snapshot @ {it}: "
                f"{last_chip:.6f} chip | {last_bb:.6f} bb/g | {last_mbb:.3f} mbb/g"
            )

        if stop_hit:
            print(
                f"[STOP] exploitability target reached @ iter {it}: "
                f"{last_mbb:.6f} mbb/g <= {stop_target:.6f} mbb/g"
            )
            break

    elapsed = time.perf_counter() - t_start
    print(f"[TIME] total={elapsed:.2f}s sweep={t_sweep:.2f}s track={t_track:.2f}s expl={t_expl:.2f}s")

    return (
        tracked_iters,
        regret_data,
        evo_data,
        node_actions,
        exploit_iters,
        expl_mbb,
        expl_bb,
        expl_chip,
    )


# EV tables (matchup-conditioned sampling)

class _PrefixSampler:
    __slots__ = ("items", "prefix", "total")

    def __init__(self, items: List[Matchup], weights: List[float]):
        self.items = items
        prefix: List[float] = []
        s = 0.0
        for w in weights:
            s += float(w)
            prefix.append(s)
        self.prefix = prefix
        self.total = s

    def sample(self) -> Matchup:
        if not self.items or self.total <= 0:
            raise RuntimeError("PrefixSampler has no mass/items")
        x = random.random() * self.total
        idx = bisect.bisect_left(self.prefix, x)
        if idx < 0:
            idx = 0
        if idx >= len(self.items):
            idx = len(self.items) - 1
        return self.items[idx]


# builds samplers for each bucket so later ev estimates are faster
def _build_conditional_matchup_samplers(
    matchups: List[Matchup],
    buckets: List[str],
    matchup_weights: Optional[List[float]] = None,
) -> Dict[Tuple[int, str], Optional[_PrefixSampler]]:
    """Samplers keyed by (actor, bucket). If matchup_weights is provided, it aligns with matchups."""
    by_key: Dict[Tuple[int, str], List[Matchup]] = {}
    w_key: Dict[Tuple[int, str], List[float]] = {}

    for b in buckets:
        by_key[(0, b)] = []
        w_key[(0, b)] = []
        by_key[(1, b)] = []
        w_key[(1, b)] = []

    if matchup_weights is not None and len(matchup_weights) != len(matchups):
        raise ValueError("matchup_weights must be None or the same length as matchups")

    for i, m in enumerate(matchups):
        w = float(matchup_weights[i]) if matchup_weights is not None else float(m.prob)
        if w <= 0.0:
            continue
        by_key[(0, m.btn_bucket)].append(m)
        w_key[(0, m.btn_bucket)].append(w)
        by_key[(1, m.bb_bucket)].append(m)
        w_key[(1, m.bb_bucket)].append(w)

    out: Dict[Tuple[int, str], Optional[_PrefixSampler]] = {}
    for k in by_key.keys():
        items = by_key[k]
        ws = w_key[k]
        if not items or sum(ws) <= 0.0:
            out[k] = None
            continue
        out[k] = _PrefixSampler(items, ws)
    return out


# helper for this part of the script
def compute_ev_rows_for_state(
    s0,
    *,
    pot: float,
    buckets: List[str],
    bucket_freq: Dict[str, float],
    matchups: List[Matchup],
    samples_per_bucket: int,
    legal_actions_fn: Callable[[object], List[str]],
    step_fn: Callable[[object, str], object],
    ikey_fn: Callable[[int, str, object], tuple],
    matchup_weights: Optional[List[float]] = None,
) -> dict:
    root_pot = float(s0.pot)
    root_inv_btn = float(s0.invested_btn)
    root_inv_bb = float(s0.invested_bb)

    actor = int(s0.to_act)
    actor_name = "BTN" if actor == 0 else "BB"

    samplers = _build_conditional_matchup_samplers(
        matchups,
        buckets,
        matchup_weights=matchup_weights,
    )

    rows = []
    for b in buckets:
        samp = samplers.get((actor, b))
        rate = round(100.0 * float(bucket_freq.get(b, 0.0)), 6)
        if samp is None:
            rows.append({"bucket": b, "rate": rate, "btn_ev": None, "bb_ev": None, "n": 0})
            continue

        total = 0.0
        for _ in range(int(samples_per_bucket)):
            m = samp.sample()
            total += eval_chip_btn(
                m,
                s0,
                root_pot,
                root_inv_btn,
                root_inv_bb,
                legal_actions_fn,
                step_fn,
                ikey_fn,
            )

        btn_chip = total / float(samples_per_bucket)
        bb_chip = float(root_pot) - float(btn_chip)

        rows.append({
            "bucket": b,
            "rate": rate,
            "btn_ev": round(float(btn_chip), 6),
            "bb_ev": round(float(bb_chip), 6),
            "n": int(samples_per_bucket),
        })

    return {
        "history": getattr(s0, "history", ""),
        "actor": actor_name,
        "pot": float(s0.pot),
        "to_call": float(getattr(s0, "to_call", 0.0)),
        "raises_made": int(getattr(s0, "raises_made", 0)),
        "rows": rows,
    }


# Export helpers

def order_actions_limit(acts: List[str]) -> List[str]:
    if "c" in acts:
        return [a for a in ["c", "f", "r"] if a in acts]
    return [a for a in ["k", "b"] if a in acts]


# helper for this part of the script
def compute_bucket_freq_by_sequence(
    *,
    matchups: List[Matchup],
    buckets: List[str],
    report_seqs: List[str],
    pot: float,
    bucket_freq_by_player: Dict[str, Dict[str, float]],
    initial_state_fn: Callable[[float], object],
    state_from_history_fn: Callable[[str, float], object],
    legal_actions_fn: Callable[[object], List[str]],
    step_fn: Callable[[object, str], object],
    ikey_fn: Callable[[int, str, object], tuple],
) -> Tuple[Dict[str, dict], Dict[str, List[float]]]:
    report_set = set(report_seqs)

    seq_info: Dict[str, dict] = {}
    reach_prob: Dict[str, List[float]] = {seq: [0.0] * len(matchups) for seq in report_seqs}

    for seq in report_seqs:
        s0 = state_from_history_fn(seq, float(pot))
        if getattr(s0, "terminal", False):
            seq_info[seq] = {"terminal": True}
            continue
        actor = "BTN" if int(s0.to_act) == 0 else "BB"
        seq_info[seq] = {
            "actor": actor,
            "bucket_freq": {b: 0.0 for b in buckets},
            "bucket_reach": {b: 0.0 for b in buckets},
            "total_freq": 0.0,
        }

    for i, m in enumerate(matchups):
        root = initial_state_fn(float(pot))

        def walk(s, pr: float) -> None:
            if getattr(s, "terminal", False):
                return

            h = getattr(s, "history", "")
            if h in report_set:
                info = seq_info.get(h)
                if info is not None and not info.get("terminal", False):
                    reach_prob[h][i] += float(pr)
                    actor = info["actor"]
                    b = m.btn_bucket if actor == "BTN" else m.bb_bucket
                    info["bucket_freq"][b] = float(info["bucket_freq"].get(b, 0.0)) + float(m.prob) * float(pr)
                    info["total_freq"] = float(info["total_freq"]) + float(m.prob) * float(pr)

            p = int(s.to_act)
            bucket = m.btn_bucket if p == 0 else m.bb_bucket
            acts = legal_actions_fn(s)
            node = infosets.get(ikey_fn(p, bucket, s))
            if node is None:
                probs = [1.0 / max(1, len(acts))] * len(acts)
            else:
                avg = node.avg_strategy()
                probs = list(avg) if len(avg) == len(acts) else [1.0 / max(1, len(acts))] * len(acts)

            for a, pa in zip(acts, probs):
                pa = float(pa)
                if pa <= 0.0:
                    continue
                walk(step_fn(s, a), float(pr) * pa)

        walk(root, 1.0)

    for seq, info in seq_info.items():
        if info.get("terminal", False):
            continue
        actor = info["actor"]
        marg = bucket_freq_by_player.get(actor, {})
        for b in buckets:
            denom = float(marg.get(b, 0.0))
            num = float(info["bucket_freq"].get(b, 0.0))
            info["bucket_reach"][b] = (num / denom) if denom > 0 else 0.0

    return seq_info, reach_prob


# exports the json files that the plots and frontend use
def export_variant(
    *,
    out_prefix: str,
    pot: float,
    iterations: int,
    buckets: List[str],
    report_seqs: List[str],
    bucket_freq_by_player: Dict[str, Dict[str, float]],
    tracked_iters: List[int],
    regret_data: dict,
    evo_data: dict,
    node_actions: dict,
    exploit_iters: List[int],
    expl_mbb: List[float],
    expl_bb: List[float],
    expl_chip: List[float],
    state_from_history_fn: Callable[[str, float], object],
    legal_actions_fn: Callable[[object], List[str]],
    step_fn: Callable[[object, str], object],
    ikey_fn: Callable[[int, str, object], tuple],
    order_actions_fn: Callable[[List[str]], List[str]],
    matchups: List[Matchup],
    ev_samples_per_bucket: int,
    time_export: bool = False,
) -> None:
    t0 = time.perf_counter() if time_export else 0.0

    out = f"../data/{out_prefix}"
    os.makedirs(out, exist_ok=True)

    buckets = [b for b in buckets if b != _EXTRA_BUCKET]

    with open(f"{out}/bucket_freq_by_player.json", "w", encoding="utf-8") as f:
        json.dump(bucket_freq_by_player, f, indent=2)

    seq_info, reach_prob = compute_bucket_freq_by_sequence(
        matchups=matchups,
        buckets=buckets,
        report_seqs=report_seqs,
        pot=float(pot),
        bucket_freq_by_player=bucket_freq_by_player,
        initial_state_fn=initial_state,
        state_from_history_fn=state_from_history_fn,
        legal_actions_fn=legal_actions_fn,
        step_fn=step_fn,
        ikey_fn=ikey_fn,
    )

    freq_out = {
        "pot": float(pot),
        "bucket_freq_by_player": bucket_freq_by_player,
        "sequences": seq_info,
    }
    with open(f"{out}/bucket_freq_by_sequence_pot{int(pot)}.json", "w", encoding="utf-8") as f:
        json.dump(freq_out, f, indent=2)

    strat_out = {
        "pot": float(pot),
        "iterations": int(iterations),
        "bucket_freq_by_player": bucket_freq_by_player,
        "sequences": {},
    }

    for seq in report_seqs:
        s0 = state_from_history_fn(seq, float(pot))
        if getattr(s0, "terminal", False):
            strat_out["sequences"][seq] = {"terminal": True}
            continue

        p = int(s0.to_act)
        actor = "BTN" if p == 0 else "BB"
        ordered = order_actions_fn(legal_actions_fn(s0))
        freq_map = seq_info.get(seq, {}).get("bucket_freq", {})

        rows = []
        for b in buckets:
            node = infosets.get(ikey_fn(p, b, s0))
            rate = round(100.0 * float(freq_map.get(b, 0.0)), 6)
            if node is None:
                uni = {a: int(round(100 / max(1, len(ordered)))) for a in ordered}
                rows.append({"bucket": b, "rate": rate, **uni})
                continue

            avg = node.avg_strategy()
            am = {a: float(avg[i]) for i, a in enumerate(node.acts)}
            row = {"bucket": b, "rate": rate}
            for a in ordered:
                row[a] = int(round(100.0 * am.get(a, 0.0)))
            rows.append(row)

        sum_rate = sum(float(r.get("rate", 0.0)) for r in rows)
        weighted = {a: 0.0 for a in ordered}
        for row in rows:
            r = float(row.get("rate", 0.0))
            for a in ordered:
                weighted[a] += r * (float(row.get(a, 0.0)) / 100.0)

        if sum_rate > 0.0:
            overall = {a: round((weighted[a] / sum_rate) * 100.0, 4) for a in ordered}
        else:
            overall = {a: 0.0 for a in ordered}

        strat_out["sequences"][seq] = {
            "actor": actor,
            "actions": ordered,
            "overall": overall,
            "rows": rows,
        }

    with open(f"{out}/strategies_pot{int(pot)}.json", "w", encoding="utf-8") as f:
        json.dump(strat_out, f, indent=2)

    reg_out = {"pot": float(pot), "tracked_iterations": tracked_iters, "sequences": {}}
    evo_out = {"pot": float(pot), "tracked_iterations": tracked_iters, "sequences": {}}

    for seq in report_seqs:
        s0 = state_from_history_fn(seq, float(pot))
        if getattr(s0, "terminal", False):
            continue
        p = int(s0.to_act)
        actor = "BTN" if p == 0 else "BB"
        acts = legal_actions_fn(s0)

        reg_out["sequences"][seq] = {"actor": actor, "actions": acts, "buckets": {}}
        evo_out["sequences"][seq] = {"actor": actor, "actions": acts, "buckets": {}}

        for b in buckets:
            key = ikey_fn(p, b, s0)
            reg_out["sequences"][seq]["buckets"][b] = {a: regret_data[key][a] for a in acts}
            evo_out["sequences"][seq]["buckets"][b] = {a: evo_data[key][a] for a in acts}

    with open(f"{out}/regrets_pot{int(pot)}.json", "w", encoding="utf-8") as f:
        json.dump(reg_out, f)

    with open(f"{out}/evolution_pot{int(pot)}.json", "w", encoding="utf-8") as f:
        json.dump(evo_out, f, indent=2)

    ex_out = {
        "tracked_iterations": exploit_iters,
        "exploitability": expl_mbb,
        "exploitability_2": expl_bb,
        "exploitability_3": expl_chip,
    }
    with open(f"{out}/exploitability_pot{int(pot)}.json", "w", encoding="utf-8") as f:
        json.dump(ex_out, f, indent=2)

    ev_out = {"pot": float(pot), "samples_per_bucket": int(ev_samples_per_bucket), "sequences": {}}
    for seq in report_seqs:
        s0 = state_from_history_fn(seq, float(pot))
        if getattr(s0, "terminal", False):
            ev_out["sequences"][seq] = {"terminal": True}
            continue

        pr_list = reach_prob.get(seq, [0.0] * len(matchups))
        w_hist = [float(m.prob) * float(pr_list[i]) for i, m in enumerate(matchups)]
        freq_map = seq_info.get(seq, {}).get("bucket_freq", {})

        ev_out["sequences"][seq] = compute_ev_rows_for_state(
            s0,
            pot=float(pot),
            buckets=buckets,
            bucket_freq=freq_map,
            matchups=matchups,
            samples_per_bucket=int(ev_samples_per_bucket),
            legal_actions_fn=legal_actions_fn,
            step_fn=step_fn,
            ikey_fn=ikey_fn,
            matchup_weights=w_hist,
        )

    with open(f"{out}/ev_pot{int(pot)}.json", "w", encoding="utf-8") as f:
        json.dump(ev_out, f, indent=2)

    if time_export:
        print(f"exported {out_prefix} pot{int(pot)} -> {out}/ | export_time={time.perf_counter() - t0:.2f}s")
    else:
        print(f"exported {out_prefix} pot{int(pot)} -> {out}/")


# Limit betting game definition (1draw)

SEED = 42
ITERATIONS = 50_000
POT_SIZES = [5]

STARTING_PLAYER = 1  # 0=BTN,1=BB

MAX_RAISES = 3
RAISE_SCHEDULE = [1.0, 2.0, 3.0, 4.0]

REPORT_SEQS = ["", "k", "b", "kb", "kbr", "br", "brr", "brrr", "kbrr", "kbrrr"]

BIG_BLIND = 0.5
BR_POLICY_ITERS = 16
EXP_PRINT_STEP = 100
EV_SAMPLES_PER_BUCKET = 800
AVG_DELAY = 250

SIM_INIT_FREQ_N = 200_000
DISCARDED_TWOS = 0

# BTN seeds: only seeds containing a 2
seeds_with_2 = [
    "2345", "2346", "2347", "2348", "2349",
    "2345", "2356", "2357", "2358", "2359",
    "2345", "2456", "2457", "2458", "2459",
    "2345", "2458",
    "2346", "2356", "2367", "2368", "2369",
    "2346", "2456", "2467", "2468", "2469",
    "2346",
    "2356", "2456", "2567", "2568", "2569",
    "2356",
    "2347", "2357", "2367", "2378", "2379",
    "2347", "2457", "2467", "2478", "2479",
    "2347",
    "2357", "2457", "2567", "2578", "2579",
    "2357",
    "2457",
    "2367", "2467", "2567", "2678", "2679",
    "2367",
    "2348", "2358", "2368", "2378", "2389",
    "2348", "2458", "2468", "2478", "2489",
    "2348",
    "2358", "2458", "2568", "2578", "2589",
    "2358",
    "2458",
    "2368", "2468", "2568", "2678", "2689",
    "2368",
    "2468",
    "2568",
]
btn_grid = [seeds_with_2]

# BB normal range grid
bb_grid = [
    ["2345", "3456", "3457", "2458", "3459"],
    ["2346", "3456", "3467", "3468", "3469"],
    ["2356", "2456", "2567", "2568", "2569"],
    ["2356", "3456", "3567", "3568", "3569"],
    ["2357", "3457", "3567", "3578", "3579"],
    ["2457", "3457", "4567", "4578", "4579"],
    ["2367", "2467", "2567", "2678", "2679"],
    ["2367", "3467", "3567", "3678", "3679"],
    ["2348", "2358", "2368", "2378", "2389"],
    ["2348", "2458", "2468", "2478", "2489"],
    ["2348", "3458", "3468", "3478", "3489"],
    ["2358", "2458", "2568", "2578", "2589"],
    ["2358", "3458", "3568", "3578", "3589"],
    ["2458", "3458", "4568", "4578", "4589"],
    ["2368", "2468", "2568", "2678", "2689"],
    ["2368", "3468", "3568", "3678", "3689"],
    ["2468", "3468", "4568", "4678", "4689"],
    ["2568", "3568", "4568", "5678", "5689"],
]

# BB grid used only when discarded_twos == 3.
# The raw list you gave still had some 2-containing seeds in it,
# so we sanitize those out below instead of pretending it was already correct.
bb_grid_without_2_raw = [
    ["3456", "3457", "3459"],

    ["3456", "3467", "3468", "3469"],
    ["2567", "2568", "2569"],
    ["3456", "3567", "3568", "3569"],

    ["3457", "3567", "3578", "3579"],
    ["3457", "4567", "4578", "4579"],
    ["2678", "2679"],
    ["3467", "3567", "3678", "3679"],

    ["3458", "3468", "3478", "3489"],
    ["2568", "2578", "2589"],
    ["3458", "3568", "3578", "3589"],
    ["3458", "4568", "4578", "4589"],
    ["3678", "3689"],
    ["3468", "3568", "3678", "3689"],
    ["3468", "4568", "4678", "4689"],
    ["3568", "4568", "5678", "5689"],
]

bb_grid_without_2 = [
    [h for h in row if "2" not in h]
    for row in bb_grid_without_2_raw
]


@dataclass
# helper for this part of the script
class State:
    to_act: int
    history: str
    pot: float
    to_call: float
    raises_made: int
    terminal: bool
    winner: Optional[int]
    showdown: bool
    invested_btn: float
    invested_bb: float


# creates the starting state for the no-limit tree
def initial_state(start_pot: float) -> State:
    return State(
        to_act=STARTING_PLAYER,
        history="",
        pot=float(start_pot),
        to_call=0.0,
        raises_made=0,
        terminal=False,
        winner=None,
        showdown=False,
        invested_btn=0.0,
        invested_bb=0.0,
    )


# returns the legal actions for the current state
def legal_actions(s: State) -> List[str]:
    if s.terminal:
        return []
    if s.to_call == 0:
        return [A_CHECK, A_BET]
    acts = [A_FOLD, A_CALL]
    if s.raises_made < MAX_RAISES:
        acts.append(A_RAISE)
    return acts


# small helper used by the main parts of the script
def _add_invested(st: State, player: int, amt: float) -> None:
    if player == 0:
        st.invested_btn += amt
    else:
        st.invested_bb += amt


# helper for this part of the script
def step(s: State, a: str) -> State:
    t = State(**vars(s))
    t.history += a
    p, opp = s.to_act, 1 - s.to_act

    if s.to_call == 0:
        if a == A_CHECK:
            if t.history.endswith("kk"):
                t.terminal = True
                t.showdown = True
            else:
                t.to_act = opp
        elif a == A_BET:
            amt = float(RAISE_SCHEDULE[0])
            t.pot += amt
            _add_invested(t, p, amt)
            t.to_call = amt
            t.raises_made = 0
            t.to_act = opp
    else:
        if a == A_FOLD:
            t.terminal = True
            t.winner = opp
        elif a == A_CALL:
            t.pot += s.to_call
            _add_invested(t, p, s.to_call)
            t.to_call = 0.0
            t.terminal = True
            t.showdown = True
        elif a == A_RAISE:
            newlvl = float(RAISE_SCHEDULE[s.raises_made + 1])
            curr = t.invested_btn if p == 0 else t.invested_bb
            oppi = t.invested_bb if p == 0 else t.invested_btn
            add = newlvl - curr
            t.pot += add
            _add_invested(t, p, add)
            t.to_call = newlvl - oppi
            t.raises_made = s.raises_made + 1
            t.to_act = opp

    return t


# helper for this part of the script
def state_from_history(h: str, start_pot: float) -> State:
    s = initial_state(start_pot)
    for ch in h:
        s = step(s, ch)
    return s


# helper for this part of the script
def ikey(p: int, bucket: str, s: State) -> tuple:
    base = (p, bucket, s.history, s.to_call, s.raises_made)

    # Only BTN conditions on discarded_twos.
    # BB infosets do NOT include it.
    if p == 0:
        return base + (DISCARDED_TWOS,)

    return base


# helper for this part of the script
def info_key_str(s: State) -> str:
    return f"h:{s.history}|tc:{s.to_call}|rm:{s.raises_made}"


# main

def main():
    global SEED, ITERATIONS, BR_POLICY_ITERS, EXP_PRINT_STEP, EV_SAMPLES_PER_BUCKET
    global AVG_DELAY, POT_SIZES, SIM_INIT_FREQ_N, DISCARDED_TWOS

    ap = argparse.ArgumentParser(description="CFR+ 1draw standalone (FULL chance sweep bucket-game)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--iters", "--iterations", dest="iters", type=int, default=ITERATIONS)
    ap.add_argument("--pots", type=str, default=",".join(str(x) for x in POT_SIZES))
    ap.add_argument("--out-prefix", type=str, default="cfr_rem")
    ap.add_argument(
        "--br-policy-iters",
        type=int,
        default=BR_POLICY_ITERS,
        help="Ignored for this standalone file; exploitability uses exact BR now.",
    )
    ap.add_argument("--exp-print-step", type=int, default=EXP_PRINT_STEP)
    ap.add_argument("--ev-samples", type=int, default=EV_SAMPLES_PER_BUCKET)
    ap.add_argument(
        "--avg-delay",
        type=int,
        default=AVG_DELAY,
        help="CFR+ averaging delay d; strategy weight uses max(t-d, 0).",
    )
    ap.add_argument(
        "--sim-init-freq-n",
        type=int,
        default=SIM_INIT_FREQ_N,
        help="MC sims for root bucket freqs",
    )
    ap.add_argument("--time-export", action="store_true", help="time export wall-clock")
    ap.add_argument("--time-total", action="store_true", help="print total script runtime at end")

    # updated: comma-separated values supported
    ap.add_argument(
        "--discarded-twos",
        type=str,
        default=str(DISCARDED_TWOS),
        help="Comma-separated discarded_twos values to run, e.g. 1,2,3",
    )

    ap.add_argument(
        "--stop-expl-mbb",
        type=float,
        default=None,
        help="Stop once exploitability (mbb/g) is <= this value.",
    )
    ap.add_argument(
        "--dense-expl-below-mbb",
        type=float,
        default=None,
        help="Once exploitability (mbb/g) is <= this value, recompute exploitability every iteration.",
    )

    args = ap.parse_args()

    t_all0 = time.perf_counter()

    SEED = int(args.seed)
    ITERATIONS = int(args.iters)
    BR_POLICY_ITERS = int(args.br_policy_iters)
    EXP_PRINT_STEP = int(args.exp_print_step)
    EV_SAMPLES_PER_BUCKET = int(args.ev_samples)
    AVG_DELAY = int(args.avg_delay)
    SIM_INIT_FREQ_N = int(args.sim_init_freq_n)

    pots = []
    for tok in str(args.pots).split(","):
        tok = tok.strip()
        if tok:
            pots.append(float(tok))
    POT_SIZES = pots if pots else POT_SIZES

    # updated: parse multiple discarded_twos values
    discarded_twos_list: List[int] = []
    for tok in str(args.discarded_twos).split(","):
        tok = tok.strip()
        if not tok:
            continue
        v = int(tok)
        if not (0 <= v <= 3):
            raise ValueError(f"--discarded-twos values must be between 0 and 3, got {v}")
        discarded_twos_list.append(v)

    if not discarded_twos_list:
        raise ValueError("No valid --discarded-twos values provided")

    random.seed(SEED)
    np.random.seed(SEED)

    print(
        f"1draw CFR+ FULL: iters={ITERATIONS:,} seed={SEED} BB={BIG_BLIND} avg_delay={AVG_DELAY} "
        f"out={args.out_prefix} discarded_twos={discarded_twos_list} "
        f"stop_expl_mbb={args.stop_expl_mbb} "
        f"dense_expl_below_mbb={args.dense_expl_below_mbb}"
    )
    print(f"root freq sims: {SIM_INIT_FREQ_N:,}")

    # run sequentially for each discarded_twos value
    for discarded_twos in discarded_twos_list:
        DISCARDED_TWOS = discarded_twos

        print("\n" + "=" * 70)
        print(f"RUNNING discarded_twos={DISCARDED_TWOS}")
        print("=" * 70)

        btn_seeds, btn_w = build_unique_seeds_and_weights_from_grid(btn_grid)
        btn_seeds, btn_w = filter_to_seeds_containing_rank(btn_seeds, btn_w, 2)

        selected_bb_grid = bb_grid_without_2 if DISCARDED_TWOS == 3 else bb_grid
        bb_seeds, bb_w = build_unique_seeds_and_weights_from_grid(selected_bb_grid)

        # Safety cleanup for the discarded_twos == 3 case.
        if DISCARDED_TWOS == 3:
            bb_seeds, bb_w = filter_out_seeds_containing_rank(bb_seeds, bb_w, 2)

        btn_items = [SeedItem(seed=s, draws=1, weight=float(w)) for s, w in zip(btn_seeds, btn_w)]
        bb_items = [SeedItem(seed=s, draws=1, weight=float(w)) for s, w in zip(bb_seeds, bb_w)]

        print(f"unique BTN seeds (all containing a 2): {len(btn_seeds)}")
        if DISCARDED_TWOS == 3:
            print(f"unique BB seeds (using no-2 grid because discarded_twos=3): {len(bb_seeds)}")
        else:
            print(f"unique BB seeds (using normal BB grid): {len(bb_seeds)}")

        print("building bucket-pair chance distribution (exact draw1)...")
        matchups, bucket_freq_by_player = build_bucket_pair_matchups_seedmodel(
            btn_items,
            bb_items,
            BUCKETS_1DRAW,
            bucket_label_1draw,
            SIM_INIT_FREQ_N,
            discarded_twos=DISCARDED_TWOS,
        )
        print(f"done: {len(matchups)} nonzero bucket-pairs")

        run_out_prefix = f"{args.out_prefix}_{DISCARDED_TWOS}"

        for pot in POT_SIZES:
            print(f"\npot={pot} | discarded_twos={DISCARDED_TWOS}")
            random.seed(SEED)
            np.random.seed(SEED)
            reset_infosets()

            tracked_iters, regret_data, evo_data, node_actions, ex_i, ex_mbb, ex_bb, ex_chip = train_cfrplus_sweep(
                matchups=matchups,
                buckets=BUCKETS_1DRAW,
                report_seqs=REPORT_SEQS,
                iterations=ITERATIONS,
                pot=float(pot),
                initial_state_fn=initial_state,
                state_from_history_fn=state_from_history,
                legal_actions_fn=legal_actions,
                step_fn=step,
                ikey_fn=ikey,
                avg_delay=AVG_DELAY,
                big_blind=BIG_BLIND,
                exp_print_step=EXP_PRINT_STEP,
                stop_expl_mbb=args.stop_expl_mbb,
                dense_expl_below_mbb=args.dense_expl_below_mbb,
            )

            actual_iterations = ex_i[-1] if ex_i else 0

            export_variant(
                out_prefix=run_out_prefix,
                pot=float(pot),
                iterations=actual_iterations,
                buckets=BUCKETS_1DRAW,
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
                state_from_history_fn=state_from_history,
                legal_actions_fn=legal_actions,
                step_fn=step,
                ikey_fn=ikey,
                order_actions_fn=order_actions_limit,
                matchups=matchups,
                ev_samples_per_bucket=EV_SAMPLES_PER_BUCKET,
                time_export=bool(args.time_export),
            )

    print("\n1draw CFR+ done!")
    if args.time_total:
        print(f"[TIME] script_total={time.perf_counter() - t_all0:.2f}s")


if __name__ == "__main__":
    main()
