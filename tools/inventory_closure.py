"""Read-only receipt-bound proof inventory, not mathematical re-verification.

Read each distinct selected proof once. Never enumerate experimental directories.
The output SQLite manifest and totals are release planning evidence only.
"""
import argparse
import codecs
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import time


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Stream:
    """Incremental root-object parser; checked_files is streamed item by item."""
    def __init__(self, path):
        self.file = Path(path).open('rb')
        self.hash = hashlib.sha256()
        self.decoder = codecs.getincrementaldecoder('utf-8')()
        self.json = json.JSONDecoder()
        self.buffer = ''
        self.offset = 0
        self.eof = False

    def more(self):
        self.buffer = self.buffer[self.offset:]
        self.offset = 0
        raw = self.file.read(65536)
        self.hash.update(raw)
        self.eof = not raw
        self.buffer += self.decoder.decode(raw, final=self.eof)

    def ws(self):
        while True:
            while self.offset < len(self.buffer) and self.buffer[self.offset].isspace():
                self.offset += 1
            if self.offset < len(self.buffer) or self.eof:
                return
            self.more()

    def token(self, value):
        self.ws()
        if self.buffer[self.offset:self.offset + 1] != value:
            raise ValueError('malformed receipt token, expected ' + value)
        self.offset += 1

    def value(self):
        self.ws()
        while True:
            try:
                result, end = self.json.raw_decode(self.buffer, self.offset)
                self.offset = end
                return result
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self.more()

    def bindings(self):
        self.token('{')
        count = 0
        metadata = {}
        keys = set()
        while True:
            key = self.value()
            if not isinstance(key, str) or key in keys:
                raise ValueError('invalid or duplicate receipt field')
            keys.add(key)
            self.token(':')
            if key == 'checked_files':
                self.token('[')
                self.ws()
                if self.buffer[self.offset:self.offset+1] != ']':
                    while True:
                        row = self.value()
                        count += 1
                        yield row
                        self.ws()
                        if self.buffer[self.offset:self.offset+1] == ']':
                            break
                        self.token(',')
                self.token(']')
            else:
                metadata[key] = self.value()
            self.ws()
            if self.buffer[self.offset:self.offset+1] == '}':
                self.token('}')
                break
            self.token(',')
        self.ws()
        if not self.eof:
            self.more()
            self.ws()
        if not self.eof or self.offset != len(self.buffer):
            raise ValueError('trailing receipt data')
        if 'checked_files' not in keys:
            raise ValueError('receipt has no checked_files')
        self.metadata = metadata
        self.count = count
        self.digest = self.hash.hexdigest()
        self.file.close()


