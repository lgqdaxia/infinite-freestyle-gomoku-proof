"""Transport helpers. Mathematical decisions belong to the frozen checkers."""
import hashlib
from pathlib import Path, PurePosixPath
import json


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for raw in iter(lambda:f.read(1024*1024),b''):
            h.update(raw)
    return h.hexdigest()


def relative_name(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name:
        raise ValueError('invalid archive path')
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or p.as_posix() != name:
        raise ValueError('noncanonical relative path')
    return name


def confined(root,name):
    name=relative_name(name)
    p=(Path(root)/name).resolve()
    p.relative_to(Path(root).resolve())
    return p


def manifest_rows(path):
    with Path(path).open(encoding='utf8') as f:
        for line in f:
            row=json.loads(line)
            relative_name(row['file'])
            if type(row['bytes']) is not int or row['bytes'] < 0:
                raise ValueError('invalid payload size')
            sha=row['sha256']
            if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
                raise ValueError('invalid digest')
            yield row


class PartsReader:
    """A sequential read-only view of numbered compressed volumes."""
    def __init__(self, paths):
        self.paths=iter(paths)
        self.current=None

    def read(self,size=-1):
        if size < 0:
            chunks=[]
            while raw:=self.read(1024*1024):chunks.append(raw)
            return b''.join(chunks)
        chunks=[]
        remaining=size
        while remaining:
            if self.current is None:
                try:self.current=Path(next(self.paths)).open('rb')
                except StopIteration:break
            raw=self.current.read(remaining)
            if not raw:
                self.current.close();self.current=None
                continue
            chunks.append(raw);remaining-=len(raw)
        return b''.join(chunks)

    def close(self):
        if self.current is not None:self.current.close();self.current=None

