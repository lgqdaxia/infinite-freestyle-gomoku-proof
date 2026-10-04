"""Fresh verification of the byte-preserved complete Gomoku review corpus."""
import argparse
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import time

from review_transport import confined, digest, manifest_rows


def index_and_seal(root,release,database,progress=None):
    manifest=root/'proof-manifest.jsonl'
    if digest(manifest)!=release['proof_manifest_sha256']:
        raise ValueError('proof manifest changed')
    db=sqlite3.connect(database)
    db.execute('CREATE TABLE files(file TEXT PRIMARY KEY, sha256 TEXT, bytes INTEGER, role TEXT)')
    total=size=0
    bundles=[]
    for row in manifest_rows(manifest):
        path=confined(root,row['file'])
        if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:
            raise ValueError('missing or altered proof bytes: '+row['file'])
        db.execute('INSERT INTO files VALUES(?,?,?,?)',
            (row['file'],row['sha256'],row['bytes'],row['role']))
        if row['role'] in ('cover','bundle'):bundles.append(row['file'])
        elif row['role'] != 'ordinary':raise ValueError('unknown proof role')
        total+=1;size+=row['bytes']
        if total%10000==0:
            db.commit()
            if progress:progress({'phase':'SEALING_INPUTS','files':total,'bytes':size})
    db.commit()
    if total!=release['proof_files'] or size!=release['proof_payload_bytes']:
        raise ValueError('proof manifest totals changed')
    # Stored filenames retain Windows separators; all mathematical file bytes
    # and all hashes are unchanged. Validate every declared external reference.
    for name in bundles:
        path=confined(root,name)
        data=json.loads(path.read_bytes())
        edges=data['branches'] if name==release['cover'] else data['children']
        for edge in edges:
            child=(path.parent/edge['file']).resolve()
            relative=child.relative_to(root).as_posix()
            expected=db.execute('SELECT sha256 FROM files WHERE file=?',(relative,)).fetchone()
            if expected is None or expected[0]!=edge['sha256']:
                raise ValueError('unshipped or mismatched external reference')
    return db,{'files':total,'bytes':size}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--output-dir',type=Path,required=True)
    args=ap.parse_args()
    if not __debug__:raise RuntimeError('Use assertions; -O and -OO are unsupported')
    if args.workers < 1:raise ValueError('positive worker count required')
    if os.name!='nt':raise RuntimeError('This byte-preserved release uses native Windows reference paths')
    root=Path(__file__).resolve().parent
    os.chdir(root)
    release=json.loads((root/'review-release.json').read_bytes())
    if release['format']!='gomoku-byte-preserved-full-review' or release['version']!=1:
        raise ValueError('wrong release format')
    for name,sha in release['checker_sha256'].items():
        if digest(confined(root,name))!=sha:raise ValueError('checker source changed: '+name)
    output=args.output_dir.resolve()
    if output.exists():raise ValueError('use a new output directory')
    output.mkdir(parents=True)
    started=time.monotonic()
    def progress(item):
        (output/'transport-progress.json').write_text(json.dumps(dict(item,seconds=time.monotonic()-started))+'\n',encoding='utf8')
    db,before=index_and_seal(root,release,output/'shipping-index.sqlite',progress)
    from scripts.reference_gap_opening_cover import verify_cover
    result=verify_cover(confined(root,release['cover']),output/'mathematics',args.workers)
    if (result['status']!='VERIFIED_EMPTY_OPENING_COVER' or result['scope']!='empty_board'
            or result['root_position']!={'black':[],'white':[],'to_move':'black'}
            or result['verified_opening_roots']!=20 or result['covered_first_replies']!=120
            or result['max_total_plies']>35 or result['sha256']!=release['cover_sha256']
            or result['checker_sha256']!=release['checker_sha256']):
        raise ValueError('wrong verified scope, coverage, bound or bytes')
    from receipt_stream import metadata
    for edge in result['opening_receipts']:
        item,sha,_=metadata(output/'mathematics'/edge['file'])
        if sha!=edge['sha256'] or item['reused_checked_files']!=0:
            raise ValueError('stale or changed verification receipt')
    for count,(name,sha,size,role) in enumerate(db.execute('SELECT * FROM files ORDER BY file'),1):
        path=confined(root,name)
        if path.stat().st_size!=size or digest(path)!=sha:
            raise ValueError('proof changed during verification')
        if count%10000==0:progress({'phase':'FINAL_BYTE_SEAL','files':count})
    db.close()
    record=dict(status='VERIFIED_EMPTY_BOARD_REVIEW_RELEASE',scope='empty_board',
        max_total_plies=35,verified_opening_roots=20,covered_first_replies=120,
        cover_sha256=result['sha256'],mathematical_result_sha256=digest(output/'mathematics/result.json'),
        release_sha256=digest(root/'review-release.json'),before=before,
        checker_sha256=result['checker_sha256'],seconds=time.monotonic()-started,
        command=sys.argv,runtime={'python':sys.version,'platform':platform.platform()})
    (output/'release-acceptance.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    print(json.dumps(record))


if __name__=='__main__':main()
