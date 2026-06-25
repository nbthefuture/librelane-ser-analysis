# LibreLane SER Analysis Pipeline

This repository contains an automated infrastructure flow for analyzing
**Soft Error Rates (SER)** on custom digital cell layouts (such as `tto_mux`).
The pipeline integrates **LibreLane**, **CircuitOps**, **OpenROAD**, and the
**Sky130 PDK** into a fully reproducible development environment managed via
**Nix Flakes**.

The core idea: run a design through LibreLane's RTL-to-GDSII flow, automatically
hand the final layout off to CircuitOps to generate gate-level IR/graph tables,
build a NetworkX graph from those tables, and compute an analytical
**Error Propagation Probability (EPP)** estimate — identifying which gates are
most likely to propagate a soft error (e.g. a cosmic ray strike) to a circuit
output.

---

##  Prerequisites & System Requirements

- **Operating System:** Linux (Ubuntu 22.04+ recommended) or macOS.
- **Disk Space:** At least 20–30 GB free (for compiled EDA toolchains and the
  unpacked Sky130 PDK libraries).
- **Git:** Installed and configured on your local system.

No Docker is required. No manual Python package installation is required.
Everything (including `pandas` and `networkx`) is declared in this repo's
`flake.nix` and provisioned automatically by Nix.

---

##  Step-by-Step Setup Guide

### Step 1: Clone the Repository

This repo includes CircuitOps as a **git submodule**, so a single recursive
clone pulls down LibreLane, CircuitOps, and the pipeline scripts together as
one unit:

```bash
git clone --recursive https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

> If you ever clone without `--recursive` by mistake, run
> `git submodule update --init --recursive` afterward to pull in CircuitOps.

### Step 2: Install the Nix Package Manager

Nix ensures that your environment has all required dependencies and packages. No manual configuration should be required for packages such as networkx or pandas.

Run the official multi-user installation script:

```bash
curl -L https://nixos.org/nix/install | sh -s -- --daemon
```

Follow the on-screen prompts. Once installation finishes, restart your
terminal session or follow the commands given in nix.

### Enable Flakes Support

This project uses Nix Flakes directly (`nix develop`), so the experimental
flakes feature must be enabled. In the same directory, run the following commands:

```bash
mkdir -p ~/.config/nix
echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf
```


Save and exit. No restart is required — this takes effect on your next
`nix` command.

### Step 3: Launch the Isolated Environment

From the root of the project directory:

```bash
nix develop
```

- **First-run execution:** Nix will download pre-built binaries or compile
  packages from scratch (including OpenROAD, Yosys, Magic, KLayout, and the
  Python environment with `pandas`/`networkx` pre-installed). This can take
  anywhere from **5 to 45 minutes** depending on your hardware and network
  speed.
- Subsequent runs are fast (seconds) since Nix caches everything it builds.
- Once complete, your shell prompt changes to indicate you're inside the
  active Nix environment.

**Verify the environment is correctly set up:**

```bash
which openroad
python3 -c "import pandas, networkx; print('Python deps OK')"
```

Both commands should succeed with no errors.

---

## PDK Management (Ciel Toolchain)

The SER simulation relies on a locked version of the Sky130 PDK. This
pipeline targets PDK variant hash:

```
0fe599b2afb6708d281543108caf8310912f54af
```

### Locating an Existing Local PDK

If your system has already run Ciel-managed projects before, check whether
this specific version is already cached (should be located in your root directory once inside the nix shell):

```bash
ls -la ~/.ciel/ciel/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af/sky130
```

Or check via the Ciel CLI from inside the `nix develop` shell:

```bash
ciel ls
```

### Downloading the PDK (If Missing)

If the `.ciel` directory is empty or this specific hash is missing, fetch
and activate it:

```bash
# 1. Fetch the exact tarball distribution
ciel fetch --pdk-family sky130 0fe599b2afb6708d281543108caf8310912f54af

