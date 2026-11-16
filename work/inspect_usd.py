from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'multi_gpu':False})
from pxr import Usd,UsdGeom
root='/vepfs/public/pengjiaqi/interndata-human-pair'
for file in [root+'/outputs/task-diagnostics/initial-scene.usdc',root+'/assets/InternDataAssets/assets/pick_and_place/pre-train-pick/assets/omniobject3d-bottle/google_scan-bottle_0011/Aligned_obj.usd']:
    s=Usd.Stage.Open(file)
    print('FILE',file,flush=True)
    for p in s.Traverse():
        path=str(p.GetPath())
        if (file.endswith('initial-scene.usdc') and path.startswith('/World/task_0/pick_object_left')) or (not file.endswith('initial-scene.usdc') and len(path.split('/'))<4):
            if UsdGeom.Xformable(p):
                print('XFORM',path,[(a.GetName(),str(a.Get())) for a in p.GetAttributes() if a.GetName().startswith('xform')],flush=True)
app.close()
