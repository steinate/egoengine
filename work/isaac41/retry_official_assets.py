import concurrent.futures, json, os, time, urllib.request, urllib.parse
from pathlib import Path
base=Path('/vepfs/public/pengjiaqi/interndata-human-pair')
token=os.environ.get('HF_TOKEN') or os.environ.get('HUGGING_FACE_HUB_TOKEN')
if not token:
    for p in [Path.home()/'.cache/huggingface/token',Path('/vepfs/public/pengjiaqi/cache/huggingface/token'),Path('/vepfs/public/pengjiaqi/data/hf_cache/token')]:
        if p.is_file(): token=p.read_text().strip();break
headers={'Authorization':'Bearer '+token} if token else {}
files=json.loads((base/'assets/official-distractor-manifest.json').read_text())
def fetch(item):
    path=item['path']; dst=base/'assets'/path
    if dst.exists() and dst.stat().st_size==item['size']: return 'cached'
    dst.parent.mkdir(parents=True,exist_ok=True)
    url='https://huggingface.co/datasets/InternRobotics/InternData-A1/resolve/main/'+urllib.parse.quote(path,safe='/')+'?download=true'
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=90) as r,open(str(dst)+'.partial','wb') as f:
                while True:
                    chunk=r.read(1024*1024)
                    if not chunk:break
                    f.write(chunk)
            if Path(str(dst)+'.partial').stat().st_size!=item['size']: raise ValueError('size mismatch')
            os.replace(str(dst)+'.partial',dst)
            return 'downloaded'
        except Exception:
            if attempt==3:raise RuntimeError('Failed asset: '+path) from None
            time.sleep(2**attempt)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    futures={pool.submit(fetch,x):x for x in files}
    done=0;errors=[]
    for fut in concurrent.futures.as_completed(futures):
        try:fut.result()
        except Exception as e: errors.append(str(e));print(str(e),flush=True)
        done+=1
        if done%50==0:print(f'{done}/{len(files)} complete',flush=True)
summary={'files':len(files),'errors':errors,'bytes':sum(x['size'] for x in files)}
(base/'outputs/official-distractor-download.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary),flush=True)
raise SystemExit(bool(errors))
