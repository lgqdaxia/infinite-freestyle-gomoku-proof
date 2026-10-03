"""Independent complete checking of a self-contained content-addressed package.

No search/builder imports and no saved success receipts. Ordinary proof nodes
are checked by the independent reference kernel; bundle geometry is recomputed.
"""
import argparse,hashlib,json,re,time,zipfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from scripts.reference_gap_bundle_verifier import position
from scripts.reference_gap_verifier import RULES,parse_point,five,successors,verify


def digest(raw):return hashlib.sha256(raw).hexdigest()


def read_object(archive,key):
    assert isinstance(key,str) and re.fullmatch('[0-9a-f]{64}',key)
    raw=archive.read('objects/'+key+'.json');assert digest(raw)==key,'object hash mismatch'
    return json.loads(raw)


_ARCHIVE=None

def open_worker(path):
    global _ARCHIVE
    _ARCHIVE=zipfile.ZipFile(path,'r')


def ordinary(key):
    data=read_object(_ARCHIVE,key);result=verify(data)
    return dict(sha256=key,root_position=result['root_position'],max_total_plies=result['max_total_plies'],reachable_nodes=result['reachable_nodes'])


def verify_package(path,workers=4,require_empty=False,progress=None):
    if not __debug__:raise RuntimeError('Assertions must be enabled')
    assert type(workers) is int and workers>=1
    started=time.monotonic();package_sha256=digest(Path(path).read_bytes());active=set();seen=set();headers={};tasks=set();constraints=[]
    with zipfile.ZipFile(path,'r') as archive:
        names=archive.namelist();assert len(names)==len(set(names)),'duplicate ZIP entry'
        assert 'manifest.json' in names
        assert all(name=='manifest.json' or re.fullmatch(r'objects/[0-9a-f]{64}\.json',name) for name in names),'unexpected entry'
        manifest=json.loads(archive.read('manifest.json'))
        assert manifest['format']=='freestyle-gomoku-infinite-gap-package' and type(manifest['version']) is int and manifest['version']==1
        root_key=manifest['root']
        def walk(key,claimed=None,parent_bound=None):
            assert key not in active,'cyclic package graph'
            if claimed is not None:constraints.append((key,claimed,parent_bound))
            if key in seen:return
            data=read_object(archive,key);seen.add(key)
            if data['format']=='freestyle-gomoku-infinite-dynamic-gap':tasks.add(key);return
            assert data['format']=='freestyle-gomoku-infinite-gap-bundle' and type(data['version']) is int and data['version']==1
            assert data['rules']==RULES
            root=position(data['position']);b,w=root;ply=len(b)+len(w);bound=data['max_total_plies']
            assert type(bound) is int and ply<bound<=35 and not five(b) and not five(w)
            if data['kind']=='black':
                assert len(b)==len(w)
                action=data['action']
                if action.get('origin') is True and not b|w:expected={(frozenset({(0,0)}),frozenset())}
                else:expected=successors(root,0,(parse_point(action['reference']),parse_point(action['offset'])))
            else:
                assert data['kind']=='white' and len(b)==len(w)+1 and 'action' not in data
                expected=successors(root,1)
            assert expected and isinstance(data['children'],list)
            children={}
            for edge in data['children']:
                child=position(edge['position'])
                assert child not in children and sum(map(len,child))==ply+1
                key_child=edge['sha256'];assert isinstance(key_child,str) and re.fullmatch('[0-9a-f]{64}',key_child)
                assert edge['file']==key_child+'.json','noncanonical object reference'
                children[child]=key_child
            assert set(children)==set(expected),'incomplete successor coverage'
            active.add(key)
            try:
                for child,child_key in children.items():walk(child_key,child,bound)
            finally:active.remove(key)
            headers[key]=dict(sha256=key,root_position=data['position'],max_total_plies=bound)
        walk(root_key)
        assert {'objects/'+k+'.json' for k in seen}==set(names)-{'manifest.json'},'unreachable package objects'
    receipts=dict(headers)
    with ProcessPoolExecutor(max_workers=workers,initializer=open_worker,initargs=(str(path),)) as pool:
        jobs={pool.submit(ordinary,key):key for key in tasks}
        for future in as_completed(jobs):
            key=jobs[future];receipt=future.result();assert receipt['sha256']==key and receipt['max_total_plies']<=35
            receipts[key]=receipt
            if progress:progress(dict(checked=len(receipts)-len(headers),total=len(tasks),seconds=time.monotonic()-started))
    for key,claimed,bound in constraints:
        receipt=receipts[key];assert position(json.loads(json.dumps(receipt['root_position'])))==claimed and receipt['max_total_plies']<=bound
    root=receipts[root_key];state=position(json.loads(json.dumps(root['root_position'])))
    if require_empty:assert state==(frozenset(),frozenset()),'not an empty-board proof'
    assert digest(Path(path).read_bytes())==package_sha256,'package changed during verification'
    return dict(status='VERIFIED_GAP_PROOF_PACKAGE',package_sha256=package_sha256,root_sha256=root_key,root_position=root['root_position'],max_total_plies=root['max_total_plies'],
        scope='empty_board' if state==(frozenset(),frozenset()) else 'positional',objects=len(seen),ordinary_files=len(tasks),bundle_files=len(headers),
        ordinary_nodes=sum(r.get('reachable_nodes',0) for r in receipts.values()),seconds=time.monotonic()-started)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('package',type=Path);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--from-empty',action='store_true');ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    try:r=verify_package(args.package,args.workers,args.from_empty)
    except Exception as error:r=dict(status='REJECTED_GAP_PROOF_PACKAGE',error=repr(error))
    r['package_sha256']=digest(args.package.read_bytes())
    r['checker_sha256']={str(p):digest(p.read_bytes()) for p in map(Path,(__file__,'scripts/reference_gap_bundle_verifier.py','scripts/reference_gap_verifier.py','scripts/reference_infinite_threat_witness.py'))}
    args.output.write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
    if r['status']!='VERIFIED_GAP_PROOF_PACKAGE':raise SystemExit(1)

if __name__=='__main__':main()
