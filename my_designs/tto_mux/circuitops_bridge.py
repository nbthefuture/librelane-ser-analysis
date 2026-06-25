"""
circuitops_bridge.py

Reads CircuitOps IR tables (csv files), builds a NetworkX directed graph, and runs the
Asadi & Tahoori EPP / SER analytical algorithm (epp_algorithm.py) on the result.


Usage:
    python3 circuitops_bridge.py <ir_directory>

The ir_directory must contain at minimum:
    cell_properties.csv
    cell_cell_edge.csv

    Optionally (improves PI identification):
        pin_properties.csv

The script handles:
    - Physical / filler cells          → silently removed
    - Sequential cells (DFF, latch)    → removed; combinational only analysed
    - Unknown gate types               → warned and removed
    - Circuits too large to simulate   → analytical EPP only (no hang)
    - Reconvergent fanout mismatches   → reported clearly, not hidden
"""

import os
import sys
import pandas as pd
import networkx as nx
from collections import Counter
from epp_algorithm import (
    normalise_gate, signal_probability,
    compute_epp, fault_injection_epp, gate_output
)


# Cell classification 
SKY130_PREFIXES = (
    "sky130_fd_sc_hd__", "sky130_fd_sc_hdll__",
    "sky130_fd_sc_hs__",  "sky130_fd_sc_ms__",
    "sky130_fd_sc_ls__",
)

def _base(libcell: str) -> str:
    """Strip sky130 prefix and drive-strength suffix."""
    name = libcell.lower()
    for pfx in SKY130_PREFIXES:
        if name.startswith(pfx):
            name = name[len(pfx):]
            break
    return name.rsplit("_", 1)[0] if "_" in name else name


PHYS_KW  = ("decap", "fill", "tap", "endcap", "phy")
SEQ_KW   = ("dff", "latch", "dlxtp", "dfxtp", "dfbbp", "sdff",
             "dfrbp", "sdfbb", "dfxbp")
BUF_KW   = ("buf", "clkbuf", "dlygate", "clkdlybuf", "delhvt", "clkinv")

# Gate classification
def classify(libcell: str) -> str:
    """
    Return one of: PHYS | SEQ | BUF | <canonical gate> | UNKNOWN
    """
    base = _base(libcell)
    if any(k in base for k in PHYS_KW): return "PHYS"
    if any(k in base for k in SEQ_KW):  return "SEQ"
    if any(k in base for k in BUF_KW):  return "BUF"
    gate = normalise_gate(libcell)
    return gate  # may be UNKNOWN


def is_filler_row(row) -> bool:
    if str(row["cell_name"]).upper().startswith("PHY_EDGE"):
        return True
    try:
        if int(row.get("is_filler", 0)):
            return True
    except (ValueError, TypeError):
        pass
    return False


# CSV loader
def _load(ir_dir: str, filename: str) -> pd.DataFrame | None:
    path = os.path.join(ir_dir, filename)
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    return df


