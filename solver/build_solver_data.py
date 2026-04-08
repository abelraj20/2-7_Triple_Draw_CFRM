#!/usr/bin/env python3
# this is the code for building the frontend solver data

from __future__ import annotations

import argparse
import json
import re
import tempfile
from html import escape
from pathlib import Path
from typing import Optional

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA_DIR = ROOT / "data"
JS_DIR = ROOT / "frontend" / "js"

VARIANTS = {
    "1draw": {"prefix": "1draw"},
    "1draw_bb": {"prefix": "1draw_bb"},
    "2draw": {"prefix": "2draw"},
    "nl": {"prefix": "nl"},
    "cfr_rem_0": {"prefix": "cfr_rem_0"},
    "cfr_rem_1": {"prefix": "cfr_rem_1"},
    "cfr_rem_2": {"prefix": "cfr_rem_2"},
    "cfr_rem_3": {"prefix": "cfr_rem_3"},
}

POT_RE = re.compile(r"_pot(\d+)\.json$")

DEFAULT_BUCKET_ORDER = [
    "75", "76", "85", "86", "87", "95", "96", "97", "98",
    "T5", "T6", "T7", "T8", "T9",
    "J8", "J9", "Q", "K", "A",
    "22", "33", "44", "55", "66", "77", "88", "99",
    "TT", "JJ", "QQ", "KK", "AA",
    "2-Pair", "Trips", "Str.", "Straight",
]

HIDDEN_BUCKETS = {"2-Pair", "Trips", "Extra"}


# helper for this part of the script
def is_hidden_bucket(bucket: object) -> bool:
    return str(bucket) in HIDDEN_BUCKETS

ACTION_COLOR_CLASS = {
    "k": "color-check",
    "c": "color-call",
    "f": "color-fold",
    "b": "color-bet",
    "r": "color-raise",
    "b40": "color-b40",
    "b80": "color-b80",
    "b120": "color-b120",
    "ba": "color-ba",
    "r86": "color-r86",
    "r111": "color-r111",
    "ra": "color-ra",
}

ACTION_LABELS = {
    "k": "Check",
    "c": "Call",
    "f": "Fold",
    "b": "Bet",
    "r": "Raise",
    "b40": "Bet 40%",
    "b80": "Bet 80%",
    "b120": "Bet 120%",
    "ba": "All-in",
    "r86": "Raise 86%",
    "r111": "Raise 111%",
    "ra": "All-in",
}

