"""Independent empty-board covering theorem; full fresh opening verification.

No search, primary geometry or assembler imports. The only permitted frame
maps are the eight lattice isometries fixing the origin. Old success receipts
and campaign status labels are never premises of this checker.
"""
import argparse,hashlib,json,time
from pathlib import Path
from scripts.reference_gap_verifier import RULES,parse_point,successors
from scripts.reference_gap_bundle_verifier import position
from scripts.reference_gap_bundle_batched import verify_parallel,write_progress

FORMAT='freestyle-gomoku-infinite-opening-cover'


def validate_header(data):
    if not __debug__:raise RuntimeError('Assertions must be enabled')
    assert data['format']==FORMAT and type(data['version']) is int and data['version']==1
    assert data['rules']==RULES and position(data['position'])==(frozenset(),frozenset())
    assert parse_point(data['first_move'])==(0,0)
    h=data['max_total_plies'];assert type(h) is int and 3<=h<=35
    branches=data['branches'];assert isinstance(branches,list) and len(branches)==20
    roots=[]
    for row in branches:
        p=parse_point(row['representative']);assert p!=(0,0)
        assert isinstance(row['file'],str) and row['file']
        sha=row['sha256'];assert isinstance(sha,str) and len(sha)==64 and all(c in '0123456789abcdef' for c in sha)
        roots.append((frozenset({(0,0)}),frozenset({p})))
    assert len(set(roots))==20,'duplicate opening roots'
    expected=successors((frozenset({(0,0)}),frozenset()),1)
    assert len(expected)==120
    # Independent enumeration of the two signed axis permutations.
    matrices={(u,0,0,v) for u in (-1,1) for v in (-1,1)}|{(0,u,v,0) for u in (-1,1) for v in (-1,1)}
    replies=data['replies'];assert isinstance(replies,list) and len(replies)==120
    covered=set();used=set()
    for row in replies:
        q=parse_point(row['point']);state=(frozenset({(0,0)}),frozenset({q}))
        assert state not in covered,'duplicate first reply'
        i=row['branch'];assert type(i) is int and 0<=i<20
        m=row['matrix'];assert isinstance(m,list) and len(m)==4 and all(type(v) is int for v in m)
        assert tuple(m) in matrices,'not a lattice D4 isometry'
        x,y=next(iter(roots[i][1]));a,b,c,d=m
        assert (a*x+b*y,c*x+d*y)==q,'wrong transformed opening root'
        used.add(i);covered.add(state)
    assert covered==expected and used==set(range(20)),'incomplete first-reply coverage'
    return roots,h


def verify_cover(path,output_dir,workers=4):
    if not __debug__:raise RuntimeError('Assertions must be enabled')
    path=Path(path).resolve();raw=path.read_bytes();data=json.loads(raw);roots,h=validate_header(data)
    output_dir=Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):raise ValueError('Use a fresh verification directory; preserve old receipts')
    output_dir.mkdir(parents=True,exist_ok=True);started=time.monotonic();receipts=[]
    for i,(row,root) in enumerate(zip(data['branches'],roots)):
        branch=path.parent/row['file']
        assert hashlib.sha256(branch.read_bytes()).hexdigest()==row['sha256'],'opening file changed'
        def progress(item):write_progress(output_dir/'progress.json',dict(item,opening_index=i,verified_roots=len(receipts),total_roots=20))
        receipt=verify_parallel(branch,workers,progress=progress)
        assert receipt['status']=='VERIFIED_REFERENCE_BUNDLE' and receipt['sha256']==row['sha256']
        assert position(json.loads(json.dumps(receipt['root_position'])))==root,'opening certificate starts at a different position'
        assert receipt['max_total_plies']<=h,'opening certificate exceeds total bound'
        file=output_dir/f'opening-{i:02}.json';write_progress(file,receipt)
        receipts.append(dict(file=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),proof_sha256=row['sha256']))
    dependencies=('scripts/reference_gap_opening_cover.py','scripts/reference_gap_bundle_batched.py','scripts/reference_gap_bundle_parallel.py','scripts/reference_gap_bundle_verifier.py','scripts/reference_gap_verifier.py','scripts/reference_infinite_threat_witness.py','scripts/reference_prepared_remote_sequence.py','scripts/reference_remote_interruption_sequence.py')
    result=dict(status='VERIFIED_EMPTY_OPENING_COVER',scope='empty_board',root_position=data['position'],
        sha256=hashlib.sha256(raw).hexdigest(),max_total_plies=h,verified_opening_roots=20,covered_first_replies=120,
        opening_receipts=receipts,seconds=time.monotonic()-started,
        checker_sha256={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in dependencies})
    write_progress(output_dir/'result.json',result);return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('proof',type=Path)
    ap.add_argument('--from-empty',action='store_true',required=True);ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--output-dir',type=Path,required=True);args=ap.parse_args()
    # Any exception exits nonzero and leaves no successful final receipt.
    result=verify_cover(args.proof,args.output_dir,args.workers);print(json.dumps(result))


if __name__=='__main__':main()
