"""Archive the sealed dependency closure with original bytes and paths."""
import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import tarfile
import time

from review_transport import digest, confined, manifest_rows, relative_name


class Volumes:
    def __init__(self,destination,limit=1536*1024*1024):
        self.destination=Path(destination)
        self.limit=limit
        self.current=None
        self.records=[]
        self.total_hash=hashlib.sha256()
        self.size=0

    def finish_part(self):
        if self.current is None:return
        self.current.close()
        self.records.append({'file':self.path.name,'bytes':self.size,'sha256':self.part_hash.hexdigest()})
        self.current=None

    def write(self,raw):
        self.total_hash.update(raw)
        offset=0
        while offset<len(raw):
            if self.current is None:
                self.path=self.destination/f'gomoku-full-review.tar.gz.{len(self.records)+1:03}'
                self.current=self.path.open('xb')
                self.part_hash=hashlib.sha256();self.size=0
            end=min(len(raw),offset+self.limit-self.size)
            chunk=raw[offset:end]
            self.current.write(chunk);self.part_hash.update(chunk)
            self.size+=len(chunk);offset=end
            if self.size==self.limit:self.finish_part()
        return len(raw)

    def close(self):self.finish_part()


class ParallelGzip:
    """Ordered standard gzip members; the output is an ordinary gzip stream."""
    def __init__(self,sink,workers,chunk=16*1024*1024,level=6):
        self.sink=sink;self.chunk=chunk;self.level=level
        self.pool=ThreadPoolExecutor(max_workers=workers)
        self.pending=deque();self.buffer=bytearray()
        self.limit=max(2,2*workers)

    def drain(self):self.sink.write(self.pending.popleft().result())

    def submit(self,raw):
        self.pending.append(self.pool.submit(gzip.compress,raw,compresslevel=self.level,mtime=0))
        if len(self.pending)>=self.limit:self.drain()

    def write(self,raw):
        self.buffer.extend(raw)
        while len(self.buffer)>=self.chunk:
            self.submit(bytes(self.buffer[:self.chunk]));del self.buffer[:self.chunk]
        return len(raw)

    def close(self):
        if self.buffer:self.submit(bytes(self.buffer));self.buffer.clear()
        while self.pending:self.drain()
        self.pool.shutdown();self.sink.close()


class BoundReader:
    def __init__(self,path,size,sha):
        self.file=Path(path).open('rb');self.expected_size=size;self.expected_sha=sha
        self.size=0;self.hash=hashlib.sha256()
        if Path(path).stat().st_size!=size:raise ValueError('source size changed')

    def read(self,size):
        raw=self.file.read(size);self.size+=len(raw);self.hash.update(raw)
        return raw

    def close(self):
        self.file.close()
        if self.size!=self.expected_size or self.hash.hexdigest()!=self.expected_sha:
            raise ValueError('source bytes differ from sealed inventory')


def write_json(path,value):
    path=Path(path)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8',newline='\n')


def bound_prefetch(root,rows,workers,window=16,maximum=8*1024*1024):
    """Bound memory while overlapping small-file reads; retain input order."""
    def load(row):
        if row['bytes']>maximum:return None
        raw=(root/relative_name(row['file'])).read_bytes()
        if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('source bytes differ from sealed inventory')
        return raw
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending=deque()
        for row in rows:
            pending.append((row,pool.submit(load,row)))
            if len(pending)>=window:
                first,future=pending.popleft()
                yield first,future.result()
        while pending:
            first,future=pending.popleft()
            yield first,future.result()


