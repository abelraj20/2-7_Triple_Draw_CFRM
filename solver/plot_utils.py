#!/usr/bin/env python3
# this is the code for plotting the graphs and viewers

from __future__ import annotations

import argparse
import json
import html
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


_SCRIPT_DIR = Path(__file__).resolve().parent
_DATA_DIR = _SCRIPT_DIR.parent / "data"

# Canonical ordering used when bucket names are known.
# Includes 1-draw style buckets plus explicit TT..AA and also legacy grouped ranges.
_CANON_BUCKET_ORDER = [
    # high-card buckets
    "75", "76", "85", "86", "87", "95", "96", "97", "98",
    "T5", "T6", "T7", "T8", "T9", "J8", "J9", "Q", "K", "A",
    # explicit pairs
    "22", "33", "44", "55", "66", "77", "88", "99", "TT", "JJ", "QQ", "KK", "AA",
    # legacy grouped
    "22-33", "44-55", "66-77", "88-99", "TT-AA",
    # catch-all
    "Straight",
]
_CAN_IDX = {b: i for i, b in enumerate(_CANON_BUCKET_ORDER)}

# Action styles (base)
# NOTE: NL actions are inferred by prefix; this table is for exact short actions.
_LIMIT_STYLES = {
    "k": {"color": "#90EE90", "label": "Check", "lw": 2},
    "b": {"color": "#DC143C", "label": "Bet",   "lw": 2},
    "c": {"color": "#90EE90", "label": "Call",  "lw": 2},
    "f": {"color": "#87CEEB", "label": "Fold",  "lw": 2},
    "r": {"color": "#DC143C", "label": "Raise", "lw": 2},
}

# Used to detect pot files in a folder.
POT_RE = re.compile(r"(regrets|evolution|strategies|exploitability|ev)_pot(\d+)\.json$")


# quick helper to safely load json files
def load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  failed to load {path}: {e}")
        return None


# checks which pot sizes actually have output files
def detect_pots(variant_dir: Path) -> List[int]:
    pots = set()
    if not variant_dir.exists():
        return []
    for p in variant_dir.glob("*.json"):
        m = POT_RE.search(p.name)
        if m:
            pots.add(int(m.group(2)))
    return sorted(pots)


# makes the folders for plots and html output
def setup_dirs(variant: str, pot: str) -> Dict[str, Path]:
    base = _DATA_DIR / f"plots_{variant}" / f"pot{pot}"
    dirs = {
        "base": base,
        "regret": base / "regret",
        "strategy": base / "strategy",
        "exploitability": base / "exploitability",
        "strategy_tables": base / "strategy_tables",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


# turns short action codes into readable labels
def _action_label(act: str) -> str:
    if act in ("k", "b", "c", "f", "r"):
        return _LIMIT_STYLES[act]["label"]

    # NL-ish
    if act.startswith("b"):
        return f"Bet {act[1:]}" if act != "ba" else "Bet All-in"
    if act.startswith("r"):
        return f"Raise {act[1:]}" if act != "ra" else "Raise All-in"
    return act.upper()


# picks colours and labels for each action when plotting
def get_style(act: str) -> dict:
    """
    Style inference:
    - k,c => green
    - f   => blue
    - b,r and any bet/raise variants => red
    """
    if act in _LIMIT_STYLES:
        return _LIMIT_STYLES[act]

    if act.startswith("k") or act.startswith("c"):
        return {"color": "#90EE90", "label": _action_label(act), "lw": 2}
    if act.startswith("f"):
        return {"color": "#87CEEB", "label": _action_label(act), "lw": 2}
    if act.startswith("b") or act.startswith("r"):
        return {"color": "#DC143C", "label": _action_label(act), "lw": 2}

    return {"color": "#888888", "label": _action_label(act), "lw": 1.8}


# turns a sequence string into something easier to read
def pretty_seq(seq: str) -> str:
    if seq == "":
        return "Start"

    # Tokenize NL sequences like "kb40r86ra"
    # Greedy parse: k/c/f single, else b\d+|ba or r\d+|ra
    tokens = []
    i = 0
    while i < len(seq):
        ch = seq[i]
        if ch in ("k", "c", "f"):
            tokens.append(ch)
            i += 1
            continue
        if ch in ("b", "r"):
            j = i + 1
            while j < len(seq) and (seq[j].isdigit() or seq[j] == "a"):
                j += 1
            tokens.append(seq[i:j])
            i = j
            continue
        tokens.append(ch)
        i += 1

    return " - ".join(_action_label(t) for t in tokens)


# makes a sequence name safe for filenames and html ids
def safe_seq_id(seq: str) -> str:
    return "start" if seq == "" else re.sub(r"[^A-Za-z0-9_]+", "_", seq)


# makes a bucket name safe for html ids
def safe_bucket_id(b: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", b)


# sorting helper so buckets stay in a sensible order
def bucket_sort_key(bucket: str) -> Tuple[int, str]:
    return (_CAN_IDX.get(bucket, 10_000), bucket)


# sorts bucket names into the order i want for plots/tables
def order_buckets(buckets: List[str]) -> List[str]:
    return sorted(buckets, key=bucket_sort_key)


# grabs every bucket that shows up in the strategy json
def _extract_all_buckets_from_strat(strat_data: dict) -> List[str]:
    out = set()
    seqs = (strat_data or {}).get("sequences", {})
    if not isinstance(seqs, dict):
        return []
    for _, info in seqs.items():
        if not isinstance(info, dict) or info.get("terminal"):
            continue
        for r in info.get("rows", []) or []:
            if isinstance(r, dict) and isinstance(r.get("bucket"), str):
                out.add(r["bucket"])
    return order_buckets(list(out))


# makes the regret graph for one node
def plot_regret(regret_dict: dict, actions: List[str], iters: List[int], title: str, outpath: Path):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    if not regret_dict or not actions or not iters:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12)
        ax.axis("off")
        fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return

    any_plotted = False
    all_vals: List[float] = []

    for act in actions:
        vals = regret_dict.get(act, [])
        if len(vals) == len(iters):
            sty = get_style(act)
            ax.plot(iters, vals, color=sty["color"], linewidth=1.6, label=sty["label"])
            any_plotted = True
            all_vals.extend([float(x) for x in vals if isinstance(x, (int, float))])

    if not any_plotted:
        ax.text(0.5, 0.5, "No plottable series", ha="center", va="center", fontsize=12)
        ax.axis("off")
        fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return

    ax.axhline(0, color="black", linewidth=0.6, alpha=0.4)
    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True)
    ax.grid(False)

    if all_vals:
        margin = max(abs(min(all_vals)), abs(max(all_vals)), 0.1) * 0.12
        ax.set_ylim(min(all_vals) - margin, max(all_vals) + margin)

    ax.set_xlabel("Iteration", fontsize=10)
    ax.set_ylabel("Accumulated Regret", fontsize=10)
    ax.set_title(title, fontsize=11, pad=8)
    ax.legend(loc="best", fontsize=9, framealpha=0.9, edgecolor="#ccc")

    plt.tight_layout()
    fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# makes the strategy frequency graph for one node
