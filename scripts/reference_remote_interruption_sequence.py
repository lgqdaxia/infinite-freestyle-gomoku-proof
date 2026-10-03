"""Independent remote-interruption checker: no primary or search imports."""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.reference_infinite_threat_witness import parse, lines, wins, five, verify as local_verify
from scripts.reference_prepared_remote_sequence import (
    normalized, pt, stone_set, rigid_group, record_closure, envelopes, may_equal)

FORMAT = 'freestyle-gomoku-remote-interruption-sequence'


def remote_audit(black, white, budget):
    assert not five(black) and not five(white) and not wins(white, black)
    memo = {}; positions = {(black, white)}; footprint = set(black | white)
    def visit(a, d):
        # A runaway graph is rejection, never a depth-truncated acceptance.
        assert 2*(len(d)-len(white)) < budget
        if (a, d) in memo:
            return memo[a, d]
        assert len(memo) <= 200000
        if five(a):
            memo[a, d] = 0
            return 0
        options = set()
        for segment in lines(d, 3):
            if not segment & a:
                options.update(segment - a - d)
        maximum = 0
        for p in sorted(options):
            nd = d | {p}; targets = wins(nd, a)
            if not targets:
                continue
            assert not five(nd) and len(targets) == 1
            nb = a | targets
            footprint.update(nb | nd)
            positions.update(((a, nd), (nb, nd)))
            maximum = max(maximum, 1 + visit(nb, nd))
            assert 2*maximum < budget
        memo[a, d] = maximum
        return maximum
    bound = visit(black, white)
    return bound, footprint, positions


def verify(data):
    if not __debug__:
        raise RuntimeError('Refusing verification with assertions disabled')
    assert data['format'] == FORMAT and data['version'] == 1
    assert data['rules'] == {'target':5, 'overline_wins':True, 'forbidden_moves':False}
    b, w = stone_set(data['black']), stone_set(data['white'])
    assert b and not b & w and len(b) == len(w) and not five(b) and not five(w)
    assert normalized(b, w) == (b, w) and data['to_move'] == 'black'
    assert type(data['max_total_plies']) is int
    budget = data['max_total_plies'] - len(b) - len(w)
    assert budget >= 1
    anchor = pt(data['anchor']); core = rigid_group(b, w, anchor)
    cb, cw = b & core, w & core
    rb, rw = b - core, w - core
    outside = rb | rw
    assert outside and rw
    # Separate fixed frames; do NOT pretend their relative positions are exact.
    unused = set(outside); regions = []
    while unused:
        group = {min(unused)}
        while True:
            expanded = group | {q for q in unused if any(
                abs(p[0]-q[0]) < 5 and abs(p[1]-q[1]) < 5 for p in group)}
            if expanded == group:
                break
            group = expanded
        unused.difference_update(group)
        count, points, positions = remote_audit(b & group, w & group, budget)
        regions.append((frozenset(group), count, points, positions))
    interruptions = sum(row[1] for row in regions)
    local_budget = budget - 2*interruptions
    bound = local_verify(cb, cw, data['sequence'], local_budget)
    local_points, local_positions = record_closure(cb, cw, parse(data['sequence']), local_budget)
    def in_frame(reference, region):
        remote_base = min(region[0]); envelope = envelopes(b, w, reference, {remote_base})[0]
        def possible(p, q):
            # Transport the queried point to the OLD remote reference, without
            # importing the primary translated-box implementation.
            at_base = q[0]-p[0]+remote_base[0], q[1]-p[1]+remote_base[1]
            return may_equal(envelope, at_base)
        return possible
    def separated(reference, points, positions, others):
        maps = [(region, in_frame(reference, region)) for region in others]
        assert not any(possible(p, q) for region, possible in maps for p in region[2] for q in points)
        for a, d in positions:
            for segment in lines(d, 1):
                if segment & a:
                    continue
                extras = []
                for region, possible in maps:
                    counts = [len({p for p in outsiders if any(possible(p, q) for q in segment-d)})
                              for _, outsiders in region[3]]
                    extras.append(max(counts))
                assert not sum(extras) or len(segment & d) + sum(extras) < 3
    separated(core, local_points, local_positions, regions)
    for i, region in enumerate(regions):
        separated(region[0], region[2], region[3], [other for j, other in enumerate(regions) if j != i])
    total = bound + 2*interruptions
    assert total <= budget
    return dict(status='VERIFIED_REMOTE_INTERRUPTION_STATE',root_black=data['black'],root_white=data['white'],
                remaining_plies=total,local_bound=bound,remote_interruptions=interruptions,
                latest_win_ply=len(b)+len(w)+total,max_total_plies=data['max_total_plies'],
                local_positions=len(local_positions),remote_positions=sum(len(row[3]) for row in regions),
                remote_components=len(regions), remote_position_counts=[len(row[3]) for row in regions],
                footprint_size=len(local_points),remote_activity_size=sum(len(row[2]) for row in regions),
                scope='all integer preimages of this normalized root; all future legal White moves')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('certificate', type=Path); ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    result = verify(json.loads(args.certificate.read_bytes()))
    result['certificate_sha256'] = hashlib.sha256(args.certificate.read_bytes()).hexdigest()
    result['checker_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text+'\n', encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