def make_manifest(inventory,root,package):
    info=json.loads((inventory/'result.json').read_bytes())
    if info['status']!='COMPLETE_RECEIPT_BOUND_INVENTORY_NOT_MATHEMATICAL_RECHECK':
        raise ValueError('completed inventory required')
    if digest(inventory/'closure.sqlite')!=info['manifest_sha256']:
        raise ValueError('inventory bytes changed')
    db=sqlite3.connect((inventory/'closure.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    total=size=0
    manifest=package/'proof-manifest.jsonl'
    cover='artifacts/empty-board-proof-20261002/empty-cover.json'
    with manifest.open('w',encoding='utf8',newline='\n') as out:
        path=confined(root,cover)
        if digest(path)!=info['cover_sha256']:raise ValueError('cover changed')
        row={'file':cover,'bytes':path.stat().st_size,'sha256':info['cover_sha256'],'role':'cover'}
        out.write(json.dumps(row,separators=(',',':'))+'\n');total+=1;size+=row['bytes']
        for name,sha,number,format_name in db.execute('SELECT relative_path,sha256,bytes,format FROM files ORDER BY relative_path'):
            role={'freestyle-gomoku-infinite-dynamic-gap':'ordinary','freestyle-gomoku-infinite-gap-bundle':'bundle'}[format_name]
            row={'file':name,'sha256':sha,'bytes':number,'role':role}
            relative_name(name)
            out.write(json.dumps(row,separators=(',',':'))+'\n')
            total+=1;size+=number
    db.close()
    if total!=info['distinct_paths']+1:raise ValueError('omitted dependencies')
    return info,dict(proof_files=total,proof_payload_bytes=size,proof_manifest_sha256=digest(manifest),
        cover=cover,cover_sha256=info['cover_sha256'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-root',type=Path,required=True)
    ap.add_argument('--inventory',type=Path,required=True)
    ap.add_argument('--destination',type=Path,required=True)
    ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args()
    if args.workers<1:raise ValueError('positive workers required')
    root=args.source_root.resolve();destination=args.destination.resolve()
    if destination.exists():raise ValueError('archive destination must be new')
    destination.mkdir(parents=True)
    package=destination/'bootstrap';package.mkdir()
    started=time.monotonic()
    own=Path(__file__).resolve().parent
    def progress(item):
        write_json(destination/'progress.json',dict(item,seconds=time.monotonic()-started))
    progress({'phase':'PREPARING_MANIFEST'})
    info,release=make_manifest(args.inventory.resolve(),root,package)
    seal=json.loads((root/'artifacts/empty-board-proof-20261002/final-byte-seal-04.json').read_bytes())
    if digest(root/'artifacts/empty-board-proof-20261002/final-byte-seal-04.json')!=info['seal_sha256']:
        raise ValueError('sealed source record changed')
    for name,sha in seal['checker_sha256'].items():
        path=confined(root,name)
        if digest(path)!=sha:raise ValueError('mathematical checker changed')
        target=package/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
    for name in ('verify-full-review.py','review_transport.py','unpack-review.py','README.txt','LICENSES.txt','LICENSE-CODE.txt'):
        shutil.copyfile(own/name,package/name)
    shutil.copyfile(root/'research/revision-review-20261003/review-package/receipt_stream.py',package/'receipt_stream.py')
    for name in ('rule-use-counts.csv','certificate-census.json','opening-run-statistics.csv'):
        shutil.copyfile(root/'research/revision-review-20261003'/name,package/name)
    census_path=package/'certificate-census.json'
    census=json.loads(census_path.read_bytes())
    for key in ('full_isolated_replay_completed','full_portable_release_delivered','compressed_release_bytes'):
        census.pop(key,None)
    write_json(census_path,census)
    for name,source in (
        ('recorded-mathematical-result.json',root/'artifacts/empty-board-proof-20261002/fresh-reference-02/result.json'),
        ('recorded-final-byte-seal.json',root/'artifacts/empty-board-proof-20261002/final-byte-seal-04.json')):
        shutil.copyfile(source,package/name)
    release.update(format='gomoku-byte-preserved-full-review',version=1,scope='empty_board',
        max_total_plies=35,opening_roots=20,canonical_first_replies=120,
        original_seal_sha256=info['seal_sha256'],checker_sha256=seal['checker_sha256'],
        statement='Complete original certificate bytes and relative filenames, with the frozen mathematical checker',
        data_license='CC-BY-4.0',code_license='MIT',author='Gaoqiang Liu')
    write_json(package/'review-release.json',release)
    bootstrap_files=sorted(p for p in package.rglob('*') if p.is_file())
    # Metadata is shipped first, then every selected original proof exactly once.
    volumes=Volumes(destination)
    compressed=ParallelGzip(volumes,args.workers)
    archive=tarfile.open(fileobj=compressed,mode='w|',format=tarfile.PAX_FORMAT,bufsize=1024*1024)
    files=payload=0
    try:
        def add(name,path,size,sha,raw=None):
            nonlocal files,payload
            header=tarfile.TarInfo(name);header.size=size;header.mtime=0
            header.mode=0o644;header.uid=header.gid=0;header.uname=header.gname=''
            reader=BoundReader(path,size,sha) if raw is None else io.BytesIO(raw)
            try:archive.addfile(header,reader)
            finally:reader.close()
            files+=1;payload+=size
        for path in bootstrap_files:
            add(path.relative_to(package).as_posix(),path,path.stat().st_size,digest(path))
        count=0
        for row,raw in bound_prefetch(root,manifest_rows(package/'proof-manifest.jsonl'),args.workers):
            add(row['file'],root/relative_name(row['file']),row['bytes'],row['sha256'],raw)
            count+=1
            if count%1000==0:
                progress({'phase':'ARCHIVING_BOUND_PROOF_BYTES','proof_files':count,'total_proof_files':release['proof_files'],
                    'input_bytes':payload,'closed_volumes':len(volumes.records)})
        if count!=release['proof_files']:raise ValueError('missing archive entries')
        archive.close();compressed.close()
    except BaseException:
        compressed.pool.shutdown(wait=True,cancel_futures=True)
        if volumes.current is not None:volumes.current.close()
        progress({'phase':'FAILED_INCOMPLETE_ARCHIVE','proof_files':count if 'count' in locals() else 0})
        raise
    record=dict(status='COMPLETE_BYTE_PRESERVED_REVIEW_ARCHIVE',version=1,archive_files=files,
        archive_payload_bytes=payload,proof_files=release['proof_files'],proof_payload_bytes=release['proof_payload_bytes'],
        proof_manifest_sha256=release['proof_manifest_sha256'],cover_sha256=release['cover_sha256'],
        checker_sha256=seal['checker_sha256'],archive_sha256=volumes.total_hash.hexdigest(),
        compressed_bytes=sum(r['bytes'] for r in volumes.records),volumes=volumes.records,
        original_bytes_and_paths_preserved=True,seconds=time.monotonic()-started,
        code_license='MIT',data_license='CC-BY-4.0')
    write_json(destination/'archive-manifest.json',record)
    (destination/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in volumes.records),encoding='ascii',newline='\n')
    progress({'phase':'COMPLETE_BYTE_PRESERVED_REVIEW_ARCHIVE','proof_files':count,'compressed_bytes':record['compressed_bytes']})
    print(json.dumps(record))


if __name__=='__main__':main()