# Graph builder
def build_graph(ir_dir: str) -> nx.DiGraph:
    print("\n" + "=" * 58)
    print("  CircuitOps → EPP  |  building graph")
    print(f"  {ir_dir}")
    print("=" * 58)

    # cells 
    cells = _load(ir_dir, "cell_properties.csv")
    if cells is None or cells.empty:
        print("  ERROR: cell_properties.csv missing or empty.")
        return nx.DiGraph()

    cells = cells[~cells.apply(is_filler_row, axis=1)].copy()
    cells["_cls"] = cells["libcell_name"].apply(classify)
    cells["cx"]   = (cells["x0"] + cells["x1"]) / 2.0
    cells["cy"]   = (cells["y0"] + cells["y1"]) / 2.0

    counts = Counter(cells["_cls"])
    print("\n  Cell breakdown:")
    for k, v in sorted(counts.items()):
        print(f"    {k:10s} : {v}")

    # warn on UNKNOWN
    unk = cells[cells["_cls"] == "UNKNOWN"]
    if not unk.empty:
        print(f"\n  [WARN] {len(unk)} unrecognised cell type(s) — removed:")
        for _, r in unk.head(8).iterrows():
            print(f"         {r['cell_name']:30s}  {r['libcell_name']}")
        if len(unk) > 8:
            print(f"         ... +{len(unk)-8} more")

    seq = cells[cells["_cls"] == "SEQ"]
    if not seq.empty:
        print(f"\n  [INFO] {len(seq)} sequential cell(s) removed — "
              f"combinational cone only.")

    keep   = cells[~cells["_cls"].isin(["PHYS", "SEQ", "UNKNOWN"])].copy()
    logic  = set(keep["cell_name"])
    print(f"\n  Logic + buf cells kept : {len(keep)}")

    if keep.empty:
        print("  ERROR: no logic cells remain.")
        return nx.DiGraph()

    # PI ports from pin_properties 
    pi_ports: set = set()
    pins = _load(ir_dir, "pin_properties.csv")
    if pins is not None and not pins.empty and "is_port" in pins.columns:
        ports = pins[(pins["is_port"] == 1) & (pins["dir"] == 1)]
        pi_ports = set(ports["pin_name"].astype(str))
        print(f"  PI ports from pins     : {len(pi_ports)}")

    # edges
    edges = _load(ir_dir, "cell_cell_edge.csv")
    if edges is None or edges.empty:
        print("  [WARN] cell_cell_edge.csv missing — no edges.")
        edges = pd.DataFrame(columns=["src", "tar"])

    # normalise column names
    rn = {}
    for c in edges.columns:
        lc = c.lower()
        if lc in ("src","source","from"):   rn[c] = "src"
        elif lc in ("tar","target","dst","to"): rn[c] = "tar"
    edges = edges.rename(columns=rn)

    # build networkx directed graph
    G = nx.DiGraph()

    for _, row in keep.iterrows():
        G.add_node(
            row["cell_name"],
            gate       = row["_cls"],
            libcell    = row["libcell_name"],
            x          = float(row["cx"]),
            y          = float(row["cy"]),
            static_pwr = float(row.get("cell_static_power", 0.0)),
        )

    for name in pi_ports:
        if name not in G:
            G.add_node(name, gate="PI", libcell="PORT",
                       x=0.0, y=0.0, static_pwr=0.0)

    added = skipped = 0
    seq_names = set(seq["cell_name"]) if not seq.empty else set()
    for _, row in edges.iterrows():
        src, tar = str(row["src"]), str(row["tar"])
        if src in seq_names or tar in seq_names:
            skipped += 1; continue
        if src in G and tar in G and src != tar:
            G.add_edge(src, tar); added += 1
        else:
            skipped += 1

    print(f"  Edges added            : {added}  (skipped {skipped})")

    # promote undriven logic nodes to PI
    promoted = 0
    for node in list(G.nodes):
        if G.in_degree(node) == 0 and G.nodes[node]["gate"] != "PI":
            G.nodes[node]["gate"] = "PI"
            promoted += 1
    if promoted:
        print(f"  Promoted to PI         : {promoted} undriven nodes")

    # DAG check
    if not nx.is_directed_acyclic_graph(G):
        cycles = list(nx.simple_cycles(G))
        print(f"\n  [WARN] {len(cycles)} cycle(s) — breaking feedback edges.")
        for cyc in cycles:
            if G.has_edge(cyc[-1], cyc[0]):
                G.remove_edge(cyc[-1], cyc[0])
            if nx.is_directed_acyclic_graph(G):
                break
        print("  Graph is now a DAG.")
    else:
        print("  Topology               : DAG ✓")

    pi_n  = sum(1 for n in G.nodes if G.nodes[n]["gate"] == "PI")
    po_n  = sum(1 for n in G.nodes if G.out_degree(n) == 0)
    print(f"\n  Nodes {len(G.nodes):4d} | Edges {len(G.edges):4d} "
          f"| PIs {pi_n:3d} | POs {po_n:3d}")

    return G


# EPP / SER report

# Maximum PI count for which brute-force simulation is feasible.
# 2^20 = ~1M evaluations — takes a few seconds; 2^25 would hang.
# Could remove this limit for testing purposes
SIM_PI_LIMIT = 20

