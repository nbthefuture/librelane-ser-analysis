"""
epp_algorithm.py

Analytical Soft Error Rate (SER) estimation via Error Propagation
Probability (EPP), based on:

    Asadi & Tahoori — "An Analytical Approach for Soft Error Rate
    Estimation in Digital Circuits"

This file is a pure library. It accepts any nx.DiGraph whose nodes
carry a 'gate' attribute and computes:

    1. signal_probability(G)  — P(node=1) for every node
    2. compute_epp(G, n, sp)  — analytical EPP from node n to all outputs
    3. fault_injection_epp(G, n) — brute-force ground truth (small circuits)

Gate vocabulary covers everything sky130 + Yosys produces:
    PI, BUF, INV
    AND, NAND, OR, NOR, XOR, XNOR
    AND3, NAND3, OR3, NOR3, AND4, NAND4, OR4, NOR4
    AOI21, OAI21, AOI22, OAI22, MUX

Raw sky130 cell names (sky130_fd_sc_hd__and2_1 etc.) are normalised
automatically by normalise_gate() before any computation.
"""

import itertools
import networkx as nx


# Sky130 cell name mapped to canonical gate type
SKY130_MAP = {
    "and2":    "AND",   "and3":   "AND3",   "and4":   "AND4",
    "or2":     "OR",    "or3":    "OR3",    "or4":    "OR4",
    "nand2":   "NAND",  "nand3":  "NAND3",  "nand4":  "NAND4",
    "nor2":    "NOR",   "nor3":   "NOR3",   "nor4":   "NOR4",
    "inv":     "INV",
    "buf":     "BUF",   "clkbuf": "BUF",    "dlygate":"BUF",
    "xor2":    "XOR",   "xnor2":  "XNOR",
    "a21o":    "AOI21", "a21oi":  "AOI21",  "a211o":  "AOI21", "a211oi": "AOI21",
    "a22o":    "AOI22", "a22oi":  "AOI22",  "a2bb2o": "AOI22", "a2bb2oi":"AOI22",
    "o21a":    "OAI21", "o21ai":  "OAI21",  "o211a":  "OAI21", "o211ai": "OAI21",
    "o22a":    "OAI22", "o22ai":  "OAI22",  "o2bb2a": "OAI22", "o2bb2ai":"OAI22",
    "mux2":    "MUX",
}

CANONICAL = frozenset(SKY130_MAP.values()) | {"PI", "BUF", "INV"}

SKY130_PREFIXES = (
    "sky130_fd_sc_hd__", "sky130_fd_sc_hdll__",
    "sky130_fd_sc_hs__",  "sky130_fd_sc_ms__",
    "sky130_fd_sc_ls__",
)


def normalise_gate(raw: str) -> str:
    """
    Map any gate label to a canonical type.
    Already-canonical labels pass through unchanged.
    Returns "UNKNOWN" if unrecognised.
    """
    if raw in CANONICAL:
        return raw
    name = raw.lower()
    for pfx in SKY130_PREFIXES:
        if name.startswith(pfx):
            name = name[len(pfx):]
            break
    if "_" in name:
        name = name.rsplit("_", 1)[0]   # strip drive strength
    return SKY130_MAP.get(name, "UNKNOWN")


# Truth-table evaluation (used by brute-force simulator)
def gate_output(gate: str, inputs: list) -> int:
    a = inputs[0] if len(inputs) > 0 else 0
    b = inputs[1] if len(inputs) > 1 else 0
    c = inputs[2] if len(inputs) > 2 else 0
    d = inputs[3] if len(inputs) > 3 else 0
    if gate in ("PI", "BUF"): return a
    if gate == "INV":   return 1 - a
    if gate == "AND":   return a & b
    if gate == "NAND":  return 1 - (a & b)
    if gate == "OR":    return a | b
    if gate == "NOR":   return 1 - (a | b)
    if gate == "XOR":   return a ^ b
    if gate == "XNOR":  return 1 - (a ^ b)
    if gate == "AND3":  return a & b & c
    if gate == "NAND3": return 1 - (a & b & c)
    if gate == "OR3":   return a | b | c
    if gate == "NOR3":  return 1 - (a | b | c)
    if gate == "AND4":  return a & b & c & d
    if gate == "NAND4": return 1 - (a & b & c & d)
    if gate == "OR4":   return a | b | c | d
    if gate == "NOR4":  return 1 - (a | b | c | d)
    if gate == "AOI21": return 1 - ((a & b) | c)
    if gate == "OAI21": return 1 - ((a | b) & c)
    if gate == "AOI22": return 1 - ((a & b) | (c & d))
    if gate == "OAI22": return 1 - ((a | b) & (c | d))
    if gate == "MUX":   return b if c else a
    return 0


