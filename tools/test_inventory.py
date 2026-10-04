import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('inventory_closure', Path(__file__).with_name('inventory_closure.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SmallReads(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 3) if size >= 0 else 3)


class InventoryParserTests(unittest.TestCase):
    def parse(self, raw):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'receipt.json'
            path.write_bytes(raw)
            stream = module.Stream(path)
            stream.file.close()
            stream.file = SmallReads(raw)
            rows = list(stream.bindings())
            return rows, stream

    def test_incremental_unicode_and_full_digest(self):
        data = {'status':'ok','header':{'x':[1,2]},'checked_files':[{'file':'棋谱.json','sha256':'0'*64},{'file':'x','sha256':'1'*64}],'tail':12}
        raw = json.dumps(data, ensure_ascii=False).encode()
        rows, stream = self.parse(raw)
        self.assertEqual(rows, data['checked_files'])
        self.assertEqual(stream.count, 2)
        self.assertEqual(stream.digest, module.sha(raw))
        self.assertEqual(stream.metadata['tail'],12)

    def test_empty_array(self):
        rows, stream = self.parse(b'{"checked_files":[],"status":"ok"}')
        self.assertEqual(rows,[])
        self.assertEqual(stream.count,0)

    def test_missing_array_rejected(self):
        with self.assertRaises(ValueError):
            self.parse(b'{"status":"ok"}')

    def test_duplicate_root_key_rejected(self):
        with self.assertRaises(ValueError):
            self.parse(b'{"checked_files":[],"checked_files":[]}')

    def test_trailing_object_rejected(self):
        with self.assertRaises(ValueError):
            self.parse(b'{"checked_files":[]} {}')

    def test_truncated_array_rejected(self):
        with self.assertRaises(ValueError):
            self.parse(b'{"checked_files":[{"file":"x"}')


if __name__ == '__main__':
    unittest.main()
