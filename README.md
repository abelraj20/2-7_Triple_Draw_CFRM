# 2-7 Triple Draw CFR+ Poker Solver

## Directory Structure

```
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

## Modes

### 1-Draw Limit (`cfr_1draw`)
- 4-card starting seeds
- **Draw 1 card** to complete 5-card hand
- Limit betting (Fixed bets of 1 chip, raise schedule: 1,2,3,4 chips)
- BB acts first in final round
- Pots: $3, $5, $7

### 2-Draw Limit (`cfr_2draw`)
- 3-card starting seeds
- **Draw 2 cards** to complete 5-card hand
- Limit betting
- Pots: $7

### No Limit (`cfr_nl`)
- 4-card starting seeds
- Draw 1 card
- Pot-based bet sizing: 40%, 80%, 120%, All-in
- 25 chip current stacks
- Single pot size: $5

```bash
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

1. **Strategy JSON**
   - Bucket frequencies
   - Action probabilities per bucket
   - Reach probabilities

2. **Convergence Data**
   - Strategy history per bucket
   - Regret history per bucket
   - Exploitability per decision node

3. **Plots**
   - Strategy convergence (% vs iterations)
   - Cumulative regret vs iterations
   - Exploitability (mbb/g) vs iterations

## Requirements

```
pip install numpy matplotlib
```

## Technical Details

- **CFR Algorithm**: CFR+
- **Iterations**: Default 250,000 per mode/pot
- **Checkpoint Interval**: Every 5,000 iterations
- **Bucket System**: 27 buckets based on hand strength
- **Action Abstraction**: Limit (check/bet/call/fold/raise) or NL (pot-based)

## License

MIT License
