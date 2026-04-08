# 2-7 Triple Draw CFR Solver

A complete CFR (Counterfactual Regret Minimization) solver for 2-7 Triple Draw poker final round scenarios.

## Directory Structure

```
triple_draw/
├── run_solvers              # Shortcut script to run all solvers
├── engine/                  # CFR solver implementations
│   ├── cfr_1draw.py          # 1-Draw Limit solver (4-card seeds, draw 1)
│   ├── cfr_1draw_bb.py       # 1-Draw with BB reraise range
│   ├── cfr_2draw.py          # 2-Draw Limit solver (3-card seeds, draw 3)
│   ├── cfr_nl.py             # No-Limit solver (pot-based betting)
│   └── cfr_nl_bb.py          # No-Limit with BB reraise range
├── solver/                  # Solver orchestration scripts
│   ├── run_solvers.py        # Main runner for all solvers
│   └── build_solver_data.py  # Merges JSON outputs and generates plots
├── data/                    # Output directory for strategy JSON files
│   ├── strat_1draw.json
│   ├── strat_1draw_bb.json
│   ├── strat_2draw.json
│   ├── strat_nl.json
│   └── strat_nl_bb.json
└── frontend/                # Web interface
    ├── index.html
    ├── css/
    │   └── style.css
    └── js/
        ├── app.js              # Main application controller
        ├── game.js             # Game logic and state management
        ├── ui.js               # UI rendering and interactions
        ├── evaluator.js        # Hand evaluation
        └── solver_data.js      # Generated strategy data
```

## Modes

### 1-Draw Limit (`1draw`)
- 4-card starting seeds
- Draw 1 card to complete 5-card hand
- Limit betting (1 BB bets, raise schedule: 1,2,3,4 BB)
- BB acts first
- Pots: $3, $5, $7

### 1-Draw BB Reraise (`1draw_bb`)
- Same as 1-Draw but BB uses tighter reraise seed range
- Smaller BB grid for stronger defending range

### 2-Draw Limit (`2draw`)
- 3-card starting seeds
- **Draw 3 cards** to complete 5-card hand
- Limit betting
- Pots: $5, $7

### No Limit (`nl`)
- 4-card starting seeds
- Draw 1 card
- Pot-based bet sizing: 33%, 75%, 133%, All-in
- 25 BB starting stack
- Single pot size: $5

### No Limit BB Reraise (`nl_bb`)
- Same as NL but BB uses tighter seed range
- Stronger defending range for BB

## Usage

### Running Solvers

```bash
# Run all solvers (from triple_draw/ directory)
./run_solvers

# Run with custom iterations
./run_solvers --iterations 500000

# Run specific modes only
./run_solvers --modes 1draw,nl

# Quick test mode (fewer iterations)
./run_solvers --quick

# Regenerate plots only (skip solver runs)
./run_solvers --plots-only
```

### Building Frontend Data

After running solvers, the data is automatically merged. To manually rebuild:

```bash
python3 solver/build_solver_data.py
```

This generates:
- `frontend/js/solver_data.js` - Merged strategy data
- `engine/convergence_plots/` - Strategy convergence plots
- `engine/regret_plots/` - Regret evolution plots
- `engine/exploit_plots/` - Exploitability plots

### Using the Frontend

Open `frontend/index.html` in a web browser to:
- Deal hands and see GTO strategy recommendations
- Explore different game states
- View bucket-by-bucket action frequencies

## Solver Outputs

Each solver generates:

1. **Strategy JSON** (`data/strat_*.json`)
   - Bucket frequencies
   - Action probabilities per bucket
   - Reach probabilities

2. **Convergence Data** (embedded in JSON)
   - Strategy history per bucket
   - Regret history per bucket
   - Exploitability per decision node

3. **Plots** (in `engine/` subdirectories)
   - Strategy convergence (% vs iterations)
   - Cumulative regret vs iterations
   - Exploitability (mbb/g) vs iterations

## Requirements

```
pip install numpy matplotlib
```

## Technical Details

- **CFR Algorithm**: Vanilla CFR with epsilon-greedy exploration
- **Iterations**: Default 250,000 per mode/pot
- **Checkpoint Interval**: Every 5,000 iterations
- **Bucket System**: 27 buckets based on hand strength
- **Action Abstraction**: Limit (check/bet/call/fold/raise) or NL (pot-based)

## License

MIT License
