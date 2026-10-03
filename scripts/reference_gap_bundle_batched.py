"""Fresh complete verification, with bounded transport batches.

Parent edges are independently recomputed. Workers run the ordinary independent
bundle verifier on every external proof; no on-disk success receipt is trusted.
"""
import argparse
import os
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
import hashlib
import json
from pathlib import Path
import time
import traceback

from scripts.reference_gap_bundle_verifier import FORMAT,position,verify_file
from scripts.reference_gap_verifier import RULES,five,successors,parse_point


class VerificationStopped(Exception):
    """A file-boundary stop never produces a successful receipt."""


def check_stop(stop):
    if stop is not None and Path(stop).exists():
        raise VerificationStopped('verification stopped at a safe file boundary')


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


def verify_batch(paths,stop=None):
    receipts=[]
    for p in paths:
        check_stop(stop)
        # No previous receipt or ordinary_cache is supplied. Every leaf is
        # checked by the original, unchanged independent mathematical kernel.
        receipts.append(verify_file(p))
    check_stop(stop)
    return receipts


def verify_parallel(path,workers=2,require_empty=False,progress=None,*,stop=None):
    if not __debug__:raise RuntimeError('Assertions must be enabled')
    if workers<1:raise ValueError('positive worker count required')
    started=time.monotonic();active=set();headers={};tasks={};constraints=[]
    last_report=0.
    def report(row,force=False):
        nonlocal last_report
        check_stop(stop);now=time.monotonic()
        if progress and (force or now-last_report>=1):
            progress(dict(row,seconds=now-started));last_report=now
    def walk(path,expected_hash=None,claimed=None,parent_bound=None,empty=False):
        check_stop(stop)
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
        cached=headers.get(str(path))
        if cached is not None:
            # One actual path cannot satisfy two different incoming hashes.
            # Do not overwrite a previously discovered binding if a file
            # changes between visits, even when both versions are valid.
            assert cached['sha256']==sha,'conflicting header versions in proof closure'
            # This is a memo of discovered geometry, not a success receipt.
            # All its leaves remain in tasks and must finish a fresh check;
            # every dependency's actual bytes are rebound in the final audit.
            cached_root=position(cached['root_position'])
            if claimed is not None:assert cached_root==claimed and cached['max_total_plies']<=parent_bound
            if empty:assert cached_root==(frozenset(),frozenset())
            return {k:cached[k] for k in ('sha256','root_position','max_total_plies')}
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
        report(dict(status='COLLECTING_HEADERS',bundle_headers=len(headers),total_files=len(tasks)))
        return {'sha256':sha,'root_position':data['position'],'max_total_plies':bound}
    root_receipt=walk(path,empty=require_empty);results={};collected=time.monotonic()
    report(dict(status='HEADERS_COMPLETE',bundle_headers=len(headers),total_files=len(tasks)),True)
    # Every file retains its own complete independent check. Only transport
    # changes: batch small files and keep at most3*workers pending futures.
    ordered=sorted(((Path(p).stat().st_size,key,p) for key,p in tasks.items()),reverse=True)
    def batches():
        small=[]
        for size,key,p in ordered:
            if size>65536:
                if small:yield small;small=[]
                yield [(key,p)]
            else:
                small.append((key,p))
                if len(small)>=64:yield small;small=[]
        if small:yield small
    iterator=iter(batches());pending={};exhausted=False;batch_count=0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        while pending or not exhausted:
            while not exhausted and len(pending)<workers*3:
                batch=next(iterator,None)
                if batch is None:exhausted=True;break
                check_stop(stop)
                pending[pool.submit(verify_batch,[p for key,p in batch],str(stop) if stop is not None else None)]=batch;batch_count+=1
            if not pending:break
            done,_=wait(pending,timeout=.2,return_when=FIRST_COMPLETED)
            check_stop(stop)
            for future in done:
                batch=pending.pop(future);receipts=future.result();assert len(receipts)==len(batch)
                for (key,p),receipt in zip(batch,receipts):
                    assert receipt['status']=='VERIFIED_REFERENCE_BUNDLE'
                    if key[1] is not None:assert receipt['sha256']==key[1],'leaf hash mismatch'
                    results[key]=receipt
                report({'status':'CHECKING','checked_files':len(results),'total_files':len(tasks),
                                      'last_file':batch[-1][0][0],'seconds':time.monotonic()-started,
                                      'submitted_batches':batch_count,'pending_batches':len(pending)},len(results)==len(tasks))
    checked=time.monotonic()
    for key,claimed,bound,empty in constraints:
        receipt=results[key];state=checked_position(receipt)
        if claimed is not None:assert state==claimed and receipt['max_total_plies']<=bound
        if empty:assert state==(frozenset(),frozenset())
    # Bind the successful computation to the entire currently saved closure.
    # This also guards memoized headers and changes made while workers ran.
    bindings={}
    for p,item in headers.items():bindings[p]=item['sha256']
    for r in results.values():
        for item in r['checked_files']:
            p=item['file'];old=bindings.setdefault(p,item['sha256'])
            assert old==item['sha256'],'conflicting file versions in proof closure'
    for i,(p,sha) in enumerate(bindings.items(),1):
        check_stop(stop)
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha,'proof dependency changed during verification'
        report(dict(status='BINDING_COMPLETE_CLOSURE',bound_files=i,total_bindings=len(bindings)))
    check_stop(stop)
    if root_receipt is None:
        root_receipt=next(r for k,r in results.items() if k[0]==str(Path(path).resolve()))
    root=checked_position(root_receipt)
    return {'status':'VERIFIED_REFERENCE_BUNDLE','root_position':root_receipt['root_position'],
            'sha256':root_receipt['sha256'],'max_total_plies':root_receipt['max_total_plies'],
            'scope':'empty_board' if not root[0]|root[1] else 'positional',
            'bundle_headers':headers,'freshly_checked_files':len(results),
            'reused_checked_files':0,
            'ordinary_node_occurrences':sum(r['counts'].get('ordinary_node_occurrences',0) for r in results.values()),
            'counts':{'ordinary_proof_files':sum(r['counts'].get('ordinary_proof_files',0) for r in results.values()),
                      'ordinary_node_occurrences':sum(r['counts'].get('ordinary_node_occurrences',0) for r in results.values()),
                      'bundle_files':len(headers)+sum(r['counts'].get('bundle_files',0) for r in results.values()),
                      'bundle_edges':sum(h['children'] for h in headers.values())+sum(r['counts'].get('bundle_edges',0) for r in results.values())},
            'transport':{'workers':workers,'batch_size':64,'max_pending_batches':workers*3,'submitted_batches':batch_count},
            'phase_seconds':{'headers':collected-started,'fresh_checks':checked-collected,
                             'bindings':time.monotonic()-checked},
            'checked_files':[{'file':p,'sha256':sha} for p,sha in bindings.items()]}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('proof',type=Path);ap.add_argument('--workers',type=int,default=2)
    ap.add_argument('--from-empty',action='store_true');ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--stop',type=Path)
    args=ap.parse_args();started=time.monotonic()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    last_progress=0.
    def progress(row):
        nonlocal last_progress
        now=time.monotonic()
        if now-last_progress<1 and row.get('checked_files')!=row.get('total_files'):return
        p=args.output.with_name(args.output.stem+'-progress.json')
        write_progress(p,row);last_progress=now
    try:result=verify_parallel(args.proof,args.workers,args.from_empty,progress,stop=args.stop)
    except VerificationStopped as error:result={'status':'INTERRUPTED_REFERENCE_BUNDLE','error':str(error)}
    except Exception as error:result={'status':'REJECTED_REFERENCE_BUNDLE','error':repr(error),'traceback':traceback.format_exc()}
    checker_names=('reference_gap_bundle_verifier.py','reference_gap_verifier.py',
        'reference_infinite_threat_witness.py','reference_gap_opening_cover.py',
        'reference_prepared_remote_sequence.py','reference_remote_interruption_sequence.py',
        'reference_gap_bundle_parallel.py')
    result.update(seconds=time.monotonic()-started,checker_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__),*(Path('scripts')/name for name in checker_names))})
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checked_files','bundle_headers')},ensure_ascii=True))
    if result['status']!='VERIFIED_REFERENCE_BUNDLE':raise SystemExit(1)


if __name__=='__main__':main()
