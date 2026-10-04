"""Small rejection regressions against the frozen independent kernels only.

No src/search imports, engine calls, or historical success-receipt premises.
These fixtures exercise acceptance boundaries; they do not replay the full cover.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from scripts import reference_gap_verifier as gap
from scripts import reference_infinite_threat_witness as local
from scripts import reference_prepared_remote_sequence as prepared
from scripts import reference_remote_interruption_sequence as remote
from scripts.reference_gap_opening_cover import validate_header

HERE = Path(__file__).resolve().parent
FIXTURES = HERE/'audit/fixtures'
CORE = frozenset({(0,0),(1,-1),(1,0)})


def load(name):
    return json.loads((FIXTURES/name).read_bytes())


def normalize(b,w):
    return gap.normalize((frozenset(b),frozenset(w)))


def positional(data,state):
    result = copy.deepcopy(data)
    for color,stones in zip(('black','white'),state):
        result[color] = [list(p) for p in sorted(stones)]
    return result


class CertificateRejectionTests(unittest.TestCase):
    def test_frozen_kernel_identities(self):
        freeze = json.loads((HERE/'CHECKER-FREEZE.json').read_bytes())
        for name,sha in freeze['mathematical_kernels'].items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((HERE/name).read_bytes()).hexdigest(),sha)

    def test_fixture_controls_are_accepted(self):
        for name in ('gap-explicit.json','gap-fork.json'):
            with self.subTest(fixture=name):
                self.assertGreater(gap.verify(load(name))['reachable_nodes'],0)
        self.assertEqual(remote.verify(load('remote-interruption.json'))['latest_win_ply'],21)
        self.assertEqual(len(validate_header(load('empty-cover-header.json'))[0]),20)

    def test_missing_black_outcome_is_rejected(self):
        data = load('gap-explicit.json')
        next(row for row in data['nodes'] if row['kind']=='black')['edges'].pop()
        with self.assertRaises(AssertionError): gap.verify(data)

    def test_occupied_black_move_is_rejected(self):
        data = load('gap-explicit.json')
        next(row for row in data['nodes'] if row['kind']=='black')['action']['offset'] = [0,0]
        with self.assertRaises(AssertionError): gap.verify(data)

    def test_missing_retained_white_outcome_is_rejected(self):
        data = load('gap-fork.json')
        next(row for row in data['nodes'] if row['kind']=='white_fork_symbolic')['edges'].pop()
        with self.assertRaises(AssertionError): gap.verify(data)

    def test_terminal_is_subject_to_total_budget(self):
        b,w = normalize({(x,0) for x in range(5)}, {(0,3),(2,5),(4,7),(6,9)})
        data = dict(format='freestyle-gomoku-infinite-dynamic-gap',version=1,rules=gap.RULES,
                    max_total_plies=9,root='t',nodes=[dict(id='t',kind='terminal',
                    position=dict(black=[list(p) for p in b],white=[list(p) for p in w],to_move='white'))])
        self.assertEqual(gap.verify(data)['reachable_nodes'],1)
        data['max_total_plies'] = 8
        with self.assertRaises(AssertionError): gap.verify(data)

    def test_white_five_cannot_hide_behind_black_terminal(self):
        b,w = normalize({(x,0) for x in range(5)}|{(0,10)}, {(x,20) for x in range(5)})
        data = dict(format='freestyle-gomoku-infinite-dynamic-gap',version=1,rules=gap.RULES,
                    max_total_plies=11,root='t',nodes=[dict(id='t',kind='terminal',
                    position=dict(black=[list(p) for p in b],white=[list(p) for p in w],to_move='white'))])
        with self.assertRaises(AssertionError): gap.verify(data)

    def test_white_immediate_win_and_malformed_pattern_reject(self):
        b = frozenset({(0,0),(1,0),(2,0)})
        seq = [dict(gain=[3,0],kind='straight_four',required=[[0,0],[1,0],[2,0]],
                    cost=[[-1,0],[4,0]],empty=[[3,0],[-1,0],[4,0]])]
        quiet = frozenset({(0,2),(1,2),(2,3)})
        self.assertEqual(local.verify(b,quiet,seq,3),3)
        with self.assertRaises(AssertionError):
            local.verify(b,frozenset({(0,2),(1,2),(2,2),(3,2)}),seq,20)
        seq[0]['cost'] = []
        with self.assertRaises(AssertionError): local.verify(b,quiet,seq,20)

    def test_white_double_counterfour_rejects_local_attack(self):
        b = frozenset({(0,0),(1,0),(4,4)})
        w = frozenset({(0,2),(1,2),(2,2)})
        seq = [dict(gain=[2,0],kind='open_three',required=[[0,0],[1,0]],cost=[[-1,0],[3,0]],
                    empty=[[2,0],[-1,0],[3,0],[-2,0],[4,0]])]
        with self.assertRaises(AssertionError): local.verify(b,w,seq,30)

    def prepared_data(self,b=None,w=None):
        state = normalize(CORE|{(-25,1),(-20,-4)},
                          {(-24,0),(-23,-1),(-22,-2),(-21,-3),(0,1)}) if b is None else normalize(b,w)
        return dict(format=prepared.FORMAT,version=1,rules=gap.RULES,
                    black=[list(p) for p in sorted(state[0])],white=[list(p) for p in sorted(state[1])],
                    anchor=[0,0],to_move='black',max_total_plies=23,
                    sequence=load('prepared-recipe.json'))

    def test_prepared_clock_and_missing_remote_blocker(self):
        data = self.prepared_data()
        self.assertEqual(prepared.verify(data)['latest_win_ply'],21)
        too_short = copy.deepcopy(data); too_short['max_total_plies'] = 20
        with self.assertRaises(AssertionError): prepared.verify(too_short)
        b,w = map(lambda points:frozenset(map(tuple,points)),(data['black'],data['white']))
        broken = positional(data,normalize(b-{(-10,1)}|{(-10,2)},w))
        with self.assertRaises(AssertionError): prepared.verify(broken)

    def test_prepared_mixed_remote_local_triple(self):
        data = self.prepared_data(CORE|{(-12,12),(-13,13)},
                                 {(0,1),(-7,2),(-8,2),(-12,16),(-13,17)})
        with self.assertRaises(AssertionError): prepared.verify(data)

    def test_remote_clock_counts_both_actual_moves(self):
        data = load('remote-interruption.json'); data['max_total_plies'] = 21
        receipt = remote.verify(data)
        self.assertEqual((receipt['local_bound'],receipt['remote_interruptions'],receipt['remaining_plies']),(11,1,13))
        data['max_total_plies'] = 20
        with self.assertRaises(AssertionError): remote.verify(data)

    def test_remote_unsealed_three_and_initial_four(self):
        data = load('remote-interruption.json')
        b,w = map(lambda points:frozenset(map(tuple,points)),(data['black'],data['white']))
        for state in (normalize(b-{(-8,1)}|{(-8,2)},w),normalize(b,w-{(1,3)}|{(-4,-3)})):
            with self.subTest(state=state):
                with self.assertRaises(AssertionError): remote.verify(positional(data,state))

    def test_future_remote_block_collides_with_local_suffix(self):
        state = normalize({(0,0),(1,-1),(1,0),(9,-9)}, {(6,-6),(7,-7),(8,-8),(1,3)})
        with self.assertRaises(AssertionError): remote.verify(positional(load('remote-interruption.json'),state))

    def test_two_remote_frames_cannot_hide_mixed_triple(self):
        state = normalize({(0,0),(1,-1),(1,0),(2,1),(-8,12),(3,12)},
                          {(x,12) for x in (-7,-6,-5,0,1,2)})
        with self.assertRaises(AssertionError): remote.verify(positional(load('remote-interruption.json'),state))

    def test_wrong_turn_type_anchor_and_duplicate_stone(self):
        original = load('remote-interruption.json')
        for key,value in (('to_move','white'),('max_total_plies',21.0),('anchor',[False,0]),
                          ('black',original['black']+[[0,0]])):
            with self.subTest(field=key):
                data = copy.deepcopy(original); data[key] = value
                with self.assertRaises(AssertionError): remote.verify(data)

    def test_missing_duplicate_and_wrong_opening_frame(self):
        original = load('empty-cover-header.json')
        bad = copy.deepcopy(original); bad['replies'].pop()
        with self.assertRaises(AssertionError): validate_header(bad)
        bad = copy.deepcopy(original); bad['replies'][1] = copy.deepcopy(bad['replies'][0])
        with self.assertRaises(AssertionError): validate_header(bad)
        bad = copy.deepcopy(original); bad['replies'][0]['matrix'] = [2,0,0,2]
        with self.assertRaises(AssertionError): validate_header(bad)

    def test_relative_black_action_preserves_all_gap_outcomes(self):
        state = (frozenset({(0,0)}),frozenset({(5,0)}))
        outcomes = gap.successors(state,0,((5,0),(-4,0)))
        self.assertIn(normalize({(0,0),(1,0)},{(5,0)}),outcomes)
        self.assertIn(normalize({(0,0),(96,0)},{(100,0)}),outcomes)

    def test_disabled_assertions_are_refused(self):
        result = subprocess.run([sys.executable,'-O','-B','-m','scripts.reference_gap_verifier'],
                                cwd=HERE,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('assertions are disabled',result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
