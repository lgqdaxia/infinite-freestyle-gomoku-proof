"""Fresh modular verification with bounded parallelism across child files.

Parent edges are independently recomputed. Workers run the ordinary independent
bundle verifier on every external proof; no on-disk success receipt is trusted.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import time
import traceback

from scripts.reference_gap_bundle_verifier import FORMAT,position,verify_file
from scripts.reference_gap_verifier import RULES,five,successors,parse_point


def write_progress(path,row):
    """Retry Windows sharing conflicts on the progress-file rename only."""
    path=Path(path);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for delay in (.01,.02,.04,.08,.16,.32,.64):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(delay)
    # A persistent access failure is still reported. Certificate failures
    # never enter this retry path and no failed verification is accepted.
    tmp.replace(path)


def checked_position(receipt):
    # verify_file returns Python tuples; serialize its own completed receipt
    # before applying the strict JSON-position parser used for certificate data.
    return position(json.loads(json.dumps(receipt['root_position'])))


def verify_parallel(path,workers=2,require_empty=False,progress=None):
    if not __debug__:raise RuntimeError('Assertions must be enabled')
    if workers<1:raise ValueError('positive worker count required')
    active=set();headers={};tasks={};constraints=[]
    def walk(path,expected_hash=None,claimed=None,parent_bound=None,empty=False):
        path=Path(path).resolve()
        # File names affect scheduling only. Any differently named bundle is
        # checked recursively in full by a worker, never treated as a receipt.
        if not path.name.endswith('.bundle.json'):
            key=(str(path),expected_hash)
            tasks[key]=str(path);constraints.append((key,claimed,parent_bound,empty))
            return None
        assert path not in active,'cyclic bundle headers'
        raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        if expected_hash is not None:assert sha==expected_hash,'bundle hash mismatch'
        data=json.loads(raw)
        if data.get('format')!=FORMAT:
            key=(str(path),sha);tasks[key]=str(path)
            constraints.append((key,claimed,parent_bound,empty));return None
        assert type(data['version']) is int and data['version']==1 and data['rules']==RULES
        root=position(data['position']);b,w=root;ply=len(b)+len(w)
        bound=data['max_total_plies'];assert type(bound) is int and ply<bound
        assert not five(b) and not five(w)
        if claimed is not None:assert root==claimed and bound<=parent_bound
        if empty:assert root==(frozenset(),frozenset())
        if data['kind']=='black':
            assert len(b)==len(w)
            a=data['action']
            if a.get('origin') is True and not b|w:expected={(frozenset({(0,0)}),frozenset())}
            else:expected=successors(root,0,(parse_point(a['reference']),parse_point(a['offset'])))
        else:
            assert data['kind']=='white' and len(b)==len(w)+1 and 'action' not in data
            expected=successors(root,1)
        assert expected and isinstance(data['children'],list)
        children={}
        for row in data['children']:
            state=position(row['position'])
            assert state not in children and sum(map(len,state))==ply+1
            assert isinstance(row['file'],str) and isinstance(row['sha256'],str)
            children[state]=row
        assert set(children)==set(expected),'incomplete successor coverage'
        active.add(path)
        try:
            for state,row in children.items():walk(path.parent/row['file'],row['sha256'],state,bound)
        finally:active.remove(path)
        headers[str(path)]={'sha256':sha,'root_position':data['position'],'max_total_plies':bound,
                            'children':len(children)}
        return {'sha256':sha,'root_position':data['position'],'max_total_plies':bound}
    root_receipt=walk(path,empty=require_empty);results={};started=time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        # Start the largest files first, avoiding a single large final task.
        ordered=sorted(tasks.items(),key=lambda item:Path(item[1]).stat().st_size,reverse=True)
        futures={pool.submit(verify_file,p):key for key,p in ordered}
        for future in as_completed(futures):
            key=futures[future];receipt=future.result()
            assert receipt['status']=='VERIFIED_REFERENCE_BUNDLE'
            if key[1] is not None:assert receipt['sha256']==key[1],'leaf hash mismatch'
            results[key]=receipt
            if progress:progress({'status':'CHECKING','checked_files':len(results),'total_files':len(tasks),
                                  'last_file':key[0],'seconds':time.monotonic()-started})
    for key,claimed,bound,empty in constraints:
        receipt=results[key];state=checked_position(receipt)
        if claimed is not None:assert state==claimed and receipt['max_total_plies']<=bound
        if empty:assert state==(frozenset(),frozenset())
    if root_receipt is None:
        root_receipt=next(r for k,r in results.items() if k[0]==str(Path(path).resolve()))
    root=checked_position(root_receipt)
    return {'status':'VERIFIED_REFERENCE_BUNDLE','root_position':root_receipt['root_position'],
            'sha256':root_receipt['sha256'],'max_total_plies':root_receipt['max_total_plies'],
            'scope':'empty_board' if not root[0]|root[1] else 'positional',
            'bundle_headers':headers,'freshly_checked_files':len(results),
            'ordinary_node_occurrences':sum(r['counts'].get('ordinary_node_occurrences',0) for r in results.values()),
            'checked_files':[item for r in results.values() for item in r['checked_files']]}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('proof',type=Path);ap.add_argument('--workers',type=int,default=2)
    ap.add_argument('--from-empty',action='store_true');ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();started=time.monotonic()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    last_progress=0.
    def progress(row):
        nonlocal last_progress
        now=time.monotonic()
        if now-last_progress<1 and row['checked_files']!=row['total_files']:return
        p=args.output.with_name(args.output.stem+'-progress.json')
        write_progress(p,row);last_progress=now
    try:result=verify_parallel(args.proof,args.workers,args.from_empty,progress)
    except Exception as error:result={'status':'REJECTED_REFERENCE_BUNDLE','error':repr(error),'traceback':traceback.format_exc()}
    result.update(seconds=time.monotonic()-started,checker_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__),Path('scripts/reference_gap_bundle_verifier.py'),Path('scripts/reference_gap_verifier.py'),Path('scripts/reference_infinite_threat_witness.py'))})
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checked_files','bundle_headers')},ensure_ascii=True))
    if result['status']!='VERIFIED_REFERENCE_BUNDLE':raise SystemExit(1)


if __name__=='__main__':main()