def atomic_json(path, data):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def confined(root, path):
    resolved = Path(path).resolve()
    resolved.relative_to(root)
    return resolved


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-root', type=Path, required=True)
    ap.add_argument('--seal', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--rule-counter', type=Path)
    args = ap.parse_args()
    if not __debug__:
        raise RuntimeError('Assertions must be enabled')
    root = args.source_root.resolve()
    out = args.output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('fresh output directory required')
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    seal_raw = args.seal.read_bytes()
    seal = json.loads(seal_raw)
    if seal['status'] != 'CURRENT_BYTES_BOUND_TO_FRESH_EMPTY_CHECK':
        raise ValueError('not the completed final byte seal')
    db = sqlite3.connect(out/'closure.sqlite')
    db.execute('CREATE TABLE files(path TEXT PRIMARY KEY,relative_path TEXT NOT NULL,sha256 TEXT NOT NULL,openings INTEGER NOT NULL,occurrences INTEGER NOT NULL,bytes INTEGER,format TEXT)')
    db.execute('CREATE TABLE edges(parent TEXT,child TEXT,sha256 TEXT,spelling TEXT)')
    for index, receipt in enumerate(seal['opening_receipts']):
        if receipt['index'] != index:
            raise ValueError('noncanonical opening receipt order')
        stream = Stream(confined(root, receipt['file']))
        for number, row in enumerate(stream.bindings(), 1):
            path = confined(root, row['file'])
            key = os.path.normcase(str(path))
            digest = row['sha256']
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('invalid dependency digest')
            old = db.execute('SELECT sha256,openings FROM files WHERE path=?', (key,)).fetchone()
            if old:
                if old[0] != digest or old[1] & (1 << index):
                    raise ValueError('conflicting digest or duplicated path inside receipt')
                db.execute('UPDATE files SET openings=openings|?,occurrences=occurrences+1 WHERE path=?', (1 << index,key))
            else:
                db.execute('INSERT INTO files VALUES(?,?,?,?,?,NULL,NULL)', (key,path.relative_to(root).as_posix(),digest,1 << index,1))
            if number % 10000 == 0:
                db.commit()
                atomic_json(out/'progress.json', dict(phase='RECEIPT_UNION',opening=index,receipt_files=number,seconds=time.monotonic()-started))
        if stream.digest != receipt['sha256'] or stream.count != receipt['files']:
            raise ValueError('receipt byte hash or count differs from seal')
        if stream.metadata['status'] != 'VERIFIED_REFERENCE_BUNDLE' or stream.metadata['sha256'] != receipt['proof_sha256'] or stream.metadata['reused_checked_files'] != 0:
            raise ValueError('receipt is not the bound fresh successful opening check')
        db.commit()
    unique, occurrences = db.execute('SELECT count(*),sum(occurrences) FROM files').fetchone()
    if unique != seal['distinct_dependency_files'] or occurrences != seal['dependency_occurrences']:
        raise ValueError('closure count differs from seal')
    counter = None
    counter_sha = None
    if args.rule_counter:
        spec = importlib.util.spec_from_file_location('review_rule_counter', args.rule_counter)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        counter = module.reachable_kind_counts
        counter_sha = sha(args.rule_counter.read_bytes())
    totals = Counter()
    weighted = Counter()
    rules_unique = Counter()
    rules_weighted = Counter()
    refs = Counter()
    cover_path = confined(root, seal['cover'])
    cover_raw = cover_path.read_bytes()
    if sha(cover_raw) != seal['cover_sha256']:
        raise ValueError('cover differs from seal')
    cover = json.loads(cover_raw)
    roots = []
    for row in cover['branches']:
        path = confined(root, cover_path.parent / row['file'])
        key = os.path.normcase(str(path))
        stored = db.execute('SELECT sha256 FROM files WHERE path=?', (key,)).fetchone()
        if not stored or stored[0] != row['sha256']:
            raise ValueError('cover branch missing from bound closure')
        roots.append(key)
    for number, (key,relative,digest,multiplicity) in enumerate(db.execute('SELECT path,relative_path,sha256,occurrences FROM files ORDER BY path'), 1):
        path = root / relative
        raw = path.read_bytes()
        if sha(raw) != digest:
            raise ValueError('current dependency changed: ' + relative)
        data = json.loads(raw)
        role = data['format']
        if role not in ('freestyle-gomoku-infinite-dynamic-gap','freestyle-gomoku-infinite-gap-bundle'):
            raise ValueError('unrecognized selected proof format')
        totals['payload_bytes'] += len(raw)
        totals[role] += 1
        weighted[role] += multiplicity
        db.execute('UPDATE files SET bytes=?,format=? WHERE path=?', (len(raw),role,key))
        if role == 'freestyle-gomoku-infinite-gap-bundle':
            for edge in data['children']:
                spelling = edge['file']
                child = confined(root,path.parent/spelling)
                child_key = os.path.normcase(str(child))
                stored = db.execute('SELECT sha256 FROM files WHERE path=?', (child_key,)).fetchone()
                if not stored or stored[0] != edge['sha256']:
                    raise ValueError('referenced child absent or incorrectly bound')
                db.execute('INSERT INTO edges VALUES(?,?,?,?)', (key,child_key,edge['sha256'],spelling))
                refs['absolute' if Path(spelling).is_absolute() else 'relative'] += 1
                refs['backslash' if '\\' in spelling else 'forward_or_plain'] += 1
                totals['bundle_edges'] += 1
                weighted['bundle_edges'] += multiplicity
        elif counter:
            rule_result = counter(data)
            counts = rule_result['kinds']
            totals['ordinary_reachable_nodes'] += rule_result['reachable_nodes']
            weighted['ordinary_reachable_nodes'] += rule_result['reachable_nodes']*multiplicity
            totals['ordinary_stored_nodes'] += rule_result['stored_nodes']
            totals['ordinary_unreachable_nodes'] += rule_result['unreachable_nodes']
            rules_unique.update(counts)
            rules_weighted.update({kind:count*multiplicity for kind,count in counts.items()})
        if number % 1000 == 0:
            db.commit()
            atomic_json(out/'progress.json', dict(phase='READ_UNIQUE_PROOFS',read=number,total=unique,payload_bytes=totals['payload_bytes'],seconds=time.monotonic()-started))
    db.commit()
    # Root reachability is checked against the receipt-selected union, independent
    # of the historical filenames or success labels. WITH UNION deduplicates DAGs.
    root_values = ','.join('(?)' for _ in roots)
    reachable = db.execute('WITH RECURSIVE reachable(path) AS (VALUES '+root_values+' UNION SELECT edges.child FROM edges JOIN reachable ON edges.parent=reachable.path) SELECT count(*) FROM reachable',roots).fetchone()[0]
    if reachable != unique:
        raise ValueError('receipt union has missing or unreachable proof paths')
    if counter and weighted['ordinary_reachable_nodes'] != 109364098:
        raise ValueError('weighted reachable node count differs from sealed cost inventory')
    result = dict(status='COMPLETE_RECEIPT_BOUND_INVENTORY_NOT_MATHEMATICAL_RECHECK',seal_sha256=sha(seal_raw),cover_sha256=sha(cover_raw),distinct_paths=unique,dependency_occurrences=occurrences,totals=dict(totals),weighted_occurrences=dict(weighted),reference_spellings=dict(refs),rule_unique_path_nodes=dict(rules_unique),rule_node_occurrences=dict(rules_weighted),rule_counter_sha256=counter_sha,seconds=time.monotonic()-started,source_root=str(root),runtime=dict(python=__import__('sys').version,platform=__import__('platform').platform()))
    db.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT)')
    db.execute('INSERT INTO metadata VALUES(?,?)', ('result',json.dumps(result)))
    db.commit()
    db.close()
    result['manifest_sha256'] = sha((out/'closure.sqlite').read_bytes())
    atomic_json(out/'result.json',result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
