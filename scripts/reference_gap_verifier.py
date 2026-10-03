"""Second dynamic-gap certificate checker, using only the Python standard library.

No imports from src, search code, Rapfi, persisted success labels, or the first
checker. Axis transitions are obtained by inserting points in concrete gaps
of lengths 5..10, then compressing them. Five-cell witnesses use direct sets.
This checks the same sufficient mathematical rules; it is not a proof assistant.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import time

D = ((1, 0), (0, 1), (1, 1), (1, -1))
RULES = {"target": 5, "overline_wins": True, "forbidden_moves": False}


def compress(values):
    values = sorted(set(values) | {0})
    prefix = [0]
    for a, b in zip(values, values[1:]):
        prefix.append(prefix[-1] + min(b - a, 5))
    origin = prefix[values.index(0)]
    return dict(zip(values, (p - origin for p in prefix)))


def normalize(state):
    occupied = state[0] | state[1]
    xm = compress(p[0] for p in occupied)
    ym = compress(p[1] for p in occupied)
    return tuple(frozenset((xm[x], ym[y]) for x, y in s) for s in state)


@lru_cache(maxsize=2048)
def axis_insertions(values):
    """All insertion types, by finite concrete representatives, not split pairs.

Only the split gap can change old normalized distances. If its real length
is >=10, all its truncated insertion outcomes already occur at lengths <=10.
Other unsplit saturated gaps may be set to 5. Outside distances >=5 collapse.
The mathematical completeness argument is in the audit document.
"""
    out = set()

    def insert(concrete, q):
        compressed = compress((*concrete, q))
        out.add((tuple(compressed[p] for p in concrete), compressed[q]))

    for q in (*values, *(values[0] - i for i in range(1, 6)),
              *(values[-1] + i for i in range(1, 6))):
        insert(values, q)
    for index, (a, b) in enumerate(zip(values, values[1:])):
        assert 1 <= b - a <= 5
        lengths = range(5, 11) if b - a == 5 else (b - a,)
        for length in lengths:
            concrete = [v if i <= index else v + length - (b - a)
                        for i, v in enumerate(values)]
            zero = concrete[values.index(0)]
            concrete = [v - zero for v in concrete]
            for q in range(concrete[index] + 1, concrete[index + 1]):
                insert(concrete, q)
    return tuple(sorted(out))


def successors(state, color, action=None):
    occupied = state[0] | state[1]
    if action is not None:
        r, delta = action
        assert r in occupied and max(map(abs, delta)) <= 4
        assert (r[0] + delta[0], r[1] + delta[1]) not in occupied
    axes = []
    for axis in (0, 1):
        values = tuple(sorted({0} | {p[axis] for p in occupied}))
        rows = []
        for mapped, q in axis_insertions(values):
            mapping = dict(zip(values, mapped))
            if action is None or q - mapping[action[0][axis]] == action[1][axis]:
                rows.append((mapping, q))
        axes.append(rows)
    result = set()
    for xm, x in axes[0]:
        for ym, y in axes[1]:
            child = [frozenset((xm[a], ym[b]) for a, b in s) for s in state]
            if (x, y) not in child[0] | child[1]:
                child[color] |= {(x, y)}
                result.add(tuple(child))
    return frozenset(result)


@lru_cache(maxsize=4096)
def windows(stones, width, minimum):
    # Form each segment as a set, count its actual intersection with stones.
    # Points on different parallel lines cannot jointly meet the minimum.
    # Grouping by line first avoids constructing thousands of empty segments.
    if len(stones)<minimum:return ()
    seen = set()
    out = []
    for dx, dy in D:
        groups={}
        for x,y in stones:groups.setdefault(dx*y-dy*x,[]).append((x,y))
        points=(p for group in groups.values() if len(group)>=minimum for p in group)
        for x,y in points:
            for k in range(width):
                start = x - k * dx, y - k * dy
                key = start, dx, dy
                if key in seen:
                    continue
                seen.add(key)
                line = frozenset((start[0] + i * dx, start[1] + i * dy)
                                 for i in range(width))
                support = line & stones
                if len(support) >= minimum:
                    out.append((start, (dx, dy), line, support))
    return tuple(out)


def five(stones):
    return _five(frozenset(stones))


@lru_cache(maxsize=8192)
def _five(stones):
    if len(stones) < 5:
        return False
    return any(all((x + i * dx, y + i * dy) in stones for i in range(1, 5))
               for x, y in stones for dx, dy in D)


def wins(own, enemy):
    if len(own)<4:return frozenset()
    return frozenset(q for _, _, line, support in windows(own, 5, 4)
                     if len(support) == 4 and not line & enemy for q in line - own)


def templates(state):
    b, w = state
    result = []
    for (x, y), (dx, dy), line, support in windows(b, 4, 3):
        if len(support) != 3 or line & w:
            continue
        p = next(iter(line - b))
        left, right = (x - dx, y - dy), (x + 4 * dx, y + 4 * dy)
        if left not in b | w and right not in b | w:
            result.append(((p, left, right), support))
    return sorted(result, key=lambda t: t[0])


def threat_actions(state):
    b, w = state
    result = set()
    for _, _, line, support in windows(w, 5, 3):
        if line & b:
            continue
        assert len(support) == 3, 'White can win immediately'
        r = min(support)
        for x, y in line - w:
            result.add((r, (x - r[0], y - r[1])))
    return result


def critical_actions(state, kind):
    """Reconstruct geometrically justified witnesses; never trust their labels."""
    b, w = state
    if kind == 'white_forced_block_symbolic':
        assert not wins(w, b)
        q = min(wins(b, w))
        r = min(r for r in b if max(abs(q[0] - r[0]), abs(q[1] - r[1])) <= 1)
        return {(r, (q[0] - r[0], q[1] - r[1]))}
    actions = threat_actions(state)
    if kind == 'white_fork_symbolic':
        # A line with exactly three old Black stones has two vacant points.
        # Either can be the setup, leaving the other as the resulting win.
        forks = {}
        for _, _, line, support in windows(b, 5, 3):
            if len(support) != 3 or line & w:
                continue
            p, q = sorted(line - b)
            for setup, target in ((p, q), (q, p)):
                forks.setdefault(setup, {}).setdefault(target, set()).update(support)
        choices = []
        for p, targets in forks.items():
            if len(targets) >= 2:
                blockers = (p,) if len(targets) >= 3 else tuple(sorted({p} | targets.keys()))
                choices.append((len(blockers), p, blockers))
        _, p, blockers = min(choices)
        supporters = forks[p]
        for q in blockers:
            anchors = set().union(*supporters.values()) if q == p else supporters[q]
            r = min(anchors)
            actions.add((r, (q[0] - r[0], q[1] - r[1])))
        return actions
    ts = templates(state)
    assert ts
    if kind == 'white_open_four_symbolic_far':
        assert len(b) >= 6
        assert any(max(abs(r[0] - s[0]), abs(r[1] - s[1])) > 8
                   for i, (_, first) in enumerate(ts) for _, second in ts[i + 1:]
                   for r in first for s in second)
        return actions
    if kind == 'white_open_four_symbolic_shared':
        assert len(b) >= 5
        families = []
        for r in sorted(b):
            family = [t for t, support in ts if r in support]
            if family:
                common = set.intersection(*(set(t) for t in family))
                families.append((len(common), r, family))
        _, r, selected = min(families)
    elif kind == 'white_open_four_symbolic_component':
        assert len(b) >= 5
        # Union-find gives each exact local frame. Include White connector stones.
        occupied = sorted(b | w)
        groups = {p: p for p in occupied}

        def root(p):
            while groups[p] != p:
                p = groups[p]
            return p

        for i, p in enumerate(occupied):
            for q in occupied[i + 1:]:
                if max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= 4:
                    groups[root(q)] = root(p)
        families = {}
        for t, support in ts:
            label = root(min(support))
            assert all(root(p) == label for p in support)
            families.setdefault(label, []).append(t)
        selected = min(families.values(), key=lambda f: (len(set.intersection(*(set(t) for t in f))), f))
        r = min(dict(ts)[selected[0]])
    else:
        assert kind == 'white_open_four_symbolic'
        selected = [t for t, _ in (ts if len(b) <= 4 else ts[:1])]
        r = min(ts[0][1])
    common = set.intersection(*(set(t) for t in selected))
    for x, y in common:
        assert max(abs(x - r[0]), abs(y - r[1])) <= 4
        actions.add((r, (x - r[0], y - r[1])))
    return actions


def parse_point(raw):
    assert isinstance(raw, list) and len(raw) == 2 and all(type(v) is int for v in raw)
    return tuple(raw)


def frame_state(state, raw, inverse=False):
    assert isinstance(raw, list) and len(raw) == 4 and all(type(v) is int for v in raw)
    # Independent recognition by explicit enumeration of the eight matrices.
    signed = {(a, 0, 0, b) for a in (-1, 1) for b in (-1, 1)}
    signed |= {(0, a, b, 0) for a in (-1, 1) for b in (-1, 1)}
    assert tuple(raw) in signed
    a, b, c, d = raw
    if inverse:
        b, c = c, b
    return tuple(frozenset((a*x + b*y, c*x + d*y) for x, y in color) for color in state)


def verify(data, require_empty=False):
    """Return checked reachable-node statistics, or raise on any rejected proof."""
    if not __debug__:
        raise RuntimeError('Refusing to verify: Python assertions are disabled')
    assert data['format'] == 'freestyle-gomoku-infinite-dynamic-gap'
    assert type(data['version']) is int and data['version'] == 1 and data['rules'] == RULES
    bound = data['max_total_plies']
    assert type(bound) is int and bound >= 1
    assert isinstance(data['nodes'], list)
    nodes, states = {}, {}
    for row in data['nodes']:
        key = row['id']
        assert isinstance(key, str) and key not in nodes
        pos = row['position']
        assert isinstance(pos['black'], list) and isinstance(pos['white'], list)
        state = tuple(frozenset(parse_point(p) for p in pos[c]) for c in ('black', 'white'))
        b, w = state
        assert len(b) == len(pos['black']) and len(w) == len(pos['white'])
        assert not b & w and len(b) - len(w) in (0, 1) and normalize(state) == state
        assert pos['to_move'] == ('black' if len(b) == len(w) else 'white')
        nodes[key], states[key] = row, state
    root_key = data['root']
    assert root_key in nodes
    if require_empty:
        assert states[root_key] == (frozenset(), frozenset())
    pending, done, counts = [root_key], set(), Counter()
    while pending:
        key = pending.pop()
        if key in done:
            continue
        row, state = nodes[key], states[key]
        b, w = state
        ply, kind = len(b) + len(w), row['kind']
        frame = row.get('rule_frame')
        if 'rule_frame' in row:
            assert kind in {'white_forced_block_symbolic', 'white_fork_symbolic',
                            'white_open_four_symbolic', 'white_open_four_symbolic_shared',
                            'white_open_four_symbolic_component', 'white_open_four_symbolic_far'}
            frame_state(state, frame)  # Validate even if no edges/actions result.
        assert ply <= bound and not five(w), (key, 'White terminal or budget')
        done.add(key)
        counts[kind] += 1
        if kind == 'terminal':
            assert len(b) == len(w) + 1 and five(b) and any(not five(b - {p}) for p in b)
            assert row.get('edges') is None
            continue
        assert not five(b) and ply < bound
        if kind=='infinite_threat_sequence':
            from scripts.reference_infinite_threat_witness import verify as verify_sequence
            assert len(b)==len(w) and row.get('edges') is None
            verify_sequence(b,w,row['sequence'],bound-ply)
            continue
        if kind=='prepared_remote_threat_sequence':
            from scripts.reference_prepared_remote_sequence import verify as verify_prepared, FORMAT as PREPARED_FORMAT
            assert len(b)==len(w) and row.get('edges') is None
            verify_prepared(dict(format=PREPARED_FORMAT,version=1,rules=data['rules'],
                black=row['position']['black'],white=row['position']['white'],
                to_move='black',anchor=row['anchor'],sequence=row['sequence'],max_total_plies=bound))
            continue
        if kind=='remote_interruption_threat_sequence':
            from scripts.reference_remote_interruption_sequence import verify as verify_interrupted, FORMAT as INTERRUPTED_FORMAT
            assert len(b)==len(w) and row.get('edges') is None
            verify_interrupted(dict(format=INTERRUPTED_FORMAT,version=1,rules=data['rules'],
                black=row['position']['black'],white=row['position']['white'],
                to_move='black',anchor=row['anchor'],sequence=row['sequence'],max_total_plies=bound))
            continue
        if kind == 'black':
            assert len(b) == len(w)
            a = row['action']
            if a.get('origin') is True and not b | w:
                expected = {(frozenset({(0, 0)}), frozenset())}
            else:
                expected = successors(state, 0, (parse_point(a['reference']), parse_point(a['offset'])))
            assert expected
        else:
            assert len(b) == len(w) + 1
            if kind in ('double_immediate_win', 'double_open_four'):
                assert ply + 2 <= bound and not wins(w, b) and len(wins(b, w)) >= 2
                assert row.get('edges') is None
                continue
            if kind == 'next_turn_finish':
                assert ply + 2 <= bound and row.get('edges') is None
                assert all(not five(c[1]) and wins(c[0], c[1]) for c in successors(state, 1))
                continue
            if kind == 'white':
                expected = successors(state, 1)
            elif kind in ('white_critical', 'white_open_four_critical'):
                expected = set()
                assert ply + (2 if kind == 'white_critical' else 4) <= bound
                if kind == 'white_open_four_critical':
                    assert (len(b), len(w)) == (3, 2)
                for child in successors(state, 1):
                    assert not five(child[1])
                    easy = wins(*child) if kind == 'white_critical' else templates(child)
                    if not easy:
                        expected.add(child)
            else:
                assert ply + (2 if kind == 'white_forced_block_symbolic' else 4) <= bound
                rule_state = state if frame is None else frame_state(state, frame)
                actions = critical_actions(rule_state, kind)
                expected = set()
                for action in actions:
                    outcomes = successors(rule_state, 1, action)
                    assert outcomes
                    expected.update(outcomes)
                if frame is not None:
                    expected = {frame_state(s, frame, inverse=True) for s in expected}
        edges = row['edges']
        assert isinstance(edges, list)
        actual = set()
        for edge in edges:
            child = edge['child']
            assert child in nodes
            child_state = states[child]
            assert sum(map(len, child_state)) == ply + 1, (key, 'non-increasing rank')
            assert child_state not in actual
            actual.add(child_state)
            pending.append(child)
        assert actual == expected, (key, kind, 'coverage', len(expected - actual), len(actual - expected))
    return {'reachable_nodes': len(done), 'stored_nodes': len(nodes), 'kinds': dict(counts),
            'root_position': nodes[root_key]['position'], 'max_total_plies': bound}


def check_file(path):
    start = time.monotonic()
    raw = Path(path).read_bytes()
    result = {'proof': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
    try:
        result.update(verify(json.loads(raw)))
        result['status'] = 'VERIFIED_REFERENCE'
    except Exception as exc:
        result.update(status='REJECTED_REFERENCE', error=repr(exc))
    result['seconds'] = time.monotonic() - start
    return result


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def main():
    # Assertions ARE the checks. Never run this kernel with -O or -OO.
    if not __debug__:
        raise SystemExit('Refusing to run: Python assertions are disabled')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('certificate', nargs='?', type=Path)
    ap.add_argument('--inventory', type=Path)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--from-empty', action='store_true')
    args = ap.parse_args()
    if args.certificate:
        result = check_file(args.certificate)
        if args.from_empty and result['status'] == 'VERIFIED_REFERENCE':
            root = result['root_position']
            if root['black'] or root['white']:
                result.update(status='REJECTED_REFERENCE', error='root is not empty')
        if args.output:
            write(args.output, result)
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if result['status'] == 'VERIFIED_REFERENCE' else 1)
    assert args.inventory and args.output and not args.from_empty
    inventory = json.loads(args.inventory.read_text(encoding='utf-8'))
    rows, start = [], time.monotonic()
    expected = {row['proof']: row['sha256'] for row in inventory['rows']}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(check_file, path): path for path in expected}
        for future in as_completed(pending):
            row = future.result()
            if row['sha256'] != expected[row['proof']]:
                row.update(status='REJECTED_REFERENCE', error='inventory SHA mismatch')
            rows.append(row)
            write(args.output.with_name('reference-progress.json'), {
                'checked': len(rows), 'total': len(expected),
                'accepted': sum(r['status'] == 'VERIFIED_REFERENCE' for r in rows),
                'seconds': time.monotonic() - start})
            if row['status'] != 'VERIFIED_REFERENCE':
                print(json.dumps(row, ensure_ascii=False), flush=True)
    result = {'files': len(rows), 'accepted': sum(r['status'] == 'VERIFIED_REFERENCE' for r in rows),
              'seconds': time.monotonic() - start,
              'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'inventory_sha256': hashlib.sha256(args.inventory.read_bytes()).hexdigest(),
              'rows': sorted(rows, key=lambda r: r['proof'])}
    write(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))
    raise SystemExit(0 if result['files'] == result['accepted'] else 1)


if __name__ == '__main__':
    main()
