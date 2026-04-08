# 2-7 Triple Draw CFR+ Poker Solver

## Instructions

### Requirements

Install the base requirements:

```bash
pip install numpy matplotlib
```

If you want to use `build_solver_data.py` to export strategy table PNGs, you also need:

```bash
pip install pillow playwright
playwright install chromium
```

### Running the Solvers

The solver scripts can be run directly from the `solver/` folder.

#### 1-Draw

```bash
python3 solver/cfr_1draw.py
```

Common arguments:

- `--seed`  
  Random seed.  
  Default: `42`

- `--iters` or `--iterations`  
  Number of CFR+ iterations.  
  Default: `50000`

- `--pots`  
  Comma-separated pot sizes to run.  
  Default: the script's configured pot list

- `--out-prefix`  
  Output folder name inside `data/`.  
  Default: `1draw`

- `--br-policy-iters`  
  Best-response policy iterations.  
  Default: `16`

- `--exp-print-step`  
  Exploitability print / tracking interval.  
  Default: `100`

- `--ev-samples`  
  EV samples per bucket.  
  Default: `800`

- `--sim-init-freq-n`  
  Monte Carlo simulations used for root bucket frequencies.  
  Default: `200000`

- `--time-export`  
  Print export timing.

- `--time-total`  
  Print total script runtime.

- `--stop-expl-mbb`  
  Stop early once exploitability reaches the target.

- `--dense-expl-below-mbb`  
  Recompute exploitability every iteration once below the given threshold.

Example:

```bash
python3 solver/cfr_1draw.py --iterations 50000 --pots 3,5,7 --out-prefix 1draw
```

#### 2-Draw

```bash
python3 solver/cfr_2draw.py
```

Arguments similar to 1-draw model.

Example:

```bash
python3 solver/cfr_2draw.py --iters 50000
```

#### No-Limit

```bash
python3 solver/cfr_nl.py
```

Unique Arguments:

- `--stack`  
  Final-round stack size.  
  Default: `25`

- `--start-pot`  
  Final-round starting pot.  
  Default: `5`

Example:

```bash
python3 solver/cfr_nl.py --iters 250000 --stack 25 --start-pot 5
```

#### Card Removal

```bash
python3 solver/cfr_rem.py
```

Unique arguments:

- `--discarded-twos`  
  Comma-separated discarded-deuce cases to run.  
  Default: `0`

Example:

```bash
python3 solver/cfr_rem.py --discarded-twos 0,1,2,3 --out-prefix cfr_rem
```

### Building Frontend Data

After running the solvers, rebuild the merged frontend data with:

```bash
python3 solver/build_solver_data.py
```

This writes:

- `frontend/js/solver_data.js`
- `frontend/js/solver_data.json`

By default it can also export per-sequence strategy table PNGs into each variant folder under:

- `data/1draw/strategy_pngs/`
- `data/2draw/strategy_pngs/`
- `data/nl/strategy_pngs/`
- `data/cfr_rem_0/strategy_pngs/`
- `data/cfr_rem_1/strategy_pngs/`
- `data/cfr_rem_2/strategy_pngs/`
- `data/cfr_rem_3/strategy_pngs/`

Useful `build_solver_data.py` arguments:

- `--meta-only-ev`  
  Store EV metadata only instead of full EV tables.

- `--no-export-strategy-pngs`  
  Skip PNG strategy-table export.

- `--png-dir-name`  
  Rename the PNG output folder.  
  Default: `strategy_pngs`

- `--png-layout`  
  PNG layout preset.  
  Options: `full`, `bucket-rate`, `bucket-rate-no-overall`, `bars-only`  
  Default: `full`

- `--png-dpi`  
  PNG DPI.  
  Default: `600`

- `--variant`  
  Restrict export to one or more variants. Repeat argument to include multiple variants.

Example:

```bash
python3 solver/build_solver_data.py --variant 1draw --variant 2draw --png-layout bucket-rate
```

### Generating Plot Viewers

To generate diagnostic plots and HTML viewers from existing solver output:

```bash
python3 solver/plot_utils.py --variant all
```

Optional arguments:

- `--variant`  
  One of `1draw`, `2draw`, `nl`, or `all`  
  Default: `all`

- `--pot`  
  Generate output for one pot only.  
  Default: auto-detect from the files in each variant folder

Example:

```bash
python3 solver/plot_utils.py --variant 1draw --pot 5
```

### Using the Frontend

To explore the solved strategies yourself, go into the `frontend/` folder and open `index.html` in a web browser. Clicking `frontend/index.html` opens the frontend in a new tab, where you can:

- deal hands and inspect strategy recommendations
- explore different game states and action sequences
- view bucket-by-bucket action frequencies
- experiment interactively using the merged solver data in `frontend/js/solver_data.js`

## Modes

### 1-Draw Limit (`cfr_1draw`)

