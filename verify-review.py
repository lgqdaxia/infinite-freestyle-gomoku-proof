"""Fresh verification of a derived, self-contained review directory.

No history receipt or search cache is an accepted proof premise. This transport
wrapper checks shipped bytes and then invokes the unchanged reference checker.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def confined(root, spelling):
    if not isinstance(spelling,str) or '\\' in spelling:
        raise ValueError('package path must use forward slashes')
    relative = Path(spelling)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('package path escapes release')
    path = (root/relative).resolve()
    path.relative_to(root)
    return path


def seal_payload(root,release):
    manifest = root/'shipped-manifest.jsonl'
    if digest(manifest) != release['shipped_manifest_sha256']:
        raise ValueError('shipped manifest differs from release')
    count = size = 0
    with manifest.open(encoding='utf8') as file:
        for line in file:
            row = json.loads(line)
            path = confined(root,row['file'])
            if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
                raise ValueError('missing or changed shipped bytes: '+row['file'])
            size += row['bytes']
            count += 1
            if row['role'] in ('cover','bundle'):
                data = json.loads(path.read_bytes())
                references = data['branches'] if row['role'] == 'cover' else data['children']
                for edge in references:
                    child = confined(root,(path.parent.relative_to(root)/edge['file']).as_posix())
                    if child.parent != root/'proofs/objects':
                        raise ValueError('noncanonical proof reference')
    if count != release['shipped_files'] or size != release['shipped_payload_bytes']:
        raise ValueError('shipped totals differ')
    return dict(files=count,payload_bytes=size)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--sample',action='store_true',help='Explicit positional smoke test, never an empty-board claim')
    args = ap.parse_args()
    if not __debug__:
        raise RuntimeError('Assertions must be enabled; do not use -O/-OO')
    if args.workers < 1:
        raise ValueError('positive worker count required')
    root = Path(__file__).resolve().parent
    os.chdir(root)
    release = json.loads((root/'release.json').read_bytes())
    if release['status'] != 'DERIVED_REVIEW_CANDIDATE_REQUIRES_FRESH_CHECK':
        raise ValueError('unrecognized release status')
    if release['scope'] != ('positional_sample' if args.sample else 'empty_board'):
        raise ValueError('scope mismatch; sample requires explicit --sample')
    output = args.output_dir.resolve()
    if output.exists():
        raise ValueError('fresh output directory required')
    started = time.monotonic()
    before = seal_payload(root,release)
    for spelling,expected in release['checker_sha256'].items():
        if digest(confined(root,spelling)) != expected:
            raise ValueError('shipped checker differs from frozen release')
    if args.sample:
        from scripts.reference_gap_package import verify_package
        output.mkdir(parents=True)
        sample = verify_package(root/'sample.zip',args.workers)
        if sample['status'] != 'VERIFIED_GAP_PROOF_PACKAGE' or sample['scope'] != 'positional':
            raise ValueError('sample is not the declared positional proof')
        (output/'result.json').write_text(json.dumps(sample,indent=2)+'\n',encoding='utf8')
        after = seal_payload(root,release)
        record = dict(status='VERIFIED_RELOCATED_POSITIONAL_SAMPLE',scope='positional_only_not_empty_board',before=before,after=after,seconds=time.monotonic()-started,command=sys.argv,runtime=dict(python=sys.version,platform=platform.platform()))
        (output/'release-acceptance.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
        print(json.dumps(record))
        return
    from scripts.reference_gap_opening_cover import verify_cover
    result = verify_cover(root/'proofs/empty-cover.json',output,args.workers)
    if result['status'] != 'VERIFIED_EMPTY_OPENING_COVER' or result['scope'] != 'empty_board' or result['verified_opening_roots'] != 20 or result['covered_first_replies'] != 120 or result['max_total_plies'] > 35 or result['root_position'] != {'black':[],'white':[],'to_move':'black'}:
        raise ValueError('wrong verified scope, coverage, or bound')
    if result['checker_sha256'] != release['checker_sha256']:
        raise ValueError('actual checker differs from frozen release')
    for edge in result['opening_receipts']:
        from receipt_stream import metadata
        receipt,receipt_sha,_ = metadata(output/edge['file'])
        if receipt_sha != edge['sha256'] or receipt['reused_checked_files'] != 0:
            raise ValueError('old receipt reused or final receipt changed')
    after = seal_payload(root,release)
    record = dict(status='VERIFIED_RELOCATED_EMPTY_BOARD_REVIEW_RELEASE',mathematical_result_sha256=digest(output/'result.json'),release_sha256=digest(root/'release.json'),before=before,after=after,seconds=time.monotonic()-started,command=sys.argv,runtime=dict(python=sys.version,platform=platform.platform()),original_workspace_access_required=False)
    (output/'release-acceptance.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
