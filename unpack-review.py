"""Check numbered release volumes and extract a complete review directory."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

from review_transport import PartsReader, confined, digest


def unpack(metadata_path,destination):
    metadata_path=Path(metadata_path).resolve()
    config=json.loads(metadata_path.read_bytes())
    if config['status']!='COMPLETE_BYTE_PRESERVED_REVIEW_ARCHIVE':
        raise ValueError('incomplete archive')
    parts=[]
    h=hashlib.sha256()
    for row in config['volumes']:
        path=confined(metadata_path.parent,row['file'])
        if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:
            raise ValueError('missing or changed archive volume: '+row['file'])
        with path.open('rb') as f:
            for raw in iter(lambda:f.read(1024*1024),b''):h.update(raw)
        parts.append(path)
    if h.hexdigest()!=config['archive_sha256']:raise ValueError('archive digest mismatch')
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('destination must be new')
    destination.mkdir(parents=True)
    stream=PartsReader(parts)
    files=total=0
    try:
        with gzip.GzipFile(fileobj=stream,mode='rb') as decompressed:
            with tarfile.open(fileobj=decompressed,mode='r|') as archive:
                for member in archive:
                    if not member.isfile():raise ValueError('only regular files are shipped')
                    target=confined(destination,member.name)
                    if target.exists():raise ValueError('duplicate archive path')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    remaining=member.size
                    with archive.extractfile(member) as source,target.open('xb') as output:
                        while remaining:
                            raw=source.read(min(1024*1024,remaining))
                            if not raw:raise ValueError('truncated archive member')
                            output.write(raw);remaining-=len(raw)
                    files+=1;total+=member.size
    finally:stream.close()
    if files!=config['archive_files'] or total!=config['archive_payload_bytes']:
        raise ValueError('archive totals differ')
    print(json.dumps({'status':'EXTRACTED_COMPLETE_REVIEW_DIRECTORY','files':files,'bytes':total,'directory':str(destination)}))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest',type=Path)
    ap.add_argument('--destination',type=Path,required=True)
    args=ap.parse_args()
    unpack(args.manifest,args.destination)


if __name__=='__main__':main()
