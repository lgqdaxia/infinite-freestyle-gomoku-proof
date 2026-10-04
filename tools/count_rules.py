"""Read-only reachable-node census; this is not a mathematical verifier.

Use only after binding the bytes to the final successful reference receipts.
Counts match the reference kernel's per-file root reachability convention:
a DAG node is counted once within a file, however many paths reach it.
Cross-root and cross-file occurrence multiplicities belong to the caller.
"""
from collections import Counter

ORDINARY_FORMAT = "freestyle-gomoku-infinite-dynamic-gap"
RULE_KINDS = frozenset({
    "terminal", "black", "white", "double_immediate_win", "double_open_four",
    "next_turn_finish", "white_critical", "white_open_four_critical",
    "white_forced_block_symbolic", "white_fork_symbolic",
    "white_open_four_symbolic", "white_open_four_symbolic_shared",
    "white_open_four_symbolic_component", "white_open_four_symbolic_far",
    "infinite_threat_sequence", "prepared_remote_threat_sequence",
    "remote_interruption_threat_sequence",
})


def reachable_kind_counts(data):
    """Return {kinds, reachable_nodes, stored_nodes, unreachable_nodes}.

    Duplicate IDs, dangling child edges and unknown reachable kinds reject
    the census rather than silently affecting the reported usage counts.
    This follows saved edges only; it does not recompute board geometry,
    omitted White responses, macro soundness, or actual move budgets.
    """
    if data.get("format") != ORDINARY_FORMAT:
        raise ValueError("ordinary dynamic-gap proof required")
    rows = data["nodes"]
    nodes = {}
    for row in rows:
        key = row["id"]
        if not isinstance(key, str) or key in nodes:
            raise ValueError("duplicate or invalid node ID")
        nodes[key] = row
    root = data["root"]
    if root not in nodes:
        raise ValueError("missing root")
    pending, seen, kinds = [root], set(), Counter()
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        if key not in nodes:
            raise ValueError("dangling child edge")
        row = nodes[key]
        kind = row["kind"]
        if kind not in RULE_KINDS:
            raise ValueError("unknown reachable node kind: " + repr(kind))
        seen.add(key)
        kinds[kind] += 1
        for edge in row.get("edges") or ():
            pending.append(edge["child"])
    return {"kinds": dict(kinds), "reachable_nodes": len(seen),
            "stored_nodes": len(nodes), "unreachable_nodes": len(nodes) - len(seen)}


def self_test():
    # Shared descendants are not duplicated; unreachable stored nodes do not
    # enter the final strategy census; each malformed case must reject.
    base = {"format": ORDINARY_FORMAT, "root": "a", "nodes": [
        {"id": "a", "kind": "white", "edges": [{"child": "b"}, {"child": "c"}]},
        {"id": "b", "kind": "black", "edges": [{"child": "d"}]},
        {"id": "c", "kind": "black", "edges": [{"child": "d"}]},
        {"id": "d", "kind": "terminal"},
        {"id": "unused", "kind": "prepared_remote_threat_sequence"},
    ]}
    assert reachable_kind_counts(base) == {
        "kinds": {"white": 1, "black": 2, "terminal": 1},
        "reachable_nodes": 4, "stored_nodes": 5, "unreachable_nodes": 1}
    for bad in (
        dict(base, root="missing"),
        dict(base, nodes=base["nodes"] + [base["nodes"][0]]),
        dict(base, nodes=[{"id": "a", "kind": "black", "edges": [{"child": "missing"}]}]),
        dict(base, nodes=[{"id": "a", "kind": "unknown"}]),
    ):
        try:
            reachable_kind_counts(bad)
        except (ValueError, KeyError):
            continue
        raise AssertionError("malformed census unexpectedly accepted")
    return "PASSED: shared DAG, unreachable nodes, missing root, duplicate ID, dangling edge, unknown kind"


if __name__ == "__main__":
    print(self_test())
