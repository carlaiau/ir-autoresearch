#!/usr/bin/env python3
"""Stream the official v2 archive and retain only frozen DL2021 candidates."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import shutil
import tempfile
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
import time
import urllib.request

URL = 'https://msmarco.z22.web.core.windows.net/msmarcoranking/msmarco_v2_doc.tar'
EXPECTED_MD5 = 'eea90100409a254fdb157b8e4e349deb'


class RangeStream:
    """Read archive bytes in order with bounded parallel HTTP prefetch on disk."""
    def __init__(self, data, workers=8, chunk=128*1024*1024):
        self.chunk=chunk; self.workers=workers; self.index=0; self.current=None
        req=urllib.request.Request(URL,method='HEAD')
        with urllib.request.urlopen(req,timeout=120) as response:
            self.length=int(response.headers['Content-Length']); self.etag=response.headers['ETag']
        self.count=(self.length+chunk-1)//chunk
        self.temp=Path(tempfile.mkdtemp(prefix='range-',dir=data))
        self.pool=ThreadPoolExecutor(max_workers=workers);self.futures={}
        for i in range(min(workers,self.count)):self.futures[i]=self.pool.submit(self.download,i)
    def download(self,i):
        start=i*self.chunk; end=min(self.length,start+self.chunk)-1
        path=self.temp/str(i)
        for attempt in range(3):
            try:
                req=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{end}','If-Match':self.etag})
                with urllib.request.urlopen(req,timeout=120) as response,path.open('wb') as out:
                    if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{self.length}':raise ValueError('range response mismatch')
                    shutil.copyfileobj(response,out,length=1024*1024)
                if path.stat().st_size!=end-start+1:raise ValueError('short range response')
                return path
            except Exception:
                if attempt==2:raise
                time.sleep(2**attempt)
    def read(self,size=-1):
        if size<0:raise ValueError('bounded reads required')
        pieces=[]; remaining=size
        while remaining and self.index<self.count:
            if self.current is None:self.current=self.futures.pop(self.index).result().open('rb')
            part=self.current.read(remaining);pieces.append(part);remaining-=len(part)
            if not part:
                path=Path(self.current.name);self.current.close();self.current=None;path.unlink()
                upcoming=self.index+self.workers
                if upcoming<self.count:self.futures[upcoming]=self.pool.submit(self.download,upcoming)
                self.index+=1
        return b''.join(pieces)
    def __enter__(self):return self
    def __exit__(self,*args):
        if self.current:self.current.close()
        self.pool.shutdown(wait=True,cancel_futures=True)
        shutil.rmtree(self.temp)

class HashReader:
    def __init__(self, source):
        self.source=source; self.sha=hashlib.sha256(); self.md5=hashlib.md5(); self.count=0
    def read(self, size=-1):
        data=self.source.read(size); self.sha.update(data); self.md5.update(data); self.count+=len(data); return data


def extract(data):
    wanted_queries={line.split()[0] for line in (data/'qrels.txt').read_text().splitlines()}
    targets=defaultdict(dict)
    with gzip.open(data/'candidates.gz','rt') as stream:
        for line in stream:
            q,_,doc,rank,score,tag=line.split()
            if q not in wanted_queries:continue
            prefix,kind,bundle,offset=doc.split('_')
            if (prefix,kind)!=('msmarco','doc'):raise ValueError('invalid document ID')
            targets[f'msmarco_doc_{bundle}.gz'][int(offset)]=doc
    selected=data/'documents';selected.mkdir(exist_ok=True)
    started=time.perf_counter(); members=[]; found=set()
    with RangeStream(data) as response:
        hashed=HashReader(response)
        with tarfile.open(fileobj=hashed,mode='r|',bufsize=1024*1024) as archive:
            for member in archive:
                name=Path(member.name).name
                if name not in targets:continue
                if not member.isfile():raise ValueError('candidate member is not a file')
                compressed=HashReader(archive.extractfile(member))
                with gzip.GzipFile(fileobj=compressed) as stream:
                    for offset,doc in sorted(targets[name].items()):
                        stream.seek(offset)
                        raw=stream.readline(); record=json.loads(raw)
                        if record['docid']!=doc:raise ValueError('document offset/ID mismatch')
                        if any(not isinstance(record.get(k),str) for k in ('title','headings','body')):raise ValueError('document fields missing')
                        dest=selected/(doc+'.json')
                        if dest.exists() and dest.read_bytes()!=raw:raise ValueError('cached document differs')
                        dest.write_bytes(raw);found.add(doc)
                    # Consume remaining decompressed bytes to verify gzip CRC.
                    while stream.read(1024*1024):pass
                while compressed.read(1024*1024):pass
                members.append({'name':member.name,'compressed_bytes':member.size,'compressed_sha256':compressed.sha.hexdigest(),'selected_documents':len(targets[name])})
                status={'status':'running','members_complete':len(members),'selected_documents':len(found),'downloaded_bytes':hashed.count,'elapsed_seconds':time.perf_counter()-started}
                (data/'extraction-progress.json').write_text(json.dumps(status))
                print(json.dumps(status),flush=True)
        while hashed.read(1024*1024):pass
    expected={doc for bundle in targets.values() for doc in bundle.values()}
    if found!=expected:raise ValueError('incomplete candidate extraction')
    if hashed.md5.hexdigest()!=EXPECTED_MD5:raise ValueError('official archive MD5 mismatch')
    result={'status':'complete','source':URL,'archive_sha256':hashed.sha.hexdigest(),'archive_md5':hashed.md5.hexdigest(),
            'downloaded_bytes':hashed.count,'unique_documents':len(found),'members':members,'elapsed_seconds':time.perf_counter()-started,
            'document_file_sha256':{d:hashlib.sha256((selected/(d+'.json')).read_bytes()).hexdigest() for d in sorted(found)}}
    (data/'extraction.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Complete: '+str(len(found))+' original documents; archive checksum verified',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('data',type=Path);args=p.parse_args();extract(args.data)
