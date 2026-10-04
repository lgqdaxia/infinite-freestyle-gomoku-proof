"""Focused regressions for archive integrity and traversal protection."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile

from build_archive import ParallelGzip,Volumes,BoundReader,bound_prefetch
from review_transport import PartsReader,confined,relative_name,digest
from importlib.machinery import SourceFileLoader

unpack=SourceFileLoader('unpack_review',str(Path(__file__).with_name('unpack-review.py'))).load_module().unpack


def test():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);out=root/'volumes';out.mkdir()
        expected=(b'Gomoku '*3100)+bytes(range(256))*21
        sink=Volumes(out,limit=317)
        compressor=ParallelGzip(sink,workers=2,chunk=211,level=1)
        archive=tarfile.open(fileobj=compressor,mode='w|',format=tarfile.PAX_FORMAT)
        name='artifacts/'+('long-path/'*30)+'example.json'
        info=tarfile.TarInfo(name);info.size=len(expected)
        archive.addfile(info,io.BytesIO(expected));archive.close();compressor.close()
        config={'status':'COMPLETE_BYTE_PRESERVED_REVIEW_ARCHIVE','volumes':sink.records,
            'archive_sha256':sink.total_hash.hexdigest(),'archive_files':1,'archive_payload_bytes':len(expected)}
        metadata=out/'archive-manifest.json';metadata.write_text(json.dumps(config))
        unpack(metadata,root/'extracted')
        assert (root/'extracted'/name).read_bytes()==expected
        concatenated=PartsReader([out/r['file'] for r in sink.records])
        try:raw=concatenated.read()
        finally:concatenated.close()
        assert gzip.decompress(raw).endswith(b'\0'*1024)
        assert hashlib.sha256(raw).hexdigest()==config['archive_sha256']
        original=root/'proof';original.write_bytes(expected)
        reader=BoundReader(original,len(expected),digest(original))
        while reader.read(29):pass
        reader.close()
        bad=BoundReader(original,len(expected),'0'*64)
        while bad.read(77):pass
        try:bad.close()
        except ValueError:pass
        else:raise AssertionError('changed source accepted')
        rows=[{'file':'proof','bytes':len(expected),'sha256':digest(original)}]*19
        loaded=list(bound_prefetch(root,rows,workers=4,window=8))
        assert [row for row,raw in loaded]==rows and all(raw==expected for row,raw in loaded)
        assert list(bound_prefetch(root,rows[:1],workers=1,maximum=1))[0][1] is None
        try:list(bound_prefetch(root,[dict(rows[0],sha256='0'*64)],workers=2))
        except ValueError:pass
        else:raise AssertionError('prefetch accepted changed source')
        for name in ('../escape','C:/escape','/escape','a\\b','a/../b'):
            try:relative_name(name)
            except ValueError:pass
            else:raise AssertionError('unsafe path accepted')
        damaged=out/config['volumes'][0]['file'];damaged.write_bytes(b'corrupt')
        try:unpack(metadata,root/'must-not-extract')
        except ValueError:pass
        else:raise AssertionError('corrupted archive accepted')
        assert not (root/'must-not-extract').exists()
    print('PASSED: ordered gzip members, numbered volumes, exact extraction, source/volume digests, path traversal rejection')


if __name__=='__main__':test()