#  Signal probability 
def signal_probability(G: nx.DiGraph) -> dict:
    """
    Compute P(node = 1) for every node, bottom-up in topological order.
    Primary inputs are assumed: P = 0.5 (50% chance of being 1 or 0).
    """
    sp = {}
    for node in nx.topological_sort(G):
        gate  = G.nodes[node].get("gate", "BUF")
        preds = list(G.predecessors(node))
        p = lambda i: sp[preds[i]] if i < len(preds) else 0.5  # noqa: E731

        if gate == "PI" or not preds:
            sp[node] = 0.5
        elif gate == "BUF":   sp[node] = p(0)
        elif gate == "INV":   sp[node] = 1 - p(0)
        elif gate == "AND":   sp[node] = p(0) * p(1)
        elif gate == "NAND":  sp[node] = 1 - p(0) * p(1)
        elif gate == "OR":    sp[node] = p(0) + p(1) - p(0)*p(1)
        elif gate == "NOR":   sp[node] = 1 - (p(0) + p(1) - p(0)*p(1))
        elif gate == "XOR":   sp[node] = p(0)*(1-p(1)) + (1-p(0))*p(1)
        elif gate == "XNOR":  sp[node] = 1 - (p(0)*(1-p(1)) + (1-p(0))*p(1))
        elif gate == "AND3":  sp[node] = p(0)*p(1)*p(2)
        elif gate == "NAND3": sp[node] = 1 - p(0)*p(1)*p(2)
        elif gate == "OR3":   sp[node] = 1 - (1-p(0))*(1-p(1))*(1-p(2))
        elif gate == "NOR3":  sp[node] = (1-p(0))*(1-p(1))*(1-p(2))
        elif gate == "AND4":  sp[node] = p(0)*p(1)*p(2)*p(3)
        elif gate == "NAND4": sp[node] = 1 - p(0)*p(1)*p(2)*p(3)
        elif gate == "OR4":   sp[node] = 1 - (1-p(0))*(1-p(1))*(1-p(2))*(1-p(3))
        elif gate == "NOR4":  sp[node] = (1-p(0))*(1-p(1))*(1-p(2))*(1-p(3))
        elif gate == "AOI21":
            ab = p(0)*p(1); sp[node] = 1 - (ab + p(2) - ab*p(2))
        elif gate == "OAI21":
            ab = p(0)+p(1)-p(0)*p(1); sp[node] = 1 - ab*p(2)
        elif gate == "AOI22":
            ab = p(0)*p(1); cd = p(2)*p(3)
            sp[node] = 1 - (ab + cd - ab*cd)
        elif gate == "OAI22":
            ab = p(0)+p(1)-p(0)*p(1); cd = p(2)+p(3)-p(2)*p(3)
            sp[node] = 1 - ab*cd
        elif gate == "MUX":
            sp[node] = (1-p(2))*p(0) + p(2)*p(1)
        else:
            sp[node] = 0.5  # fallback for UNKNOWN
    return sp


# 4-vector primitives (Asadi & Tahoori implementation)
#
# Each node carries a 4-tuple describing fault behaviour:
#   p0  = P(correct output = 0, no fault)
#   p1  = P(correct output = 1, no fault)
#   pa  = P(output flips 0 → 1 due to fault)
#   pan = P(output flips 1 → 0 due to fault)

def _vec(p0, p1, pa, pan):
    return (p0, p1, pa, pan)

def _off(sp):
    """Node not on the fault path — fault probability is zero."""
    return _vec(1-sp, sp, 0.0, 0.0)

def _src():
    """Fault injection point — output is always flipped."""
    return _vec(0.0, 0.0, 1.0, 0.0)

def _and(a, b):
    p1  = a[1]*b[1]
    pa  = (a[1]+a[2])*(b[1]+b[2]) - p1
    pan = (a[1]+a[3])*(b[1]+b[3]) - p1
    return _vec(1-p1-pa-pan, p1, pa, pan)

def _or(a, b):
    p0  = a[0]*b[0]
    pa  = (a[0]+a[2])*(b[0]+b[2]) - p0
    pan = (a[0]+a[3])*(b[0]+b[3]) - p0
    return _vec(p0, 1-p0-pa-pan, pa, pan)

def _inv(a):
    return _vec(a[1], a[0], a[3], a[2])


