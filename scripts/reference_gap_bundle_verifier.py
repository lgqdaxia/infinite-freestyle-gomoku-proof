"""Check modular infinite-gap proofs, one complete child file at a time.

Only the standard library and the independent reference kernel are used.
The default entry point ignores all saved receipts. An explicit local ordinary
cache is available for intermediate publication; final roots omit that cache.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from scripts.reference_gap_verifier import RULES,parse_point,normalize,five,successors,verify

FORMAT='freestyle-gomoku-infinite-gap-bundle'


def position(raw):
    assert isinstance(raw,dict)
    assert all(isinstance(raw[c],list) for c in ('black','white'))
    state=tuple(frozenset(parse_point(p) for p in raw[c]) for c in ('black','white'))
    b,w=state
    assert len(b)==len(raw['black']) and len(w)==len(raw['white'])
    assert not b&w and len(b)-len(w) in (0,1) and normalize(state)==state
    assert raw['to_move']==('black' if len(b)==len(w) else 'white')
    return state


def verify_file(path,require_empty=False,*,ordinary_cache=None):
    if not __debug__:raise RuntimeError('Assertions must be enabled')
    active=set();checked={};counts=Counter();bindings=[]
    fresh_files=0;reused_files=0
    def visit(path,expected_hash=None,empty=False):
        nonlocal fresh_files,reused_files
        path=Path(path).resolve()
        assert path not in active,'cyclic file references'
        raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        if expected_hash is not None:assert sha==expected_hash,'child file hash mismatch'
        # Only completed ordinary DAGs are cached. Bundle dependencies are
        # revisited so each declared child file is checked against its hash.
        key=(str(path),sha)
        if key in checked:
            root,bound=checked[key]
            if empty:assert root==(frozenset(),frozenset())
            return root,bound,sha
        # Optional LOCAL memo only. Every file was read and hashed above;
        # a cache entry can originate only from the ordinary reference kernel.
        cached=ordinary_cache.lookup(sha) if ordinary_cache is not None else None
        if cached is not None:
            root=position(cached['root_position']);bound=cached['max_total_plies']
            if empty:assert root==(frozenset(),frozenset())
            counts['ordinary_proof_files']+=1
            counts['ordinary_node_occurrences']+=cached['reachable_nodes']
            checked[key]=(root,bound);reused_files+=1
            bindings.append({'file':str(path),'sha256':sha})
            return root,bound,sha
        data=json.loads(raw);del raw
        active.add(path)
        try:
            if data['format']=='freestyle-gomoku-infinite-dynamic-gap':
                receipt=(verify(data,require_empty=empty) if ordinary_cache is None else
                         ordinary_cache.verify_and_record(data,sha,require_empty=empty))
                fresh_files+=1
                root=position(receipt['root_position']);bound=receipt['max_total_plies']
                counts['ordinary_proof_files']+=1
                counts['ordinary_node_occurrences']+=receipt['reachable_nodes']
                checked[key]=(root,bound)
            else:
                assert data['format']==FORMAT and type(data['version']) is int and data['version']==1
                assert data['rules']==RULES
                root=position(data['position']);b,w=root;ply=len(b)+len(w)
                bound=data['max_total_plies'];assert type(bound) is int and ply<bound
                assert not five(b) and not five(w),'play continued after a win'
                if empty:assert root==(frozenset(),frozenset())
                if data['kind']=='black':
                    assert len(b)==len(w)
                    a=data['action']
                    if a.get('origin') is True and not b|w:
                        expected={(frozenset({(0,0)}),frozenset())}
                    else:expected=successors(root,0,(parse_point(a['reference']),parse_point(a['offset'])))
                else:
                    assert data['kind']=='white' and len(b)==len(w)+1
                    assert 'action' not in data
                    expected=successors(root,1)
                assert expected and isinstance(data['children'],list)
                actual={};children=data['children']
                for row in children:
                    state=position(row['position'])
                    assert sum(map(len,state))==ply+1,'non-increasing ply rank'
                    assert state not in actual,'duplicate child position'
                    assert isinstance(row['file'],str) and isinstance(row['sha256'],str)
                    actual[state]=row
                assert set(actual)==set(expected),'incomplete or extraneous successor coverage'
                for state,row in actual.items():
                    child,child_bound,_=visit(path.parent/row['file'],row['sha256'])
                    assert child==state,'external proof has a different root'
                    assert child_bound<=bound,'child exceeds parent horizon'
                counts['bundle_files']+=1;counts['bundle_edges']+=len(children)
            bindings.append({'file':str(path),'sha256':sha})
            return root,bound,sha
        finally:active.remove(path)
    root,bound,sha=visit(path,empty=require_empty)
    return {'status':'VERIFIED_REFERENCE_BUNDLE','sha256':sha,'root_position':{
        'black':sorted(root[0]),'white':sorted(root[1]),
        'to_move':'black' if len(root[0])==len(root[1]) else 'white'},
        'max_total_plies':bound,'scope':'empty_board' if not root[0]|root[1] else 'positional',
        'counts':dict(counts),'checked_files':bindings,
        'freshly_checked_files':fresh_files,'reused_checked_files':reused_files}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('proof',type=Path);ap.add_argument('--from-empty',action='store_true')
    ap.add_argument('--output',type=Path)
    args=ap.parse_args();started=time.monotonic()
    try:result=verify_file(args.proof,args.from_empty)
    except Exception as error:result={'status':'REJECTED_REFERENCE_BUNDLE','error':repr(error)}
    result.update(seconds=time.monotonic()-started,checker_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__),Path('scripts/reference_gap_verifier.py'),Path('scripts/reference_infinite_threat_witness.py'))})
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='checked_files'},ensure_ascii=True))
    if result['status']!='VERIFIED_REFERENCE_BUNDLE':raise SystemExit(1)


if __name__=='__main__':main()