def run_epp(G: nx.DiGraph, label: str = "Circuit") -> None:
    print(f"\n{'─'*58}")
    print(f"  SER / EPP Report  —  {label}")
    print(f"{'─'*58}")

    if G.number_of_nodes() == 0:
        print("  Graph is empty — nothing to analyse.")
        return

    topo    = list(nx.topological_sort(G))
    pis     = [n for n in topo if G.nodes[n].get("gate") == "PI"]
    outputs = [n for n in topo if G.out_degree(n) == 0]
    gates   = [n for n in topo if G.nodes[n].get("gate") not in ("PI",)]

    if not gates:
        print("  No logic gates found.")
        return
    if not outputs:
        print("  No output nodes found.")
        return

    # signal probability
    sp = signal_probability(G)

    print(f"\n  Signal probabilities:")
    for n in topo:
        g = G.nodes[n].get("gate", "?")
        print(f"    {str(n):28s}  {g:8s}  P(1) = {sp[n]:.4f}")

    # decide whether simulation is feasible
    do_sim = len(pis) <= SIM_PI_LIMIT
    if not do_sim:
        print(f"\n  [INFO] {len(pis)} PIs → simulation skipped "
              f"(limit {SIM_PI_LIMIT}). Analytical only.")

    # EPP table
    hdr = f"  {'Gate':28s}  {'Output':20s}  {'Analytical':>11s}"
    if do_sim:
        hdr += f"  {'Simulated':>10s}  Match"
    print(f"\n{hdr}")
    print("  " + "─" * (72 if do_sim else 50))

    all_epp    = []
    mismatches = 0

    for gate in gates:
        analytical = compute_epp(G, gate, sp)
        simulated  = fault_injection_epp(G, gate) if do_sim else {}

        for out in outputs:
            a = analytical.get(out, 0.0)
            all_epp.append(a)

            if do_sim:
                s  = simulated.get(out, 0.0)
                ok = abs(a - s) < 1e-9
                if not ok:
                    mismatches += 1
                flag = "YES" if ok else f"NO  (Δ={abs(a-s):.2e})"
                print(f"  {str(gate):28s}  {str(out):20s}  {a:11.6f}"
                      f"  {s:10.6f}  {flag}")
            else:
                print(f"  {str(gate):28s}  {str(out):20s}  {a:11.6f}")

    # summary
    avg = sum(all_epp) / len(all_epp) if all_epp else 0.0
    mx  = max(all_epp) if all_epp else 0.0
    mn  = min(all_epp) if all_epp else 0.0

    print(f"\n  {'─'*40}")
    print(f"  Gates analysed : {len(gates)}")
    print(f"  Avg EPP (SER)  : {avg:.6f}")
    print(f"  Max EPP        : {mx:.6f}  ← highest soft-error risk")
    print(f"  Min EPP        : {mn:.6f}")

    if do_sim and mismatches:
        print(f"\n  {mismatches} analytical/simulated mismatch(es).")
        print(f"  These are reconvergent fanout paths — simulator is ground truth.")
        print(f"  The analytical method over-approximates in these cases (Asadi & Tahoori §IV).")

    # top 5 highest-risk gates
    gate_epp = {}
    for gate in gates:
        a_map = compute_epp(G, gate, sp)
        gate_epp[gate] = max(a_map.get(o, 0.0) for o in outputs)

    ranked = sorted(gate_epp.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"\n  Top {len(ranked)} highest-EPP gates (hardening candidates):")
    for name, epp in ranked:
        lib = G.nodes[name].get("libcell", "")
        print(f"    {str(name):28s}  EPP={epp:.6f}  ({lib})")



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python circuitops_bridge.py <ir_directory>")
        sys.exit(1)

    ir_dir = sys.argv[1].rstrip("/")

    if not os.path.isdir(ir_dir):
        print(f"ERROR: not a directory: {ir_dir}")
        sys.exit(1)

    G = build_graph(ir_dir)
    run_epp(G, label=os.path.basename(ir_dir))
