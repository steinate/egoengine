"""Select official assets required by the unchanged task's distractor sampler."""
import json,os,urllib.request,urllib.parse,concurrent.futures
from pathlib import Path
root=Path('/vepfs/public/pengjiaqi/interndata-human-pair')
token=os.environ.get('HF_TOKEN') or os.environ.get('HUGGING_FACE_HUB_TOKEN')
if not token:
    for p in [Path.home()/'.cache/huggingface/token',Path('/vepfs/public/pengjiaqi/cache/huggingface/token'),Path('/vepfs/public/pengjiaqi/data/hf_cache/token')]:
        if p.is_file():token=p.read_text().strip();break
headers={'Authorization':'Bearer '+token} if token else {}
prefix='InternDataAssets/assets/pick_and_place/pre-train-pick/assets'
def listing(path,recursive=False):
    url='https://huggingface.co/api/datasets/InternRobotics/InternData-A1/tree/main/'+urllib.parse.quote(path,safe='/')+'?limit=1000&recursive='+str(recursive).lower()
    result=[]
    while url:
        with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=60) as r:
            result.extend(json.load(r));link=r.headers.get('Link','')
        url=link.split('>')[0].lstrip('<') if 'rel="next"' in link else None
    return result
categories=[x['path'] for x in listing(prefix) if x['type']=='directory' and not any(k in x['path'].split('/')[-1] for k in ['bottle','shoe','book','hair_dryer','box','cube','whistle','discarded','ball'])]
chosen=[]
for cat in categories:
    objects=[x['path'] for x in listing(cat) if x['type']=='directory' and '/.' not in x['path']]
    chosen+=objects[:2]
    if len(chosen)>=10:break
chosen=chosen[:10]
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    groups=list(pool.map(lambda p:listing(p,True),chosen))
files=[x for group in groups for x in group if x['type']=='file' and '/.' not in x['path']]
(root/'assets/official-distractor-manifest.json').write_text(json.dumps(files,indent=2))
print(json.dumps({'objects':chosen,'files':len(files),'bytes':sum(x['size'] for x in files)}),flush=True)
def fetch(item):
    dst=root/'assets'/item['path'];dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.is_file() and dst.stat().st_size==item['size']:return
    url='https://huggingface.co/datasets/InternRobotics/InternData-A1/resolve/main/'+urllib.parse.quote(item['path'],safe='/')
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=120) as r,dst.with_suffix(dst.suffix+'.partial').open('wb') as f:
        while data:=r.read(1024*1024):f.write(data)
    tmp=dst.with_suffix(dst.suffix+'.partial');assert tmp.stat().st_size==item['size'];tmp.replace(dst)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    for i,_ in enumerate(pool.map(fetch,files),1):
        if i%10==0:print('Downloaded',i,'/',len(files),flush=True)
print('OFFICIAL_DISTRACTORS_READY',flush=True)
