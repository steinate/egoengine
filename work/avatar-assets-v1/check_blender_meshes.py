import bpy,numpy as np,json
from pathlib import Path
B=Path('/vepfs/public/pengjiaqi/interndata-human-pair/avatar-assets-v1');bpy.ops.wm.open_mainfile(filepath=str(B/'usd/mpfb_cc0_adult_male-driven.blend'))
report=[];save={}
for i in [0,30,60]:
 bpy.context.scene.frame_set(i);dg=bpy.context.evaluated_depsgraph_get()
 for o in bpy.data.objects:
  if o.type!='MESH':continue
  e=o.evaluated_get(dg);m=e.to_mesh();v=np.array([list(o.matrix_world@p.co) for p in m.vertices]);key=f'{i}_{o.name}';save[key]=v
  if i==0:report.append({'object':o.name,'data':o.data.name,'vertices':len(v),'shape_keys':len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0,'modifiers':[(m.name,m.type) for m in o.modifiers],'bounds':[v.min(0).tolist(),v.max(0).tolist()]})
  e.to_mesh_clear()
np.savez_compressed(B/'blender-mesh-reference.npz',**save);(B/'blender-mesh-reference.json').write_text(json.dumps(report,indent=2));print('REFERENCE_READY',report,flush=True)