def plot_strategy(evo_dict: dict, actions: List[str], iters: List[int], title: str, outpath: Path):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    if not evo_dict or not actions or not iters:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12)
        ax.axis("off")
        fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return

    any_plotted = False
    for act in actions:
        vals = evo_dict.get(act, [])
        if len(vals) == len(iters):
            sty = get_style(act)
            ax.plot(iters, vals, color=sty["color"], linewidth=1.6, label=sty["label"])
            any_plotted = True

    if not any_plotted:
        ax.text(0.5, 0.5, "No plottable series", ha="center", va="center", fontsize=12)
        ax.axis("off")
        fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return

    ax.tick_params(axis="both", which="both", direction="in", labelsize=14, top=True, right=True)
    ax.grid(False)
    ax.set_ylim(-3, 103)
    ax.set_xlabel("Iteration", fontsize=16)
    ax.set_ylabel("Strategy %", fontsize=16)
    ax.set_title(title, fontsize=11, pad=8)
    ax.legend(loc="best", fontsize=14, framealpha=0.9, edgecolor="#ccc")

    plt.tight_layout()
    fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# makes one of the output plots
def plot_exploit(exploit_iters: List[int], exploit_vals: List[float], title: str, outpath: Path):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    if not exploit_iters or not exploit_vals:
        ax.text(0.5, 0.5, "No exploitability data", ha="center", va="center", fontsize=12)
        ax.axis("off")
        fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return

    iters = np.asarray(exploit_iters, dtype=float)
    vals = np.asarray(exploit_vals, dtype=float)

    ok = np.isfinite(iters) & np.isfinite(vals) & (iters > 0) & (vals > 0)
    iters = iters[ok]
    vals = vals[ok]

    if vals.size == 0:
        ax.text(0.5, 0.5, "No positive exploitability points (log-log needs > 0).",
                ha="center", va="center", fontsize=12)
        ax.axis("off")
        fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return

    ax.plot(iters, vals, color="black", linewidth=1.8)

    ax.set_xscale("log", base=10)
    ax.set_yscale("log", base=10)

    xmin = float(np.min(iters))
    xmax = float(np.max(iters))
    ymin = float(np.min(vals))
    ymax = float(np.max(vals))

    # --- symmetric padding in LOG space (because x=0 is impossible on log axes)
    x_min_pow = int(np.floor(np.log10(xmin)))
    x_max_pow = int(np.ceil(np.log10(xmax)))
    
    lx0 = np.log10(xmin)
    lx1 = np.log10(xmax)

    x_lo = 10.0 ** (lx0)
    x_hi = 10.0 ** (lx1 + 1)

    # --- y limits decade aligned (looks clean with decade gridlines)
    y_min_pow = int(np.floor(np.log10(ymin)))
    y_max_pow = int(np.ceil(np.log10(ymax)))
    ax.set_ylim(10.0 ** y_min_pow, 10.0 ** y_max_pow)

    # --- major ticks at decades (based on padded x range, so edges still look “even”)
    x_min_pow = int(np.floor(np.log10(x_lo)))
    x_max_pow = int(np.ceil(np.log10(x_hi)))
    ax.set_xticks([10.0 ** k for k in range(x_min_pow, x_max_pow + 1)])
    ax.set_yticks([10.0 ** k for k in range(y_min_pow, y_max_pow + 1)])

    ax.xaxis.set_major_formatter(mticker.LogFormatterMathtext(base=10))
    ax.yaxis.set_major_formatter(mticker.LogFormatterMathtext(base=10))

    # --- minor ticks 2..9 inside each decade
    ax.xaxis.set_minor_locator(mticker.LogLocator(base=10.0, subs=np.arange(2, 10), numticks=100))
    ax.yaxis.set_minor_locator(mticker.LogLocator(base=10.0, subs=np.arange(2, 10), numticks=100))
    ax.xaxis.set_minor_formatter(mticker.NullFormatter())
    ax.yaxis.set_minor_formatter(mticker.NullFormatter())

    # --- ticks
    ax.tick_params(axis="both", which="major", direction="in", top=True, right=True, length=6)
    ax.tick_params(axis="both", which="minor", direction="in", top=True, right=True, length=3)

    # --- grid: horizontal only at y decades
    ax.xaxis.grid(False, which="both")
    ax.yaxis.grid(True, which="major", linestyle=":", linewidth=0.8, color="black", alpha=0.35)
    ax.yaxis.grid(False, which="minor")

    ax.set_xlabel("Iteration", fontsize=10)
    ax.set_ylabel("Exploitability (mbb/g)", fontsize=10)
 
    ax.set_xlim(0.6, 10**5)

    plt.tight_layout()
    fig.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# builds one part of the data or output pipeline
