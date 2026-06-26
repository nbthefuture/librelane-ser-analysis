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

## Table of Contents

- [Prerequisites and System Requirements](#prerequisites-and-system-requirements)
- [Step-by-Step Setup Guide](#step-by-step-setup-guide)
- [PDK Management (Ciel Toolchain)](#pdk-management-ciel-toolchain)
- [Executing the Simulation Pipeline](#executing-the-simulation-pipeline)
- [Repository Layout](#repository-layout)
- [Demo Circuit: tto\_mux](#demo-circuit-tto_mux)
- [Understanding the SER / EPP Report](#understanding-the-ser--epp-report)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [References](#references)
- [Credits](#credits)

---

## Prerequisites and System Requirements

- **Operating System:** Linux (Ubuntu 22.04+ recommended) or macOS.
- **Disk Space:** At least 20–30 GB free (for compiled EDA toolchains and the
  unpacked Sky130 PDK libraries).
- **Git:** Installed and configured on your local system.

No Docker is required. No manual Python package installation is required —
everything (including `pandas` and `networkx`) is declared in this repo's
`flake.nix` and provisioned automatically by Nix.

---

## Step-by-Step Setup Guide

### Step 1: Clone the Repository

This repo includes CircuitOps as a **git submodule**, so a single recursive
clone pulls down LibreLane, CircuitOps, and the pipeline scripts together as
one unit:

```bash
git clone --recursive https://github.com/nbthefuture/librelane-ser-analysis.git
cd librelane-ser-analysis
```

> If you ever clone without `--recursive` by mistake, run
> `git submodule update --init --recursive` afterward to pull in CircuitOps.

### Step 2: Install the Nix Package Manager

Nix ensures that your compiler toolchain, C++ dependencies, and Python environments match identically across machines
with no manual configuration.

Run the official multi-user installation script:

```bash
curl -L https://nixos.org/nix/install | sh -s -- --daemon
```

Follow the on-screen prompts. Once installation finishes, restart your
terminal session (or `source` your shell profile) to activate the `nix`
command.

### Enable Flakes Support

This project uses Nix Flakes directly (`nix develop`), so the experimental
flakes feature must be enabled. Open (or create) your global Nix
configuration file:

```bash
mkdir -p ~/.config/nix
echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf
```

Add the following line:

```
experimental-features = nix-command flakes
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

LibreLane automatically locates your installed PDK with **no path
configuration needed** — it checks `~/.ciel` by default and uses whichever
sky130 version `ciel` currently has marked as **enabled**. You do not need
to hardcode any path or hash anywhere in this repo.

### Check what's installed

```bash
ciel ls --pdk-family sky130
```

This lists every installed sky130 version and shows which one (if any) is
currently marked `(enabled)`.

### If nothing is installed

Fetch and enable a known-good version:

```bash
ciel fetch --pdk-family sky130 0fe599b2afb6708d281543108caf8310912f54af
ciel enable --pdk-family sky130 0fe599b2afb6708d281543108caf8310912f54af
```

### If a version is installed but not enabled

This is a common situation where `ciel ls` can show an installed version with no
`(enabled)` marker next to it. LibreLane will fail with
`The PDK sky130A was not found.` until you explicitly enable one:

```bash
ciel enable --pdk-family sky130 <hash-from-ciel-ls>
```

Re-run `ciel ls --pdk-family sky130` afterward to confirm `(enabled)` now
appears next to that version. Once enabled, LibreLane will find it
automatically on every run — this is a one-time, per-machine setup step.

---

## Executing the Simulation Pipeline

With your Nix shell active (`nix develop`) and a PDK enabled, navigate to the tto\_mux example design in the my\_designs folder. Execute the full flow with the following command:

```bash
python3 run_ser_flow.py
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
    ser_report.txt      human-readable summary
    ser_metrics.json    machine-readable metrics
```

These metrics are also merged into LibreLane's standard run metrics under:

- `ser__avg_epp`
- `ser__max_epp`
- `ser__gate_count`

You can inspect the raw CircuitOps IR tables directly at:

```
CircuitOps/IRs/sky130hd/tto_mux/
```

---

## Repository Layout

```
flake.nix                      Nix flake — pulls in LibreLane + pandas/networkx
README.md                      this file
librelane/                     LibreLane source (flows, steps, state, config)
CircuitOps/                    git submodule — CircuitOps IR/graph generator
my_designs/tto_mux/
    tto_mux.v                  Verilog source
    config.json                LibreLane design configuration
    run_ser_flow.py             custom flow + SER step definition
    circuitops_bridge.py        builds NetworkX graph from IR tables
    epp_algorithm.py            analytical EPP / SER algorithm
```

---

## Demo Circuit: tto\_mux

`tto_mux` is a 2-to-1 multiplexer built from exactly four gates, used as a
small, hand-verifiable proof of concept for the full pipeline. It is
intentionally simple enough that every EPP value below can be checked by
hand against the pipeline's output.

### Signal Probabilities

Assuming each primary input is independently equally likely to be 0 or 1
(P = 0.5):

```
P(S_n) = 1 - P(S)              = 1 - 0.5  = 0.5
P(G1)  = P(A) * P(S_n)         = 0.5*0.5  = 0.25
P(G2)  = P(B) * P(S)           = 0.5*0.5  = 0.25
P(Y)   = P(G1) + P(G2) - P(G1)*P(G2)
       = 0.25 + 0.25 - 0.0625  = 0.4375
```



### Summary Table

*(A circuit diagram illustrating this gate structure will be added here.)*

---

## Understanding the SER / EPP Report

**EPP (Error Propagation Probability)** is the probability that a fault at a
given gate propagates through the circuit and changes a primary output. It's
computed analytically using signal probabilities (assuming each primary
input is equally likely to be 0 or 1) and the structural masking behavior of
each gate type (AND, OR, NAND, NOR, XOR, etc.).

- **Average EPP** — overall soft-error sensitivity of the circuit.
- **Peak EPP** — the single most vulnerable gate's propagation probability.
- **Top hardening candidates** — gates ranked by individual EPP

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
| `librelane.config.config.InvalidConfig: The PDK sky130A was not found.` | A sky130 PDK version is installed via `ciel` but not marked `(enabled)` | Run `ciel ls --pdk-family sky130` to find the installed hash, then `ciel enable --pdk-family sky130 <hash>` |

---

## References

G. Asadi and M. B. Tahoori, "An analytical approach for soft error rate
estimation in digital circuits," *2005 IEEE International Symposium on
Circuits and Systems (ISCAS)*, Kobe, Japan, 2005, pp. 2991-2994 Vol. 3,
doi: 10.1109/ISCAS.2005.1465256

---

## Credits

- **LibreLane** — open-source RTL-to-GDSII flow:
  https://github.com/librelane/librelane
- **CircuitOps** — ML-friendly circuit graph/IR generation built on
  OpenROAD: https://github.com/NVlabs/CircuitOps
- **EPP / SER methodology** — based on the analytical Error Propagation
  Probability approach introduced by Asadi & Tahoori (see References) for
  soft error rate estimation in digital circuits.
