"""Small shipping-entry regressions; these do not simulate mathematical acceptance."""
import hashlib
import gc
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

from review_transport import digest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('full_review_entry', HERE/'verify-full-review.py')
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


def fixture(root, reference='leaf.json', wrong_sha=False):
    leaf = b'{"fixture":"shipping test only"}'
    (root/'leaf.json').write_bytes(leaf)
    sha = hashlib.sha256(leaf).hexdigest()
    cover = {'branches':[{'file':reference, 'sha256':'0'*64 if wrong_sha else sha}]}
    (root/'cover.json').write_text(json.dumps(cover), encoding='utf8')
    rows = [{'file':name, 'bytes':(root/name).stat().st_size,
             'sha256':digest(root/name), 'role':role}
            for name,role in [('cover.json','cover'),('leaf.json','ordinary')]]
    manifest = root/'proof-manifest.jsonl'
    manifest.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf8')
    return {'cover':'cover.json', 'proof_files':2,
            'proof_payload_bytes':sum(row['bytes'] for row in rows),
            'proof_manifest_sha256':digest(manifest)}


def rejected(root, release):
    accepted = False
    try:
        db, _ = entry.index_and_seal(root, release, root/'index.sqlite')
        db.close()
        accepted = True
    except (ValueError, sqlite3.IntegrityError):
        pass
    # The real entry exits its process on an error. In this in-process fixture,
    # collect failed sqlite connections before Windows removes the temp tree.
    gc.collect()
    if accepted:
        raise AssertionError('invalid shipping inputs accepted')


def test():
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        good = base/'good'; good.mkdir()
        release = fixture(good)
        db, counts = entry.index_and_seal(good, release, good/'index.sqlite')
        assert counts == {'files':2, 'bytes':release['proof_payload_bytes']}
        assert db.execute('SELECT COUNT(*) FROM files').fetchone() == (2,)
        db.close()
        for name, reference, wrong_sha in [('outside','../outside.json',False),
                                           ('missing','missing.json',False),
                                           ('digest','leaf.json',True)]:
            root = base/name; root.mkdir()
            rejected(root, fixture(root, reference, wrong_sha))
        root = base/'changed'; root.mkdir()
        release = fixture(root)
        (root/'leaf.json').write_bytes(b'changed')
        rejected(root, release)
        root = base/'totals'; root.mkdir()
        release = fixture(root); release['proof_files'] = 3
        rejected(root, release)
        root = base/'duplicate'; root.mkdir()
        release = fixture(root)
        manifest = root/'proof-manifest.jsonl'
        manifest.write_text(manifest.read_text()+manifest.read_text().splitlines()[0]+'\n')
        release['proof_manifest_sha256'] = digest(manifest)
        rejected(root, release)
        result = subprocess.run([sys.executable,'-B','-O',str(HERE/'verify-full-review.py'),
                                 '--output-dir',str(base/'must-not-exist')],capture_output=True)
        assert result.returncode != 0
        assert b'Use assertions' in result.stderr and not (base/'must-not-exist').exists()
    print('PASSED: exact shipping manifest, reference closure, digest/count/duplicate rejection, optimized-interpreter rejection')


if __name__ == '__main__':
    test()