def build_viewer_html(variant: str, pot: str, plot_type: str, seq_buckets: Dict[str, List[str]], base_dir: Path):
    """
    Image viewer for regret/strategy plots:
      - sequence tabs
      - arrows to switch bucket image
      - keyboard arrows switch too
      - no bucket sidebar
    """
    html_path = base_dir / f"{plot_type}_viewer.html"

    raw_seqs = list(seq_buckets.keys())
    raw_seqs.sort(key=lambda s: (s != "", s))
    seq_items: List[Tuple[str, str]] = [(safe_seq_id(s), s) for s in raw_seqs]
    ordered_map = {safe_seq_id(s): order_buckets(seq_buckets[s]) for s in raw_seqs}

    js_seq_items = json.dumps(seq_items)
    js_seq_buckets = json.dumps(ordered_map)

    css = """<style>
body{font-family:system-ui,sans-serif;margin:20px;background:#f5f5f5}
h2{text-align:center;color:#222;margin:0 0 14px}
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.tab{padding:8px 14px;cursor:pointer;border:1px solid #ccc;border-radius:10px;background:#eee;font-size:13px;user-select:none}
.tab.on{background:#fff;font-weight:700;border-color:#bbb;box-shadow:0 1px 6px rgba(0,0,0,.06)}
.panel{display:none;background:#fff;border:1px solid #ddd;border-radius:14px;padding:14px}
.panel.on{display:block}
.nav{display:flex;justify-content:center;align-items:center;gap:10px;margin:6px 0 10px}
.navBtn{cursor:pointer;padding:6px 12px;background:#fff;border:1px solid #ccc;border-radius:10px;font-size:16px;user-select:none}
.navBtn:hover{background:#eee}
.navLbl{font-size:13px;color:#333;min-width:220px;text-align:center}
.imgWrap{text-align:center}
.imgWrap img{max-width:100%;border-radius:10px;border:1px solid #eee}
.note{font-size:12px;color:#666;margin-top:8px;text-align:center}
</style>"""

    js = f"""<script>
const SEQS = {js_seq_items};
const BUCKETS = {js_seq_buckets};
let CUR = SEQS.length ? SEQS[0][0] : null;

function setSeq(safeSeq) {{
  CUR = safeSeq;
  for (const [sid,_] of SEQS) {{
    const t = document.getElementById('t_' + sid);
    const p = document.getElementById('p_' + sid);
    if (t) t.classList.remove('on');
    if (p) p.classList.remove('on');
  }}
  const t = document.getElementById('t_' + safeSeq);
  const p = document.getElementById('p_' + safeSeq);
  if (t) t.classList.add('on');
  if (p) p.classList.add('on');

  const bs = BUCKETS[safeSeq] || [];
  if (bs.length) setBucketIdx(safeSeq, 0);
}}

function setBucketIdx(safeSeq, idx) {{
  const bs = BUCKETS[safeSeq] || [];
  if (!bs.length) return;
  idx = ((idx % bs.length) + bs.length) % bs.length;

  const panel = document.getElementById('p_' + safeSeq);
  if (!panel) return;
  panel.dataset.idx = String(idx);

  const bucket = bs[idx];
  const lbl = panel.querySelector('.navLbl');
  if (lbl) lbl.textContent = bucket + ' (' + (idx+1) + '/' + bs.length + ')';

  const img = panel.querySelector('img');
  if (img) {{
    const safeB = bucket.replaceAll(/[^A-Za-z0-9_]+/g,'_');
    img.src = '{plot_type}/seq_' + safeSeq + '_bucket_' + safeB + '.png';
    img.alt = bucket;
  }}
}}

function prevBucket() {{
  if (!CUR) return;
  const panel = document.getElementById('p_' + CUR);
  const idx = parseInt((panel && panel.dataset.idx) ? panel.dataset.idx : '0', 10);
  setBucketIdx(CUR, idx - 1);
}}

function nextBucket() {{
  if (!CUR) return;
  const panel = document.getElementById('p_' + CUR);
  const idx = parseInt((panel && panel.dataset.idx) ? panel.dataset.idx : '0', 10);
  setBucketIdx(CUR, idx + 1);
}}

window.addEventListener('keydown', (e) => {{
  if (e.key === 'ArrowLeft') prevBucket();
  if (e.key === 'ArrowRight') nextBucket();
}});

window.onload = function() {{
  if (SEQS.length) setSeq(SEQS[0][0]);
}};
</script>"""

    body = f"<h2>{variant.upper()} {plot_type.title()} — Pot {pot}</h2>\n"
    body += '<div class="tabs">\n'
    for safe, raw in seq_items:
        label = "Start" if raw == "" else raw
        body += f'<div id="t_{safe}" class="tab" onclick="setSeq(\'{safe}\')">{label}</div>\n'
    body += "</div>\n"

    for safe, raw in seq_items:
        buckets = ordered_map.get(safe, [])
        first = buckets[0] if buckets else ""
        first_safe_b = safe_bucket_id(first)
        img_src = f"{plot_type}/seq_{safe}_bucket_{first_safe_b}.png" if first else ""

        body += f'<div id="p_{safe}" class="panel" data-idx="0">\n'
        body += '  <div class="nav">\n'
        body += '    <div class="navBtn" onclick="prevBucket()">&#8592;</div>\n'
        body += f'    <div class="navLbl">{first} ({1 if buckets else 0}/{len(buckets)})</div>\n'
        body += '    <div class="navBtn" onclick="nextBucket()">&#8594;</div>\n'
        body += '  </div>\n'
        body += '  <div class="imgWrap">\n'
        body += f'    <img src="{img_src}" loading="lazy"/>\n'
        raw_label = "Start" if raw == "" else raw
        body += f'    <div class="note">Sequence: {raw_label} (use &#8592; / &#8594; keys too)</div>\n'
        body += '  </div>\n'
        body += '</div>\n'

    html = f"<!DOCTYPE html><html><head><meta charset=utf-8><title>{plot_type} {variant} pot{pot}</title>{css}</head><body>{body}{js}</body></html>"
    html_path.write_text(html, encoding="utf-8")
    print(f"    viewer: {html_path.name}")


