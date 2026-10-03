"""Bounded-memory JSON receipt reading; no mathematical acceptance decisions."""
import codecs
import hashlib
import json
from pathlib import Path


class Stream:
    def __init__(self,path):
        self.file = Path(path).open('rb')
        self.hash = hashlib.sha256()
        self.utf8 = codecs.getincrementaldecoder('utf-8')()
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
        self.buffer += self.utf8.decode(raw,final=self.eof)

    def ws(self):
        while True:
            while self.offset < len(self.buffer) and self.buffer[self.offset].isspace():
                self.offset += 1
            if self.offset < len(self.buffer) or self.eof:
                return
            self.more()

    def token(self,value):
        self.ws()
        if self.buffer[self.offset:self.offset+1] != value:
            raise ValueError('malformed receipt token')
        self.offset += 1

    def value(self):
        self.ws()
        while True:
            try:
                result,end = self.json.raw_decode(self.buffer,self.offset)
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self.more()
                continue
            # raw_decode may accept a numeric prefix before the next chunk.
            # A following delimiter (or actual EOF) is required before accepting.
            if end == len(self.buffer) and not self.eof:
                self.more()
                continue
            if end < len(self.buffer) and self.buffer[end] not in ' \t\r\n,:]}':
                if type(result) in (int,float) and self.buffer[end] in '.eE+-' and not self.eof:
                    self.more()
                    continue
                raise ValueError('invalid JSON value boundary')
            self.offset = end
            return result

    def bindings(self):
        self.token('{')
        keys = set()
        metadata = {}
        count = 0
        while True:
            key = self.value()
            if not isinstance(key,str) or key in keys:
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
        if not self.eof or self.offset != len(self.buffer) or 'checked_files' not in keys:
            raise ValueError('trailing or missing receipt data')
        self.metadata,self.count,self.digest = metadata,count,self.hash.hexdigest()
        self.file.close()


def metadata(path):
    stream = Stream(path)
    try:
        for _ in stream.bindings():
            pass
        return stream.metadata,stream.digest,stream.count
    finally:
        stream.file.close()