- 4-card starting seeds
- **Draw 1 card** to complete a 5-card hand
- Limit betting
- Raise schedule: `1, 2, 3, 4` chips
- BB acts first in the final round
- Uses its configured pot list unless overridden with `--pots`

### 2-Draw Limit (`cfr_2draw`)

- 3-card starting seeds
- **Draw 2 cards** to complete a 5-card hand
- Limit betting
- BB acts first in the final round
- Uses the internally configured pot list
- Default pot: `7`

### Card Removal (`cfr_rem`)

- 1-draw limit structure with card-removal variants
- Models the effect of removed deuces on the final-round game
- BTN conditions on the discarded-deuce count while BB does not
- Use `--discarded-twos 0,1,2,3` to generate all four removal cases
- Running all four cases with the default output prefix creates:
  - `cfr_rem_0`
  - `cfr_rem_1`
  - `cfr_rem_2`
  - `cfr_rem_3`

### No Limit (`cfr_nl`)

- 4-card starting seeds
- **Draw 1 card** to complete a 5-card hand
- No-limit betting abstraction
- Pot-based bet sizes: `40%`, `80%`, `120%`, and all-in
- Raise options include `86%`, `111%`, and all-in depending on the branch
- Final-round stack size defaults to `25`
- Final-round starting pot defaults to `5`

## Solver Outputs

The `data/` folder stores the solver outputs and generated visualisations.

### What goes inside `data/`

The `data/` folder contains files written by three parts of the pipeline:

1. **The solver scripts**  
   These write the raw model outputs for each variant and pot size.

2. **`plot_utils.py`**  
   This reads the solver JSON files and generates PNG plots plus HTML viewers.

3. **`build_solver_data.py`**  
   This merges solver outputs for the frontend and can also export per-sequence strategy table PNGs into each variant folder.

Typical contents inside a variant folder such as `data/1draw/`, `data/2draw/`, `data/nl/`, or `data/cfr_rem_0/` include:

- `bucket_freq_by_player.json`
- `bucket_freq_by_sequence_potX.json`
- `strategies_potX.json`
- `regrets_potX.json`
- `evolution_potX.json`
- `exploitability_potX.json`
- `ev_potX.json`

Depending on the solver and export step, the variant folder may also contain:

- EV spreadsheet exports
- `strategy_pngs/`
- `manifest.json` for exported strategy PNGs

### Accessing Strategy, Regret, and Exploitability Outputs

After running `plot_utils.py`, the generated plots and viewers are stored under:

- `data/plots_1draw/pot5/`
- `data/plots_2draw/pot7/`
- `data/plots_nl/pot5/`

and similarly for any other generated variant / pot combinations.

Inside each `data/plots_<variant>/pot<pot>/` folder, you can access:

- `regret/`  
  PNG regret plots for each sequence / bucket

- `strategy/`  
  PNG strategy convergence plots for each sequence / bucket

- `exploitability/`  
  Exploitability graph

- `strategy_tables/`  
  HTML strategy-table pages

- `index.html`  
  Landing page for that pot

- `regret_viewer.html`  
  HTML viewer for regret plots

- `strategy_viewer.html`  
  HTML viewer for strategy plots

- `strategy_table_viewer.html`  
  HTML viewer for strategy tables

## Technical Details

- **Algorithm**: CFR+
- **1-draw default iterations**: `50000`
- **2-draw default iterations**: `50000`
- **Card-removal default iterations**: `50000`
- **No-limit default iterations**: `250000`
- **1-draw / 2-draw / card-removal / No-limit EV samples per bucket**: `800`
- **1-draw / 2-draw / card-removal / No-limit best-response policy iterations**: `16`

## Directory Structure

```text
triple_plus/
├── data/                          # Solver outputs and generated plot folders
│   ├── 1draw/
│   ├── 2draw/
│   ├── cfr_rem_0/
│   ├── cfr_rem_1/
│   ├── cfr_rem_2/
│   ├── cfr_rem_3/
│   ├── nl/
│   ├── plots_1draw/
│   ├── plots_2draw/
│   └── plots_nl/
├── solver/                        # Core solver scripts and shared utilities
│   ├── build_solver_data.py       # Builds frontend solver data from outputs
│   ├── cfr_1draw.py               # 1-draw solver
│   ├── cfr_2draw.py               # 2-draw solver
│   ├── cfr_common_bucketgame.py   # Shared CFR / bucket-game logic
│   ├── cfr_nl.py                  # No-limit solver
│   ├── cfr_rem.py                 # Card-removal solver
│   └── plot_utils.py              # Plotting helpers
└── frontend/                      # Web interface
    ├── index.html
    ├── css/
    │   └── style.css
    └── js/
        ├── app.js                 # Main application controller
        ├── game.js                # Game logic and state handling
        ├── seeds.js               # Seed / range definitions
        ├── solver_data.js         # Generated solver data
        └── ui.js                  # UI rendering and interactions
```

## License

MIT License
