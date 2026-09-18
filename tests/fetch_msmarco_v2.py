#!/usr/bin/env python3
import gzip,hashlib,io,json,sys,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reranking'))
import fetch_msmarco_v2 as f

class Tests(unittest.TestCase):
    def test_range_stream_preserves_bytes_and_cleans_temp(self):
        raw=b'0123456789abcdefghijklmnopqrstuvwxyz'
        class Response(io.BytesIO):pass
        def open_request(request,timeout):
            if request.get_method()=='HEAD':
                r=Response(b'');r.headers={'Content-Length':str(len(raw)),'ETag':'pinned'};return r
            a,b=map(int,request.get_header('Range').split('=')[1].split('-'))
            self.assertEqual(request.get_header('If-match'),'pinned')
            r=Response(raw[a:b+1]);r.status=206;r.headers={'Content-Range':f'bytes {a}-{b}/{len(raw)}'};return r
        with tempfile.TemporaryDirectory() as tmp,patch.object(f.urllib.request,'urlopen',side_effect=open_request):
            p=Path(tmp)
            with f.RangeStream(p,workers=2,chunk=7) as stream:
                output=b''
                while piece:=stream.read(5):output+=piece
            self.assertEqual(output,raw);self.assertFalse(list(p.iterdir()))

    def test_extraction_verifies_ids_and_archive_checksum(self):
        record={'docid':'msmarco_doc_0_0','title':'t','headings':'h','body':'complete body and tail'}
        raw=(json.dumps(record)+'\n').encode();compressed=gzip.compress(raw)
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as tar:
            info=tarfile.TarInfo('msmarco_v2_doc/msmarco_doc_0.gz');info.size=len(compressed);tar.addfile(info,io.BytesIO(compressed))
        payload=archive.getvalue()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'qrels.txt').write_text('1 Q0 irrelevant-id 1\n')
            with gzip.open(p/'candidates.gz','wt') as out:out.write('1 Q0 msmarco_doc_0_0 1 1 run\n')
            with patch.object(f,'RangeStream',side_effect=lambda _:io.BytesIO(payload)),patch.object(f,'EXPECTED_MD5',hashlib.md5(payload).hexdigest()):f.extract(p)
            self.assertEqual((p/'documents/msmarco_doc_0_0.json').read_bytes(),raw)
            manifest=json.loads((p/'extraction.json').read_text());self.assertEqual(manifest['unique_documents'],1)
            self.assertEqual(manifest['archive_sha256'],hashlib.sha256(payload).hexdigest())

if __name__=='__main__':unittest.main()