# 2. Set this hash version as the active PDK
ciel enable --pdk-family sky130 0fe599b2afb6708d281543108caf8310912f54af
```

---

##  Configuring the Pipeline Path

Before running the pipeline, point the runner script at your local PDK path.

1. Open the runner file:

```bash
nano my_designs/tto_mux/run_ser_flow.py
```

2. Locate the hardcoded PDK path variable and update it with **your**
   machine's actual home directory and username:

```python
# Replace 'your_username' with your actual system username
PDK_PATH = "/home/your_username/.ciel/ciel/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af/sky130"
```

> Tip: run `echo $HOME` to confirm your home directory path exactly.

---

##  Executing the Simulation Pipeline

With your Nix shell active (`nix develop`) and the PDK path configured, run
the complete analysis:

```bash
python3 my_designs/tto_mux/run_ser_flow.py
```

### What Happens Behind the Scenes

1. **LibreLane Classic Flow** — the design runs through synthesis,
   floorplanning, placement, CTS, routing, and signoff, producing the final
   netlist, DEF, SPEF, and SDC files.
2. **CircuitOps Parsing** — the custom `SERAnalysisStep` stages and
   compresses these final layout files, then invokes CircuitOps'
   `generate_tables.py` (via OpenROAD's built-in Python interpreter) to
   generate gate-level IR/graph tables.
3. **Graph Construction** — `circuitops_bridge.py` reads the generated CSV
   IR tables and builds a NetworkX directed graph representing the
   gate-level circuit.
4. **SER / EPP Calculation** — `epp_algorithm.py` runs the analytical Error
   Propagation Probability algorithm (based on the Asadi & Tahoori method)
   across every gate, identifying average circuit-wide vulnerability and
   ranking the top hardening candidate gates.

### Where to Find Your Results

After the run completes, results are written into the LibreLane run
directory, inside the SER step's own step folder:

```
my_designs/tto_mux/runs/ser_extraction_run/<NN>-librelane-seranalysis/
├── ser_report.txt      # human-readable summary
└── ser_metrics.json    # machine-readable metrics
```

These metrics are also merged into LibreLane's standard run metrics under:

- `ser__avg_epp`
- `ser__max_epp`
- `ser__gate_count`

You can inspect the raw CircuitOps IR tables directly at:

```
CircuitOps/IRs/sky130hd/tto_mux/
```



## Understanding the SER / EPP Report

**EPP (Error Propagation Probability)** is the probability that a fault at a
given gate propagates through the circuit and changes a primary output. It's
computed analytically using signal probabilities (assuming each primary
input is equally likely to be 0 or 1) and the structural masking behavior of
each gate type (AND, OR, NAND, NOR, XOR, etc.).

- **Average EPP** — overall soft-error sensitivity of the circuit.
- **Peak EPP** — the single most vulnerable gate's propagation probability.
- **Top hardening candidates** — gates ranked by individual EPP, useful for
  prioritizing a limited hardening budget (e.g. redundant logic or hardened
  cell variants).

---

## Known Limitations

- The EPP algorithm assumes primary inputs are independent and equally
  likely (P = 0.5). It does not yet model realistic input probability
  distributions or sequential/temporal correlation.
- Reconvergent fanout (a fault reaching an output through multiple paths)
  can cause the analytical method to slightly over-approximate EPP compared
  to true logic simulation — this is a known property of the underlying
  Asadi & Tahoori method, not a bug in this implementation.
- Sequential elements are excluded from the graph; EPP is computed over the
  combinational logic cone only.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `error: experimental Nix feature 'flakes' is disabled` | `experimental-features` not set in `nix.conf` | Re-check Step 2 — add the line, save, retry `nix develop` |
| `ModuleNotFoundError: No module named 'pandas'` (or `networkx`) | Not inside the `nix develop` shell, or `flake.nix` changes weren't picked up | Confirm you're inside the shell; if you edited `flake.nix`, exit and re-run `nix develop` to rebuild |
| `openroad: command not found` | Not inside the Nix dev shell | Run `nix develop` from the repo root first |
| `FileNotFoundError` referencing CircuitOps paths | Submodule not initialized | Run `git submodule update --init --recursive` |
| `TypeError: Wrong number or type of arguments for overloaded function 'dbBlock_globalConnect'` | CircuitOps' `openroad_helpers.py` was written against an older OpenROAD ODB API; current OpenROAD's `globalConnect` signature has changed | Check the live signature with `openroad -python -c "import odb; help(odb.dbBlock.globalConnect)"` and update the call in `openroad_helpers.py` to match (see inline comment in that file for the patched call) |
| PDN / floorplan errors on tiny designs | Die area too small for default PDN strap rules | Use a `DIE_AREA` of at least `[0,0,100,100]` with low `FP_CORE_UTIL` (10–20) in `config.json` |
| Wrong / outdated PDK path | `PDK_PATH` in `run_ser_flow.py` doesn't match this machine | Re-run the `ciel ls` check from the PDK section and update the path |

---

## Credits

- **LibreLane** — open-source RTL-to-GDSII flow:
  https://github.com/librelane/librelane
- **CircuitOps** — ML-friendly circuit graph/IR generation built on
  OpenROAD: https://github.com/NVlabs/CircuitOps
- **EPP / SER methodology** — based on the analytical Error Propagation
  Probability approach introduced by Asadi & Tahoori for soft error rate
  estimation in digital circuits.
