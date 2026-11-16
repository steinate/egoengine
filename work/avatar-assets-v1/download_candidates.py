from pathlib import Path
import urllib.request,hashlib,json,zipfile,time
B=Path('/vepfs/public/pengjiaqi/interndata-human-pair/avatar-assets-v1');(B/'downloads').mkdir(exist_ok=True,parents=True)
u='https://renderpeople.com/sample/free/renderpeople_free_rigged_people_FBX.zip';p=B/'downloads/renderpeople_free_rigged_people_FBX.zip'
if not p.exists():
 with urllib.request.urlopen(u,timeout=90) as r,open(str(p)+'.part','wb') as f:
  while True:
   b=r.read(4*1024*1024)
   if not b:break
   f.write(b)
 Path(str(p)+'.part').rename(p)
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 dest=B/'assets/renderpeople';dest.mkdir(exist_ok=True,parents=True)
 for n in z.namelist():
  assert (dest/n).resolve().is_relative_to(dest.resolve())
 z.extractall(dest);print('FILES',z.namelist(),flush=True)
r={'url':u,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'purpose':'Asset file inspection and appearance preview only. Not approved for CV, dataset generation, or ML use under the standard/free terms.','terms_url':'https://renderpeople.com/general-terms-and-conditions/'}
(B/'renderpeople-download.json').write_text(json.dumps(r,indent=2));print('DOWNLOAD_DONE',r,flush=True)