def _propagate(gate: str, vecs: list) -> tuple:
    """
    Compute output 4-vector for gate given input 4-vectors.
    Every gate decomposes into _and / _or / _inv — no new math.
    """
    def v(i):
        return vecs[i] if i < len(vecs) else _off(0.5)

    if gate in ("PI", "BUF"):  return v(0)
    if gate == "INV":          return _inv(v(0))
    if gate == "AND":          return _and(v(0), v(1))
    if gate == "NAND":         return _inv(_and(v(0), v(1)))
    if gate == "OR":           return _or(v(0), v(1))
    if gate == "NOR":          return _inv(_or(v(0), v(1)))
    if gate == "XOR":
        return _or(_and(v(0), _inv(v(1))), _and(_inv(v(0)), v(1)))
    if gate == "XNOR":
        return _inv(_or(_and(v(0), _inv(v(1))), _and(_inv(v(0)), v(1))))
    if gate == "AND3":         return _and(_and(v(0), v(1)), v(2))
    if gate == "NAND3":        return _inv(_and(_and(v(0), v(1)), v(2)))
    if gate == "OR3":          return _or(_or(v(0), v(1)), v(2))
    if gate == "NOR3":         return _inv(_or(_or(v(0), v(1)), v(2)))
    if gate == "AND4":         return _and(_and(_and(v(0), v(1)), v(2)), v(3))
    if gate == "NAND4":        return _inv(_and(_and(_and(v(0), v(1)), v(2)), v(3)))
    if gate == "OR4":          return _or(_or(_or(v(0), v(1)), v(2)), v(3))
    if gate == "NOR4":         return _inv(_or(_or(_or(v(0), v(1)), v(2)), v(3)))
    if gate == "AOI21":        return _inv(_or(_and(v(0), v(1)), v(2)))
    if gate == "OAI21":        return _inv(_and(_or(v(0), v(1)), v(2)))
    if gate == "AOI22":        return _inv(_or(_and(v(0), v(1)), _and(v(2), v(3))))
    if gate == "OAI22":        return _inv(_and(_or(v(0), v(1)), _or(v(2), v(3))))
    if gate == "MUX":
        return _or(_and(v(0), _inv(v(2))), _and(v(1), v(2)))
    # UNKNOWN — let fault pass through conservatively
    return _vec(0.0, 0.0, v(0)[2], v(0)[3])


# Analytical EPP
def compute_epp(G: nx.DiGraph, fault_node, sp: dict) -> dict:
    """
    Inject a fault at fault_node and propagate its 4-vector forward.
    Returns {node: EPP} for every node reachable from fault_node.
    EPP = pa + pan = total probability fault changes the node's output.
    """
    if fault_node not in G:
        return {}

    reachable = nx.descendants(G, fault_node) | {fault_node}
    vecs = {fault_node: _src()}

    for node in nx.topological_sort(G):
        if node not in reachable or node == fault_node:
            continue
        gate  = G.nodes[node].get("gate", "BUF")
        preds = list(G.predecessors(node))
        ivecs = [vecs[p] if p in vecs else _off(sp[p]) for p in preds]
        vecs[node] = _propagate(gate, ivecs)

    return {n: v[2] + v[3] for n, v in vecs.items()}


# ── Brute-force simulator (ground truth for small circuits) ───────────────────

def fault_injection_epp(G: nx.DiGraph, fault_node) -> dict:
    """
    Enumerate all PI combinations, inject a fault at fault_node,
    and count how often the output differs. O(2^|PIs|) — only use
    for circuits with ≤ 20 PIs.
    """
    topo    = list(nx.topological_sort(G))
    pis     = [n for n in topo if G.nodes[n].get("gate") == "PI"]
    outputs = [n for n in topo if G.out_degree(n) == 0]

    if not pis or not outputs:
        return {}

    flips  = {o: 0 for o in outputs}
    combos = list(itertools.product([0, 1], repeat=len(pis)))

    for combo in combos:
        pi_vals = dict(zip(pis, combo))

        def evaluate(flip=None):
            vals = dict(pi_vals)
            for node in topo:
                if node in vals:
                    continue
                gate   = G.nodes[node].get("gate", "BUF")
                preds  = list(G.predecessors(node))
                result = gate_output(gate, [vals[p] for p in preds])
                vals[node] = (1 - result) if node == flip else result
            return vals

        normal   = evaluate()
        injected = evaluate(flip=fault_node)
        for o in outputs:
            if normal.get(o) != injected.get(o):
                flips[o] += 1

    total = len(combos)
    return {o: flips[o] / total for o in outputs}
