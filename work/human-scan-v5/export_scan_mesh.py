import bpy, numpy as np, json
from pathlib import Path
B=Path('/vepfs/public/pengjiaqi/interndata-human-pair/human-scan-v5')
bpy.ops.wm.open_mainfile(filepath=str(B/'scan-reduced.blend'))
o=next(o for o in bpy.data.objects if o.type=='MESH');m=o.data
v=np.array([list(x.co) for x in m.vertices]);m.calc_loop_triangles()
faces=np.array([list(t.vertices) for t in m.loop_triangles]);loops=np.array([list(t.loops) for t in m.loop_triangles]);uv=np.array([list(x.uv) for x in m.uv_layers.active.data])
# Keep the hand and a cuff overlap. The existing clothed full body remains continuous.
keep=(v[faces,2].min(1)>28.5);faces=faces[keep];loops=loops[keep];used=np.unique(faces);mapping=np.full(len(v),-1);mapping[used]=np.arange(len(used));faces=mapping[faces]
np.savez_compressed(B/'scan-mesh.npz',points_cm=v[used],faces=faces,uv=uv[loops])
print('CROPPED_SCAN',len(used),len(faces),flush=True)
