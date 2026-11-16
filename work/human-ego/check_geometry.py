from pathlib import Path
import json,sys
import numpy as np
from scipy.spatial import cKDTree,ConvexHull
sys.path.insert(0,str(Path(__file__).resolve().parent))
import make_human as model
root=Path(__file__).resolve().parent
if not (root/'human-animation.npz').exists() and (root.parent/'human-animation.npz').exists():root=root.parent
h=np.load(root/'human-animation.npz');d=np.load(root/'world-tracks.npz')
report={'frames':844,'all_arrays_finite':all(np.isfinite(h[k]).all() for k in h.files),'arms':{},'grasp_checks':{},'limitations':'Template fit, not physical human simulation. Penetration statistic tests control vertices against object convex hull; it is not an exact triangle-mesh intersection or subdivided-render mesh certificate.'}
for side,start,end in [('left',146,290),('right',457,614)]:
 arm=h[side+'_arm'];lens=np.linalg.norm(np.diff(arm,axis=1),axis=2)
 report['arms'][side]={'upper_length_minmax_m':[float(lens[:,0].min()),float(lens[:,0].max())],'fore_length_minmax_m':[float(lens[:,1].min()),float(lens[:,1].max())],'max_wrist_frame_displacement_m':float(np.linalg.norm(np.diff(h[side+'_wrist_T'][:,:3,3],axis=0),axis=1).max())}
 name='pick_object_'+side+'1';ov=d[name+'_mesh_vertices'];T=d[name+'_world'];tree=cKDTree(ov);hull=ConvexHull(ov);eq=hull.equations
 frame=start+10;v=(h[side+'_vertices'][frame]-T[frame,:3,3])@T[frame,:3,:3]
 signed=(v@eq[:,:3].T+eq[:,3]).max(1)
 contact=[float(tree.query(v[ids],k=1)[0].min()) for ids in model.tips]
 rel=np.linalg.inv(T[start:end+1])@h[side+'_wrist_T'][start:end+1]
 report['grasp_checks'][side]={'frame':frame,'min_fingertip_vertex_to_object_vertex_distances_m':contact,'max_control_vertex_convex_hull_penetration_m':float(max(0,-signed.min())),'locked_wrist_relative_translation_drift_m':float(np.linalg.norm(rel[:,:3,3]-rel[0,:3,3],axis=1).max())}
(root/'geometry-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