# small helper used by the main parts of the script
def _coerce_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


# small helper used by the main parts of the script
def _coerce_pct(x: Any) -> float:
    v = _coerce_float(x)
    return float(v) if v is not None and np.isfinite(v) else 0.0


# small helper used by the main parts of the script
def _build_overall_from_rows(rows: List[dict], actions: List[str]) -> Dict[str, float]:
    out = {a: 0.0 for a in actions}
    for r in rows:
        rate = _coerce_pct(r.get("rate", 0.0))
        for a in actions:
            out[a] += rate * (_coerce_pct(r.get(a, 0.0)) / 100.0)
    return {a: float(out[a]) for a in actions}


# small helper used by the main parts of the script
def _compact_action_class(act: str) -> str:
    exact = {
        "f": "color-fold",
        "k": "color-check",
        "c": "color-call",
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
    if act in exact:
        return exact[act]
    if act.startswith("b"):
        return "color-bet"
    if act.startswith("r"):
        return "color-raise"
    if act.startswith("c"):
        return "color-call"
    if act.startswith("k"):
        return "color-check"
    if act.startswith("f"):
        return "color-fold"
    return "color-bet"


# small helper used by the main parts of the script
def _ev_class(v: Optional[float]) -> str:
    if v is None:
        return "ev-zero"
    if v > 1e-12:
        return "ev-positive"
    if v < -1e-12:
        return "ev-negative"
    return "ev-zero"


# small helper used by the main parts of the script
def _fmt_pct_value(x: Optional[float]) -> str:
    if x is None:
        return "-"
    return f"{float(x):.1f}%"


# small helper used by the main parts of the script
def _fmt_num_value(x: Optional[float]) -> str:
    if x is None:
        return "-"
    return f"{float(x):.3f}"


# small helper used by the main parts of the script
def _strategy_tables_css() -> str:
    return """<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background: #1a1a2e;
  color: #e0e0e0;
  margin: 0;
  padding: 14px;
}
a { color: inherit; text-decoration: none; }
.page-wrap {
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  background: #16213e;
  border: 1px solid #0f3460;
  border-radius: 10px;
  overflow: hidden;
}
.page-head {
  padding: 10px 12px;
  background: #0f3460;
  border-bottom: 1px solid #0f3460;
}
.page-head h1 {
  font-size: 13px;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: #e94560;
  margin: 0;
}
.page-sub {
  padding: 8px 12px;
  border-bottom: 1px solid #0f3460;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11px;
}
.page-sub .muted { color: #aaa; }
.nav-row {
  padding: 8px 12px;
  border-bottom: 1px solid #0f3460;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.nav-btn {
  background: #0d1b2a;
  color: #e0e0e0;
  border: 1px solid #0f3460;
  border-radius: 4px;
  padding: 5px 8px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.nav-btn:hover { border-color: #e94560; color: #fff; }
.lp-section { padding: 8px 12px; border-bottom: 1px solid #0f3460; }
.freq-title {
  font-size: 10px;
  font-weight: bold;
  margin-bottom: 6px;
  color: #aaa;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.freq-bar-container {
  display: flex;
  width: 100%;
  height: 52px;
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
  font-size: 10px;
  font-weight: 600;
  color: rgb(255, 255, 255);
  text-shadow: 0 1px 0 rgb(0, 0, 0);
  white-space: nowrap;
  overflow: hidden;
  text-transform: uppercase;
  letter-spacing: 0.2px;
}
.freq-pct {
  font-size: 16px;
  font-weight: 600;
  color: rgb(255, 255, 255);
  text-shadow: 0 1px 0 rgb(0, 0, 0);
}
.color-fold { background: #87CEEB; }
.color-check { background: #74dd70; }
.color-call { background: #74dd70; }
.color-bet { background: #DC143C; }
.color-raise { background: #DC143C; }
.color-b40 { background: #FFB6C1; }
.color-b80 { background: #FF6B6B; }
.color-b120 { background: #DC143C; }
.color-ba { background: #8B0000; }
.color-r86 { background: #FF6B6B; }
.color-r111 { background: #DC143C; }
.color-ra { background: #8B0000; }

.table-wrap {
  padding: 8px 12px 12px 12px;
  overflow-x: auto;
}
.strategy-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 10px;
  table-layout: fixed;
}
.strategy-table th {
  background: #0f3460;
  text-transform: uppercase;
  font-size: 8px;
  letter-spacing: 0.2px;
  color: #aaa;
  padding: 5px 3px;
  border-bottom: 2px solid #e94560;
  text-align: center;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
}
.strategy-table td {
  padding: 2px 3px;
  border-bottom: 1px solid #0f3460;
  vertical-align: middle;
  height: 24px;
  overflow: hidden;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.strategy-table tr:hover td { background: rgba(79, 195, 247, 0.05); }

.strategy-table th.col-strategy,
.strategy-table td.col-strategy { width: 52%; }
.strategy-table th.col-rate,
.strategy-table td.col-rate { width: 16%; }
.strategy-table th.col-ev-btn,
.strategy-table td.col-ev-btn { width: 16%; }
.strategy-table th.col-ev-bb,
.strategy-table td.col-ev-bb { width: 16%; }

.bucket-strategy-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  width: 100%;
}
.bucket-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  padding: 2px 4px;
  border-radius: 4px;
  background: rgba(15, 52, 96, 0.65);
  border: 1px solid rgba(233, 69, 96, 0.25);
  color: #4fc3f7;
  font-weight: 800;
  letter-spacing: 0.1px;
  font-size: 10px;
  line-height: 1;
  flex-shrink: 0;
}
.strategy-bar {
  display: flex;
  height: 16px;
  border-radius: 3px;
  overflow: hidden;
  background: rgba(255,255,255,0.1);
  width: 190px;
  flex: 0 0 190px;
}
.bar-segment { height: 100%; }

.ev-positive { color: #4caf50; font-weight: 800; }
.ev-negative { color: #e94560; font-weight: 800; }
.ev-zero { color: #888; }

.seq-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 8px;
  padding: 12px;
}
.seq-card {
  display: block;
  background: #0d1b2a;
  border: 1px solid #0f3460;
  border-radius: 6px;
  padding: 10px;
}
.seq-card:hover { border-color: #e94560; }
.seq-card .seq-title {
  font-size: 11px;
  font-weight: 700;
  color: #e0e0e0;
  margin-bottom: 4px;
}
.seq-card .seq-meta {
  font-size: 10px;
  color: #aaa;
}
.empty-note {
  padding: 12px;
  color: #aaa;
  font-size: 11px;
}
@media (max-width: 900px) {
  body { padding: 8px; }
  .page-wrap { max-width: 100%; }
  .strategy-bar { width: 160px; flex-basis: 160px; }
}
</style>"""


# small helper used by the main parts of the script
def _render_overall_bar(overall: Dict[str, float], actions: List[str]) -> str:
    if not actions:
        return '<div class="freq-bar-container"><div class="freq-bar-segment" style="width:100%"><div class="freq-label">No data</div><div class="freq-pct">-</div></div></div>'

    seg_width = 100.0 / max(len(actions), 1)
    bits = ['<div class="freq-bar-container">']
    for a in actions:
        pct = float(overall.get(a, 0.0) or 0.0)
        label = html.escape(_action_label(a))
        cls = _compact_action_class(a)
        bits.append(
            f'<div class="freq-bar-segment {cls}" style="width:{seg_width:.6f}%;">'
            f'<div class="freq-label">{label}</div>'
            f'<div class="freq-pct">{pct:.1f}%</div>'
            f'</div>'
        )
    bits.append("</div>")
    return "".join(bits)


# small helper used by the main parts of the script
def _render_strategy_rows(rows: List[dict], actions: List[str]) -> str:
    out: List[str] = []
    for r in rows:
        bucket = html.escape(str(r.get("bucket", "")))
        rate = _fmt_pct_value(r.get("rate"))
        btn_ev = r.get("btn_ev")
        bb_ev = r.get("bb_ev")
        btn_cls = _ev_class(btn_ev)
        bb_cls = _ev_class(bb_ev)

        segs: List[str] = []
        strat = r.get("strat", {}) or {}
        for a in actions:
            pct = float(strat.get(a, 0.0) or 0.0)
            if pct <= 0:
                continue
            cls = _compact_action_class(a)
            segs.append(
                f'<div class="bar-segment {cls}" style="width:{pct:.6f}%;" title="{html.escape(_action_label(a))}: {pct:.1f}%"></div>'
            )
        if not segs:
            segs.append('<div class="bar-segment" style="width:100%;background:rgba(255,255,255,0.06)"></div>')

        out.append(
            "<tr>"
            '<td class="col-strategy">'
            '<div class="bucket-strategy-cell">'
            f'<span class="bucket-tag">{bucket}</span>'
            f'<div class="strategy-bar">{"".join(segs)}</div>'
            '</div>'
            '</td>'
            f'<td class="col-rate">{rate}</td>'
            f'<td class="col-ev-btn {btn_cls}">{_fmt_num_value(btn_ev)}</td>'
            f'<td class="col-ev-bb {bb_cls}">{_fmt_num_value(bb_ev)}</td>'
            "</tr>"
        )
    return "".join(out)


# builds one part of the data or output pipeline
def build_strategy_table_viewer(variant: str, pot: str, base_dir: Path, strat_data: dict, ev_data: Optional[dict]):
    folder = base_dir / "strategy_tables"
    folder.mkdir(parents=True, exist_ok=True)

    seqs = (strat_data or {}).get("sequences", {})
    if not isinstance(seqs, dict) or not seqs:
        return

    present_buckets = _extract_all_buckets_from_strat(strat_data)
    bucket_order = present_buckets if present_buckets else list(_CANON_BUCKET_ORDER)

    ev_map: Dict[str, Dict[str, Tuple[Optional[float], Optional[float]]]] = {}
    if ev_data and isinstance(ev_data.get("sequences"), dict):
        for seq, info in ev_data["sequences"].items():
            if not isinstance(info, dict) or info.get("terminal"):
                continue
            m: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
            for row in info.get("rows", []) or []:
                if not isinstance(row, dict):
                    continue
                b = row.get("bucket")
                if not isinstance(b, str):
                    continue
                m[b] = (_coerce_float(row.get("btn_ev", None)), _coerce_float(row.get("bb_ev", None)))
            ev_map[seq] = m

    raw_seqs = list(seqs.keys())
    raw_seqs.sort(key=lambda s: (s != "", s))

    cooked_sequences: List[Dict[str, Any]] = []
    for idx, raw_seq in enumerate(raw_seqs):
        entry = seqs.get(raw_seq, {})
        if not isinstance(entry, dict) or entry.get("terminal"):
            continue

        actions = entry.get("actions", []) or []
        rows = entry.get("rows", []) or []
        by_b = {r.get("bucket"): r for r in rows if isinstance(r, dict) and isinstance(r.get("bucket"), str)}
        ordered_rows: List[dict] = [by_b[b] for b in bucket_order if b in by_b]
        bucket_order_set = set(bucket_order)
        remaining = [b for b in by_b.keys() if b not in bucket_order_set]
        for b in order_buckets(remaining):
            ordered_rows.append(by_b[b])

        overall = entry.get("overall")
        if not isinstance(overall, dict):
            overall = _build_overall_from_rows(ordered_rows, actions)

        ev_for_seq = ev_map.get(raw_seq, {})
        cooked_rows: List[dict] = []
        for r in ordered_rows:
            b = r.get("bucket")
            rr = {
                "bucket": b,
                "rate": _coerce_float(r.get("rate", 0.0)) or 0.0,
                "strat": {a: float(r.get(a, 0.0) or 0.0) for a in actions},
                "btn_ev": None,
                "bb_ev": None,
            }
            if b in ev_for_seq:
                rr["btn_ev"], rr["bb_ev"] = ev_for_seq[b]
            cooked_rows.append(rr)

        safe = safe_seq_id(raw_seq)
        filename = f"{idx:02d}_{safe}.html"
        cooked_sequences.append(
            {
                "idx": idx,
                "raw_seq": raw_seq,
                "safe": safe,
                "filename": filename,
                "actor": entry.get("actor", "?"),
                "actions": actions,
                "overall": {a: float(overall.get(a, 0.0) or 0.0) for a in actions},
                "rows": cooked_rows,
            }
        )

    css = _strategy_tables_css()

    if not cooked_sequences:
        index_html = f"<!DOCTYPE html><html><head><meta charset=utf-8><title>{variant} pot{pot} strategy tables</title>{css}</head><body><div class='page-wrap'><div class='page-head'><h1>{html.escape(variant.upper())} Strategy Tables — Pot {html.escape(str(pot))}</h1></div><div class='empty-note'>No non-terminal strategy tables found.</div></div></body></html>"
        (folder / "index.html").write_text(index_html, encoding="utf-8")
        (base_dir / "strategy_table_viewer.html").write_text(index_html, encoding="utf-8")
        print("    viewer: strategy_tables/index.html")
        return

    for i, seq in enumerate(cooked_sequences):
        prev_href = cooked_sequences[i - 1]["filename"] if i > 0 else "index.html"
        next_href = cooked_sequences[i + 1]["filename"] if i + 1 < len(cooked_sequences) else "index.html"
        seq_label = "Start" if seq["raw_seq"] == "" else seq["raw_seq"]
        pretty_label = pretty_seq(seq["raw_seq"])
        actions_label = ", ".join(_action_label(a) for a in seq["actions"]) if seq["actions"] else "-"
        overall_html = _render_overall_bar(seq["overall"], seq["actions"])
        rows_html = _render_strategy_rows(seq["rows"], seq["actions"])

        page = (
            "<!DOCTYPE html><html><head><meta charset=utf-8>"
            f"<title>{html.escape(variant)} pot{html.escape(str(pot))} {html.escape(seq_label)}</title>"
            f"{css}</head><body>"
            '<div class="page-wrap">'
            f'<div class="page-head"><h1>{html.escape(variant.upper())} Strategy Table — Pot {html.escape(str(pot))}</h1></div>'
            '<div class="page-sub">'
            f'<div><span class="muted">Sequence:</span> {html.escape(seq_label)}'
            f' &nbsp; <span class="muted">Parsed:</span> {html.escape(pretty_label)}</div>'
            f'<div><span class="muted">Actor:</span> {html.escape(str(seq["actor"]))}</div>'
            '</div>'
            '<div class="nav-row">'
            f'<a class="nav-btn" href="{prev_href}">Prev</a>'
            f'<a class="nav-btn" href="index.html">All tables</a>'
            f'<a class="nav-btn" href="{next_href}">Next</a>'
            f'<a class="nav-btn" href="../index.html">Pot index</a>'
            '</div>'
            '<div class="lp-section">'
            '<div class="freq-title">Overall Frequency</div>'
            f'{overall_html}'
            '</div>'
            '<div class="lp-section">'
            f'<div class="freq-title">Actions</div><div class="muted" style="font-size:11px;">{html.escape(actions_label)}</div>'
            '</div>'
            '<div class="table-wrap">'
            '<table class="strategy-table">'
            '<thead><tr>'
            '<th class="col-strategy">Strategy</th>'
            '<th class="col-rate">Rate</th>'
            '<th class="col-ev-btn">BTN EV</th>'
            '<th class="col-ev-bb">BB EV</th>'
            '</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            '</table>'
            '</div>'
            '</div></body></html>'
        )
        (folder / seq["filename"]).write_text(page, encoding="utf-8")

    cards = []
    for seq in cooked_sequences:
        seq_label = "Start" if seq["raw_seq"] == "" else seq["raw_seq"]
        cards.append(
            f'<a class="seq-card" href="{seq["filename"]}">'
            f'<div class="seq-title">{html.escape(seq_label)}</div>'
            f'<div class="seq-meta">Actor: {html.escape(str(seq["actor"]))}</div>'
            f'<div class="seq-meta">{len(seq["rows"])} buckets</div>'
            '</a>'
        )

    index_html = (
        "<!DOCTYPE html><html><head><meta charset=utf-8>"
        f"<title>{html.escape(variant)} pot{html.escape(str(pot))} strategy tables</title>"
        f"{css}</head><body>"
        '<div class="page-wrap">'
        f'<div class="page-head"><h1>{html.escape(variant.upper())} Strategy Tables — Pot {html.escape(str(pot))}</h1></div>'
        '<div class="page-sub">'
        f'<div><span class="muted">Sequences:</span> {len(cooked_sequences)}</div>'
        '<div><a class="nav-btn" href="../index.html">Back to pot index</a></div>'
        '</div>'
        '<div class="seq-grid">'
        f'{"".join(cards)}'
        '</div>'
        '</div></body></html>'
    )
    (folder / "index.html").write_text(index_html, encoding="utf-8")

    landing_html = (
        "<!DOCTYPE html><html><head><meta charset=utf-8>"
        f"<title>{html.escape(variant)} pot{html.escape(str(pot))} strategy tables</title>"
        '<meta http-equiv="refresh" content="0; url=strategy_tables/index.html">'
        f"{css}</head><body>"
        '<div class="page-wrap">'
        f'<div class="page-head"><h1>{html.escape(variant.upper())} Strategy Tables — Pot {html.escape(str(pot))}</h1></div>'
        '<div class="empty-note">Open <a href="strategy_tables/index.html">strategy_tables/index.html</a>.</div>'
        '</div></body></html>'
    )
    (base_dir / "strategy_table_viewer.html").write_text(landing_html, encoding="utf-8")
    print("    viewer: strategy_tables/index.html")


# builds one part of the data or output pipeline
def build_pot_index_html(variant: str, pot: str, base_dir: Path, have_regret: bool, have_strategy: bool, have_exploit: bool, have_strategy_table: bool):
    parts = []
    parts.append(f"<h2>{variant.upper()} — Pot {pot}</h2>")
    parts.append("<div class='cards'>")

    def card(title: str, href: str, desc: str) -> str:
        return f"""
        <a class="card" href="{href}">
          <div class="ct">{title}</div>
          <div class="cd">{desc}</div>
        </a>
        """

    if have_strategy_table:
        parts.append(card("Strategy Tables Folder", "strategy_tables/index.html",
                          "One compact strategy-table page per sequence."))
    if have_regret:
        parts.append(card("Regret Viewer", "regret_viewer.html", "Browse regret plots by sequence + bucket (arrows)."))
    if have_strategy:
        parts.append(card("Strategy Plot Viewer", "strategy_viewer.html", "Browse strategy plots by sequence + bucket (arrows)."))
    parts.append("</div>")

    if have_exploit:
        parts.append("<div class='sec'><h3>Exploitability</h3>")
        parts.append("<div class='img'><img src='exploitability/exploitability.png' loading='lazy'></div></div>")

    css = """<style>
body{font-family:system-ui,sans-serif;margin:20px;background:#f5f5f5}
h2{color:#222;margin:0 0 14px}
.cards{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:18px}
.card{display:block;min-width:240px;max-width:380px;padding:14px 16px;background:#fff;border:1px solid #ddd;
      border-radius:14px;text-decoration:none;color:#111;box-shadow:0 1px 10px rgba(0,0,0,.05)}
.card:hover{border-color:#bbb; transform:translateY(-1px)}
.ct{font-weight:700;margin-bottom:6px}
.cd{font-size:13px;color:#555}
.sec{background:#fff;border:1px solid #ddd;border-radius:14px;padding:14px}
.sec h3{margin:0 0 10px;color:#222}
.img{text-align:center}
.img img{max-width:100%;border-radius:12px;border:1px solid #eee}
</style>"""

    html = "<!DOCTYPE html><html><head><meta charset=utf-8><title>"
    html += f"{variant} pot{pot}</title>{css}</head><body>"
    html += "\n".join(parts)
    html += "</body></html>"

    (base_dir / "index.html").write_text(html, encoding="utf-8")
    print("    index: index.html")


# helper for this part of the script
def process_variant(variant: str, pots: List[int]):
    print(f"\n  {variant}")
    sub = _DATA_DIR / variant
    if not sub.exists():
        print(f"  missing folder: {sub}")
        return

    if not pots:
        _process_one(variant, "default", sub)
        return

    for pot in pots:
        _process_one(variant, str(pot), sub)


# small helper used by the main parts of the script
def _process_one(variant: str, pot_key: str, sub: Path):
    print(f"\n  pot {pot_key}:")
    dirs = setup_dirs(variant, pot_key)
    base_dir = dirs["base"]

    if pot_key.isdigit():
        reg_path = sub / f"regrets_pot{pot_key}.json"
        evo_path = sub / f"evolution_pot{pot_key}.json"
        exp_path = sub / f"exploitability_pot{pot_key}.json"
        strat_path = sub / f"strategies_pot{pot_key}.json"
        ev_path = sub / f"ev_pot{pot_key}.json"
    else:
        reg_path = sub / "regrets.json"
        evo_path = sub / "evolution.json"
        exp_path = sub / "exploitability.json"
        strat_path = sub / "strategies.json"
        ev_path = sub / "ev.json"

    reg_data = load_json(reg_path)
    evo_data = load_json(evo_path)
    exp_data = load_json(exp_path)
    strat_data = load_json(strat_path)
    ev_data = load_json(ev_path)

    if not reg_data and not evo_data and not exp_data and not strat_data:
        print("    no data, skipping")
        return

    tracked_iters = []
    if reg_data:
        tracked_iters = reg_data.get("tracked_iterations", [])
    elif evo_data:
        tracked_iters = evo_data.get("tracked_iterations", [])

    have_regret = False
    have_strategy = False
    have_exploit = False
    have_strategy_table = False

    if strat_data:
        build_strategy_table_viewer(variant, pot_key, base_dir, strat_data, ev_data)
        have_strategy_table = True

    # regret plots
    seq_buckets_reg: Dict[str, List[str]] = {}
    reg_count = 0
    if reg_data:
        seqs_data = reg_data.get("sequences", {})
        if isinstance(seqs_data, dict):
            for seq, seq_info in seqs_data.items():
                if not isinstance(seq_info, dict):
                    continue
                actor = seq_info.get("actor", "?")
                actions = seq_info.get("actions", []) or []
                buckets_data = seq_info.get("buckets", {}) or {}

                bucket_list = []
                for bkt, bkt_regrets in buckets_data.items():
                    if not isinstance(bkt, str):
                        continue
                    if not bkt_regrets or not actions:
                        continue
                    title = f"{variant} pot{pot_key} | {actor} | {pretty_seq(seq)} | {bkt}"
                    outpath = dirs["regret"] / f"seq_{safe_seq_id(seq)}_bucket_{safe_bucket_id(bkt)}.png"
                    plot_regret(bkt_regrets, actions, tracked_iters, title, outpath)
                    bucket_list.append(bkt)
                    reg_count += 1

                if bucket_list:
                    seq_buckets_reg[seq] = order_buckets(bucket_list)

    if reg_count:
        print(f"    {reg_count} regret plots")
        build_viewer_html(variant, pot_key, "regret", seq_buckets_reg, base_dir)
        have_regret = True

    # strategy plots
    seq_buckets_evo: Dict[str, List[str]] = {}
    evo_count = 0
    if evo_data:
        evo_iters = evo_data.get("tracked_iterations", tracked_iters)
        seqs_data = evo_data.get("sequences", {})
        if isinstance(seqs_data, dict):
            for seq, seq_info in seqs_data.items():
                if not isinstance(seq_info, dict):
                    continue
                actor = seq_info.get("actor", "?")
                actions = seq_info.get("actions", []) or []
                buckets_data = seq_info.get("buckets", {}) or {}

                bucket_list = []
                for bkt, bkt_evo in buckets_data.items():
                    if not isinstance(bkt, str):
                        continue
                    if not bkt_evo or not actions:
                        continue
                    title = f"{variant} pot{pot_key} | {actor} | {pretty_seq(seq)} | {bkt}"
                    outpath = dirs["strategy"] / f"seq_{safe_seq_id(seq)}_bucket_{safe_bucket_id(bkt)}.png"
                    plot_strategy(bkt_evo, actions, evo_iters, title, outpath)
                    bucket_list.append(bkt)
                    evo_count += 1

                if bucket_list:
                    seq_buckets_evo[seq] = order_buckets(bucket_list)

    if evo_count:
        print(f"    {evo_count} strategy plots")
        build_viewer_html(variant, pot_key, "strategy", seq_buckets_evo, base_dir)
        have_strategy = True

    if exp_data:
        ex_iters = exp_data.get("tracked_iterations", [])
        ex_vals = exp_data.get("exploitability", None)
        if ex_vals is None:
            ex_vals = exp_data.get("exploitability_mbb_per_g", exp_data.get("approx_exploitability_mbb_per_g", []))

        outpath = dirs["exploitability"] / "exploitability.png"
        plot_exploit(ex_iters, ex_vals, f"{variant} pot{pot_key} | Exploitability", outpath)
        print("    1 exploitability plot")
        have_exploit = True

    build_pot_index_html(variant, pot_key, base_dir, have_regret, have_strategy, have_exploit, have_strategy_table)


# runs the full script from the command line
def main():
    parser = argparse.ArgumentParser(description="Generate solver diagnostic plots + HTML viewers.")
    parser.add_argument("--variant", choices=["1draw", "1draw_bb", "2draw", "nl", "all"], default="all")
    parser.add_argument("--pot", type=int, default=None, help="Optional: plot only this pot (otherwise auto-detect).")
    args = parser.parse_args()

    variants = ["1draw", "1draw_bb", "2draw", "nl"] if args.variant == "all" else [args.variant]

    print("plot_utils: generating diagnostic plots")
    print(f"  data dir: {_DATA_DIR}")

    for v in variants:
        sub = _DATA_DIR / v
        pots = [args.pot] if args.pot is not None else detect_pots(sub)
        process_variant(v, pots)

    print("\nall plots done!")
    print(f"output: {_DATA_DIR}/plots_*/")


if __name__ == "__main__":
    main()