FRONTEND_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body {
  width: 100%;
  height: auto;
}
body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background: #16213e;
  color: #e0e0e0;
}
.capture-root {
  display: inline-block;
  background: #16213e;
}
.panel {
  width: 100%;
  background: #16213e;
  color: #e0e0e0;
  padding: 0;
}
.freq-bar-container {
  display: flex;
  width: 100%;
  height: 60px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #444;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.freq-bar-segment {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4px 8px;
  border-right: 1px solid rgba(0,0,0,0.3);
  min-width: 0;
  gap: 2px;
}
.freq-bar-segment:last-child { border-right: none; }
.freq-label {
  font-size: 12px;
  font-weight: 600;
  color: rgb(255, 255, 255);
  text-shadow: 0 1px 0 rgb(0, 0, 0);
  white-space: nowrap;
  overflow: hidden;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.freq-pct {
  font-size: 22px;
  font-weight: 600;
  color: rgb(255, 255, 255);
  text-shadow: 0 1px 0 rgb(0, 0, 0);
}
.color-fold { background: #87CEEB; }
.color-check { background: #93ee90; }
.color-call { background: #93ee90; }
.color-bet { background: #DC143C; }
.color-raise { background: #DC143C; }
.color-b40 { background: #FFB6C1; }
.color-b80 { background: #FF6B6B; }
.color-b120 { background: #DC143C; }
.color-ba { background: #8B0000; }
.color-r86 { background: #FF6B6B; }
.color-r111 { background: #DC143C; }
.color-ra { background: #8B0000; }
.strategy-wrap {
  margin-top: 12px;
}
.strategy-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  table-layout: fixed;
}
.strategy-table th {
  background: #0f3460;
  text-transform: none;
  font-size: 12px;
  letter-spacing: 0.2px;
  color: #ffffff;
  padding: 6px 4px;
  border-bottom: 2px solid #e94560;
  text-align: center;
  font-family: inherit;
  font-weight: 800;
}
.strategy-table td {
  padding: 3px 4px;
  border-bottom: 1px solid #0f3460;
  vertical-align: middle;
  height: 28px;
  overflow: hidden;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.strategy-table th.col-strategy,
.strategy-table td.col-strategy {
  width: 56%;
}
.strategy-table th.col-rate,
.strategy-table td.col-rate {
  width: 14%;
}
.strategy-table td.col-rate {
  font-size: 12px;
  font-weight: 700;
  font-family: inherit;
}
.strategy-table th.col-ev-btn,
.strategy-table td.col-ev-btn {
  width: 15%;
}
.strategy-table th.col-ev-bb,
.strategy-table td.col-ev-bb {
  width: 15%;
}
.bucket-strategy-cell {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  width: 100%;
}
.bucket-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 54px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(15, 52, 96, 0.65);
  border: 1px solid rgba(233, 69, 96, 0.25);
  color: #4fc3f7;
  font-weight: 800;
  letter-spacing: 0.2px;
  font-size: 11px;
  line-height: 1;
  flex-shrink: 0;
}
.strategy-bar {
  display: flex;
  height: 20px;
  border-radius: 3px;
  overflow: hidden;
  background: rgba(255,255,255,0.1);
  width: 200px;
  flex: 0 0 200px;
}
.bar-segment {
  height: 100%;
}
.ev-positive { color: #4caf50; font-weight: 800; }
.ev-negative { color: #e94560; font-weight: 800; }
.ev-zero { color: #888; }
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #888;
  font-size: 12px;
  border: 1px solid #0f3460;
  padding: 20px;
}
"""

LAYOUT_PRESETS = {
    "full": {
        "show_overall": True,
        "show_rate": True,
        "show_btn_ev": True,
        "show_bb_ev": True,
        "width": 980,
    },
    "bucket-rate": {
        "show_overall": True,
        "show_rate": True,
        "show_btn_ev": False,
        "show_bb_ev": False,
        "width": 620,
    },
    "bucket-rate-no-overall": {
        "show_overall": False,
        "show_rate": True,
        "show_btn_ev": False,
        "show_bb_ev": False,
        "width": 620,
    },
    "bars-only": {
        "show_overall": True,
        "show_rate": False,
        "show_btn_ev": False,
        "show_bb_ev": False,
        "width": 560,
    },
}


# gets the bit of data needed here
def get_layout_config(layout_name: str) -> dict:
    if layout_name not in LAYOUT_PRESETS:
        raise ValueError(f"unknown layout: {layout_name}")
    return dict(LAYOUT_PRESETS[layout_name])


# helper for this part of the script
def load_if_exists(path: Path) -> Optional[dict]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  warning: failed to load {p}: {e}")
        return None


# helper for this part of the script
def detect_pots_in_folder(sub: Path) -> list[int]:
    if not sub.exists():
        return []
    pots = set()
    for p in sub.glob("*.json"):
        m = POT_RE.search(p.name)
        if m:
            pots.add(int(m.group(1)))
    return sorted(pots)


# helper for this part of the script
def normalize_exploitability(exp: dict) -> dict:
    if not isinstance(exp, dict):
        return exp

    out = dict(exp)

    if "exploitability" in out:
        out.setdefault("exploitability_2", [])
        out.setdefault("exploitability_3", [])
        return out

    if "exploitability_mbb_per_g" in out:
        out["exploitability"] = out.pop("exploitability_mbb_per_g")
        out.setdefault("exploitability_2", [])
        out.setdefault("exploitability_3", [])
        return out

    return out


# helper for this part of the script
def ev_meta_from_ev_json(ev: dict) -> dict:
    if not isinstance(ev, dict):
        return {"has_full_data": False}

    sequences = ev.get("sequences", {})
    seqs = list(sequences.keys()) if isinstance(sequences, dict) else []

    return {
        "pot": ev.get("pot"),
        "samples_per_bucket": ev.get("samples_per_bucket"),
        "sequences": seqs,
        "has_full_data": True,
    }


# small helper used by the main parts of the script
def _first_existing(paths: list[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists():
            return p
    return None


# helper for this part of the script
def action_sort_key(act: str) -> tuple[int, str]:
    if not isinstance(act, str):
        return (9999, str(act))

    if act in ("check", "k"):
        return (10, act)
    if act in ("bet", "b"):
        return (20, act)
    if act == "b40":
        return (21, act)
    if act == "b80":
        return (22, act)
    if act == "b120":
        return (23, act)
    if act == "ba":
        return (24, act)
    if act in ("call", "c"):
        return (30, act)
    if act in ("fold", "f"):
        return (40, act)
    if act in ("raise", "r"):
        return (50, act)
    if act == "r86":
        return (51, act)
    if act == "r111":
        return (52, act)
    if act == "ra":
        return (53, act)
    if re.fullmatch(r"b\d+", act):
        return (25, act)
    if re.fullmatch(r"r\d+", act):
        return (54, act)

    return (9999, act)


# helper for this part of the script
def sort_actions(actions: list[str]) -> list[str]:
    return sorted(actions, key=action_sort_key)


# helper for this part of the script
def reorder_action_dict(d: dict, actions: list[str]) -> dict:
    if not isinstance(d, dict):
        return d

    out = {}
    for a in actions:
        if a in d:
            out[a] = d[a]

    for k, v in d.items():
        if k not in out:
            out[k] = v

    return out


# helper for this part of the script
def normalize_strategies_json(strat: dict) -> dict:
    if not isinstance(strat, dict):
        return strat

    out = dict(strat)
    sequences = out.get("sequences")
    if not isinstance(sequences, dict):
        return out

    new_sequences = {}
    for seq_name, seq_data in sequences.items():
        if not isinstance(seq_data, dict):
            new_sequences[seq_name] = seq_data
            continue

        seq_out = dict(seq_data)
        actions = seq_data.get("actions", [])
        if isinstance(actions, list):
            actions = sort_actions(actions)
            seq_out["actions"] = actions

            overall = seq_data.get("overall")
            if isinstance(overall, dict):
                seq_out["overall"] = reorder_action_dict(overall, actions)

            rows = seq_data.get("rows")
            if isinstance(rows, list):
                new_rows = []
                for row in rows:
                    if not isinstance(row, dict):
                        new_rows.append(row)
                        continue

                    row_out = {}
                    if "bucket" in row:
                        row_out["bucket"] = row["bucket"]
                    if "rate" in row:
                        row_out["rate"] = row["rate"]
                    for a in actions:
                        if a in row:
                            row_out[a] = row[a]
                    for k, v in row.items():
                        if k not in row_out:
                            row_out[k] = v
                    new_rows.append(row_out)
                seq_out["rows"] = new_rows

        new_sequences[seq_name] = seq_out

    out["sequences"] = new_sequences
    return out


# helper for this part of the script
def collect_pot_data(sub: Path, pot: Optional[int], include_ev: bool = True) -> dict:
    if pot is not None:
        pot_key = str(pot)
        strat_candidates = [
            sub / f"strategies_pot{pot}.json",
            sub / f"strategy_pot{pot}.json",
            sub / f"strategies_{pot}.json",
        ]
        exp_candidates = [sub / f"exploitability_pot{pot}.json", sub / f"exploit_pot{pot}.json"]
        reg_candidates = [sub / f"regrets_pot{pot}.json"]
        evo_candidates = [sub / f"evolution_pot{pot}.json"]
        ev_candidates = [sub / f"ev_pot{pot}.json"]
        freqseq_candidates = [sub / f"bucket_freq_by_sequence_pot{pot}.json"]
    else:
        pot_key = "default"
        strat_candidates = [sub / "strategies.json", sub / "strategy.json"]
        exp_candidates = [sub / "exploitability.json", sub / "exploit.json"]
        reg_candidates = [sub / "regrets.json"]
        evo_candidates = [sub / "evolution.json"]
        ev_candidates = [sub / "ev.json"]
        freqseq_candidates = [sub / "bucket_freq_by_sequence.json"]

    pot_data: dict = {}

    sp = _first_existing(strat_candidates)
    if sp:
        strat = load_if_exists(sp)
        if strat:
            pot_data["strategies"] = normalize_strategies_json(strat)

    rp = _first_existing(reg_candidates)
    if rp:
        reg = load_if_exists(rp)
        if reg:
            seqs = reg.get("sequences", {})
            pot_data["regrets_meta"] = {
                "tracked_iterations": reg.get("tracked_iterations", []),
                "sequences": list(seqs.keys()) if isinstance(seqs, dict) else [],
                "has_full_data": True,
            }

    ep = _first_existing(evo_candidates)
    if ep:
        evo = load_if_exists(ep)
        if evo:
            seqs = evo.get("sequences", {})
            pot_data["evolution_meta"] = {
                "tracked_iterations": evo.get("tracked_iterations", []),
                "sequences": list(seqs.keys()) if isinstance(seqs, dict) else [],
                "has_full_data": True,
            }

    xp = _first_existing(exp_candidates)
    if xp:
        exp = load_if_exists(xp)
        if exp:
            pot_data["exploitability"] = normalize_exploitability(exp)

    vp = _first_existing(ev_candidates)
    if vp:
        ev = load_if_exists(vp)
        if ev:
            pot_data["ev_meta"] = ev_meta_from_ev_json(ev)
            if include_ev:
                pot_data["ev"] = ev

    fp = _first_existing(freqseq_candidates)
    if fp:
        freqseq = load_if_exists(fp)
        if freqseq:
            pot_data["bucket_freq_by_sequence"] = freqseq

    return {pot_key: pot_data} if pot_data else {}


# helper for this part of the script
def collect_variant(variant: str, cfg: dict, include_ev: bool = True) -> Optional[dict]:
    prefix = cfg["prefix"]
    sub = DATA_DIR / prefix

    if not sub.exists():
        return None

    result: dict = {"variant": variant, "pots": {}}

    freq_old = load_if_exists(sub / "bucket_freq.json")
    freq_by_player = load_if_exists(sub / "bucket_freq_by_player.json")
    if freq_old:
        result["bucket_freq"] = freq_old
    if freq_by_player:
        result["bucket_freq_by_player"] = freq_by_player

    detected_pots = detect_pots_in_folder(sub)

    if detected_pots:
        for pot in detected_pots:
            result["pots"].update(collect_pot_data(sub, pot, include_ev))
    else:
        result["pots"].update(collect_pot_data(sub, None, include_ev))

    return result if result["pots"] else None


# gets the bit of data needed here
def get_action_color_class(act: str) -> str:
    if act in ACTION_COLOR_CLASS:
        return ACTION_COLOR_CLASS[act]
    if isinstance(act, str):
        if act in ("check", "k"):
            return "color-check"
        if act in ("call", "c"):
            return "color-call"
        if act in ("fold", "f"):
            return "color-fold"
        if act and act[0] == "b":
            return "color-bet"
        if act and act[0] == "r":
            return "color-raise"
    return "color-call"


# gets the bit of data needed here
def get_action_label(act: str) -> str:
    if act in ACTION_LABELS:
        return ACTION_LABELS[act]
    if isinstance(act, str):
        if act == "check":
            return "Check"
        if act == "call":
            return "Call"
        if act == "fold":
            return "Fold"
        if act == "bet":
            return "Bet"
        if act == "raise":
            return "Raise"
        if act in ("ba", "ra"):
            return "All-in"
        if act.startswith("b") and act[1:].isdigit():
            return f"Bet {act[1:]}%"
        if act.startswith("r") and act[1:].isdigit():
            return f"Raise {act[1:]}%"
    return str(act)


# gets the bit of data needed here
def get_display_actions(actions: list[str]) -> list[str]:
    return sort_actions(list(actions or []))


# helper for this part of the script
def apply_freqseq_to_seq_data(seq_data: dict, freq_seq: Optional[dict]) -> dict:
    if not seq_data or not seq_data.get("rows") or not freq_seq or not freq_seq.get("bucket_freq"):
        return seq_data

    total_freq = float(freq_seq.get("total_freq") or 0.0)
    out = dict(seq_data)
    out_rows = []
    for row in seq_data["rows"]:
        rr = dict(row)
        bucket = rr.get("bucket")
        if bucket in freq_seq["bucket_freq"]:
            mass = float(freq_seq["bucket_freq"][bucket])
            rr["rate"] = (mass / total_freq) * 100.0 if total_freq > 0 else 0.0
        out_rows.append(rr)
    out["rows"] = out_rows
    return out


# helper for this part of the script
def compute_overall_from_rows(seq_data: dict) -> dict[str, float]:
    if not seq_data or not seq_data.get("rows"):
        return {}

    actions = get_display_actions(seq_data.get("actions", []))
    sum_rate = 0.0
    totals: dict[str, float] = {}

    for row in seq_data["rows"]:
        w = float(row.get("rate") or 0.0)
        sum_rate += w
        for a in actions:
            p = float(row.get(a) or 0.0)
            totals[a] = totals.get(a, 0.0) + (w * p / 100.0)

    if sum_rate <= 0:
        return {a: 0.0 for a in actions}
    return {a: (totals.get(a, 0.0) / sum_rate) * 100.0 for a in actions}


# gets the bit of data needed here
def get_bucket_order(seq_data: dict) -> list[str]:
    buckets = []
    for row in seq_data.get("rows", []):
        if isinstance(row, dict) and row.get("bucket") and not is_hidden_bucket(row["bucket"]):
            buckets.append(row["bucket"])

    if not buckets:
        return [b for b in DEFAULT_BUCKET_ORDER if not is_hidden_bucket(b)]

    seen = set()
    uniq = []
    for b in buckets:
        if b not in seen:
            seen.add(b)
            uniq.append(b)

    canon = {b: i for i, b in enumerate(DEFAULT_BUCKET_ORDER)}
    uniq.sort(key=lambda b: (canon.get(b, 100000), str(b)))
    return uniq


# builds one part of the data or output pipeline
def build_ev_map(ev_seq: Optional[dict]) -> dict:
    if not ev_seq or not isinstance(ev_seq.get("rows"), list):
        return {}
    out = {}
    for row in ev_seq["rows"]:
        if isinstance(row, dict) and row.get("bucket") is not None:
            out[row["bucket"]] = row
    return out


# helper for this part of the script
def safe_filename(name: str) -> str:
    if not name:
        return "start"
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", str(name)).strip("-._")
    return name or "start"


# helper for this part of the script
def format_ev_cell(value: object) -> tuple[str, str]:
    if value is None or value == "":
        return "-", "ev-zero"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "-", "ev-zero"
    if v > 0:
        cls = "ev-positive"
    elif v < 0:
        cls = "ev-negative"
    else:
        cls = "ev-zero"
    return f"{v:.3f}", cls


# helper for this part of the script
def render_overall_html(overall: dict[str, float], actions: list[str]) -> str:
    if not actions:
        return (
            '<div class="freq-bar-container">'
            '<div class="freq-bar-segment color-check" style="width:100%">'
            '<span class="freq-label">No data</span>'
            '<span class="freq-pct">-</span>'
            '</div></div>'
        )

    equal_width = 100.0 / max(len(actions), 1)
    segs = []
    for act in actions:
        pct = float(overall.get(act, 0.0))
        segs.append(
            f'<div class="freq-bar-segment {escape(get_action_color_class(act))}" '
            f'style="width:{equal_width:.8f}%">'
            f'<span class="freq-label">{escape(get_action_label(act))}</span>'
            f'<span class="freq-pct">{pct:.1f}%</span>'
            '</div>'
        )
    return '<div class="freq-bar-container">' + ''.join(segs) + '</div>'


# helper for this part of the script
def render_table_html(seq_data: dict, ev_seq: Optional[dict], layout: dict) -> tuple[str, int]:
    actions = get_display_actions(seq_data.get("actions", []))
    ev_map = build_ev_map(ev_seq)
    rows_html = []
    visible_rows = 0

    show_rate = bool(layout.get("show_rate", True))
    show_btn_ev = bool(layout.get("show_btn_ev", True))
    show_bb_ev = bool(layout.get("show_bb_ev", True))

    for bucket in get_bucket_order(seq_data):
        if is_hidden_bucket(bucket):
            continue

        row = None
        for r in seq_data.get("rows", []):
            if r.get("bucket") == bucket:
                row = r
                break
        if not row:
            continue

        rate = float(row.get("rate") or 0.0)
        if rate < 0.0001:
            continue

        visible_rows += 1
        bar_parts = []
        for act in actions:
            pct = float(row.get(act) or 0.0)
            if pct <= 0:
                continue
            bar_parts.append(
                f'<div class="bar-segment {escape(get_action_color_class(act))}" '
                f'style="width:{pct:.8f}%"></div>'
            )

        ev_row = ev_map.get(bucket, {})
        btn_text, btn_class = format_ev_cell(ev_row.get("btn_ev"))
        bb_text, bb_class = format_ev_cell(ev_row.get("bb_ev"))

        cells = [
            '<td class="col-strategy">'
            '<div class="bucket-strategy-cell">'
            f'<span class="bucket-tag">{escape(str(bucket))}</span>'
            f'<div class="strategy-bar">{"".join(bar_parts)}</div>'
            '</div>'
            '</td>'
        ]
        if show_rate:
            cells.append(f'<td class="col-rate">{rate:.2f}%</td>')
        if show_btn_ev:
            cells.append(f'<td class="col-ev-btn {btn_class}">{escape(btn_text)}</td>')
        if show_bb_ev:
            cells.append(f'<td class="col-ev-bb {bb_class}">{escape(bb_text)}</td>')

        rows_html.append('<tr>' + ''.join(cells) + '</tr>')

    if not rows_html:
        return '<div class="empty-state">No strategy rows</div>', 0

    headers = ['<th class="col-strategy">Strategy</th>']
    if show_rate:
        headers.append('<th class="col-rate">P(x)</th>')
    if show_btn_ev:
        headers.append('<th class="col-ev-btn">BTN EV</th>')
    if show_bb_ev:
        headers.append('<th class="col-ev-bb">BB EV</th>')

    table_html = (
        '<table class="strategy-table">'
        '<thead><tr>'
        + ''.join(headers) +
        '</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        '</table>'
    )
    return table_html, visible_rows


# builds one part of the data or output pipeline
def build_layout_override_css(layout: dict) -> str:
    show_rate = bool(layout.get("show_rate", True))
    show_btn_ev = bool(layout.get("show_btn_ev", True))
    show_bb_ev = bool(layout.get("show_bb_ev", True))
    show_overall = bool(layout.get("show_overall", True))

    if show_rate and (not show_btn_ev) and (not show_bb_ev):
        parts = [
            '.strategy-wrap{display:flex;justify-content:center;margin-top:0;}',
            '.strategy-table{width:370px;max-width:370px;margin:0 auto;}',
            '.strategy-table th.col-strategy,.strategy-table td.col-strategy{width:284px;}',
            '.strategy-table th.col-rate,.strategy-table td.col-rate{width:86px;}',
            '.bucket-strategy-cell{justify-content:flex-start;}',
            '.strategy-bar{width:200px;flex:0 0 200px;}',
        ]
        if show_overall:
            parts.append('.freq-bar-container{width:370px;max-width:370px;margin:0 auto;}')
        return ''.join(parts)

    if (not show_rate) and (not show_btn_ev) and (not show_bb_ev):
        parts = [
            '.strategy-wrap{display:flex;justify-content:center;margin-top:0;}',
            '.strategy-table{width:284px;max-width:284px;margin:0 auto;}',
            '.strategy-table th.col-strategy,.strategy-table td.col-strategy{width:284px;}',
            '.bucket-strategy-cell{justify-content:flex-start;}',
            '.strategy-bar{width:200px;flex:0 0 200px;}',
        ]
        if show_overall:
            parts.append('.freq-bar-container{width:284px;max-width:284px;margin:0 auto;}')
        return ''.join(parts)

    return ''


# builds one part of the data or output pipeline
def build_strategy_html_document(
    seq_data: dict,
    ev_seq: Optional[dict],
    freq_seq: Optional[dict],
    layout: dict,
    width: Optional[int] = None,
) -> tuple[str, int, int]:
    seq_data = apply_freqseq_to_seq_data(seq_data, freq_seq)
    actions = get_display_actions(seq_data.get("actions", []))

    if width is None:
        width = int(layout.get("width", 980))

    overall = seq_data.get("overall") if isinstance(seq_data.get("overall"), dict) else None
    has_overall = False
    if overall:
        total = sum(float(overall.get(a, 0.0)) for a in actions)
        has_overall = total > 0.0001
    if (not has_overall) or freq_seq:
        overall = compute_overall_from_rows(seq_data)
    if overall is None:
        overall = {}

    show_overall = bool(layout.get("show_overall", True))
    overall_html = render_overall_html(overall, actions) if show_overall else ""
    table_html, visible_rows = render_table_html(seq_data, ev_seq, layout)

    header_block_h = 60 if show_overall else 0
    gap_h = 12 if show_overall else 0
    if visible_rows == 0:
        table_h = 64
    else:
        table_h = 34 + (visible_rows * 28) + 2
    panel_h = 16 + header_block_h + gap_h + table_h + 16

    extra_css = build_layout_override_css(layout)

    xhtml_parts = [f'<div class="capture-root" style="width:{width}px;">']
    xhtml_parts.append(f'<div class="panel" style="width:{width}px;">')
    if show_overall:
        xhtml_parts.append(overall_html)
    xhtml_parts.append(f'<div class="strategy-wrap">{table_html}</div>')
    xhtml_parts.append('</div></div>')

    html = (
        '<!doctype html>'
        '<html>'
        '<head>'
        '<meta charset="UTF-8"/>'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
        f'<style>{FRONTEND_CSS}{extra_css}</style>'
        '</head>'
        '<body>'
        + ''.join(xhtml_parts) +
        '</body>'
        '</html>'
    )
    return html, width, panel_h


# helper for this part of the script
def render_html_to_png(html_text: str, out_path: Path, width: int, height: int, dpi: int = 600) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright is not installed. Run:\n"
            "  pip install playwright pillow\n"
            "  playwright install chromium"
        ) from e

    out_path.parent.mkdir(parents=True, exist_ok=True)

    device_scale = dpi / 96.0
    viewport_width = max(int(width + 32), 400)
    viewport_height = max(int(height + 32), 400)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_png = Path(tmp.name)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height},
                device_scale_factor=device_scale,
            )
            page = context.new_page()
            page.set_content(html_text, wait_until="load")
            page.wait_for_timeout(250)

            locator = page.locator(".strategy-table")
            locator.screenshot(path=str(tmp_png))
            context.close()
            browser.close()

        with Image.open(tmp_png) as im:
            im.save(out_path, format="PNG", dpi=(dpi, dpi))
    finally:
        if tmp_png.exists():
            tmp_png.unlink()


# writes this part of the output to file
def export_strategy_pngs_for_variant(
    sub: Path,
    variant_data: dict,
    png_dir_name: str = "strategy_pngs",
    png_layout: str = "full",
    png_dpi: int = 600,
) -> int:
    pots = variant_data.get("pots", {})
    if not isinstance(pots, dict):
        return 0

    exported = 0
    layout = get_layout_config(png_layout)
    png_root = sub / png_dir_name
    png_root.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict] = {}

    for pot_key, pot_data in pots.items():
        strategies = pot_data.get("strategies", {})
        sequences = strategies.get("sequences", {}) if isinstance(strategies, dict) else {}
        ev_sequences = {}
        if isinstance(pot_data.get("ev"), dict):
            ev_sequences = pot_data["ev"].get("sequences", {}) or {}
        freq_sequences = {}
        if isinstance(pot_data.get("bucket_freq_by_sequence"), dict):
            freq_sequences = pot_data["bucket_freq_by_sequence"].get("sequences", {}) or {}

        if not isinstance(sequences, dict) or not sequences:
            continue

        pot_dir_name = f"pot_{pot_key}" if pot_key != "default" else "default"
        out_dir = png_root / pot_dir_name
        out_dir.mkdir(parents=True, exist_ok=True)

        pot_manifest = {}
        for seq_name, seq_data in sequences.items():
            if not isinstance(seq_data, dict):
                continue

            ev_seq = ev_sequences.get(seq_name) if isinstance(ev_sequences, dict) else None
            freq_seq = freq_sequences.get(seq_name) if isinstance(freq_sequences, dict) else None

            html_text, width, height = build_strategy_html_document(
                seq_data=seq_data,
                ev_seq=ev_seq,
                freq_seq=freq_seq,
                layout=layout,
            )

            fname = safe_filename(seq_name) + ".png"
            out_path = out_dir / fname
            render_html_to_png(
                html_text=html_text,
                out_path=out_path,
                width=width,
                height=height,
                dpi=png_dpi,
            )

            exported += 1
            pot_manifest[seq_name] = str(out_path.relative_to(sub))

        if pot_manifest:
            manifest[pot_key] = pot_manifest

    if manifest:
        (png_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return exported


# runs the full script from the command line
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--include-ev",
        dest="include_ev",
        action="store_true",
        default=True,
        help="Include full EV tables in solver_data.js (default: on).",
    )
    ap.add_argument(
        "--meta-only-ev",
        dest="include_ev",
        action="store_false",
        help="Store only EV metadata, not full EV rows.",
    )
    ap.add_argument(
        "--export-strategy-pngs",
        dest="export_strategy_pngs",
        action="store_true",
        default=True,
        help="Export per-sequence PNG strategy tables into each data/<variant>/<png_dir_name>/ folder (default: on).",
    )
    ap.add_argument(
        "--no-export-strategy-pngs",
        dest="export_strategy_pngs",
        action="store_false",
        help="Skip PNG strategy-table export.",
    )
    ap.add_argument(
        "--png-dir-name",
        default="strategy_pngs",
        help="Subfolder name inside each variant data folder for exported PNGs (default: strategy_pngs).",
    )
    ap.add_argument(
        "--png-layout",
        choices=sorted(LAYOUT_PRESETS.keys()),
        default="full",
        help=(
            "PNG export layout preset: "
            "full = overall + rate + BTN EV + BB EV; "
            "bucket-rate = overall + bucket bar + rate only; "
            "bucket-rate-no-overall = bucket bar + rate only; "
            "bars-only = overall + bucket bars only."
        ),
    )
    ap.add_argument(
        "--png-dpi",
        type=int,
        default=600,
        help="PNG DPI metadata and render scale target (default: 600).",
    )
    ap.add_argument(
        "--variant",
        choices=sorted(VARIANTS.keys()),
        action="append",
        help=(
            "Only build/export the selected variant(s). "
            "Repeat the flag to include multiple variants, e.g. --variant 1draw --variant 2draw. "
            "Default: all variants."
        ),
    )
    args = ap.parse_args()

    JS_DIR.mkdir(parents=True, exist_ok=True)

    merged: dict = {}
    png_export_count = 0

    selected_items = list(VARIANTS.items())
    if args.variant:
        selected_items = [(variant, VARIANTS[variant]) for variant in args.variant]

    for variant, cfg in selected_items:
        print(f"collecting {variant}...")
        data = collect_variant(variant, cfg, include_ev=bool(args.include_ev))
        if data:
            merged[variant] = data
            print(f"  found {len(data['pots'])} pot configs: {list(data['pots'].keys())}")

            if args.export_strategy_pngs:
                sub = DATA_DIR / cfg["prefix"]
                n = export_strategy_pngs_for_variant(
                    sub=sub,
                    variant_data=data,
                    png_dir_name=args.png_dir_name,
                    png_layout=args.png_layout,
                    png_dpi=args.png_dpi,
                )
                png_export_count += n
                print(f"  exported {n} strategy PNGs to {sub / args.png_dir_name}")
        else:
            print("  no data found, skipping")

    if not merged:
        print("no data found at all, check your data/ folder")
        return

    outpath = JS_DIR / "solver_data.js"
    with open(outpath, "w", encoding="utf-8") as f:
        f.write("// auto-generated solver data, do not edit\n")
        f.write("window.SOLVER_DATA = ")
        json.dump(merged, f)
        f.write(";\n")

    json_path = JS_DIR / "solver_data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    size_kb = outpath.stat().st_size / 1024
    print(f"\nbuilt {outpath.name} ({size_kb:.0f} KB)")
    print(f"variants: {list(merged.keys())}")
    print("EV:", "INCLUDED (full tables)" if args.include_ev else "META ONLY")
    if args.export_strategy_pngs:
        print(f"PNG strategy tables exported: {png_export_count}")
        print(f"PNG layout: {args.png_layout}")
        print(f"PNG DPI: {args.png_dpi}")


if __name__ == "__main__":
    main()
