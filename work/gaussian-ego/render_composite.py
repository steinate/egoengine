"""GHOST headless rendering with per-surfel scene depth clipping."""
from ghost_adapter import *
import argparse,json,imageio.v2 as iio
p=argparse.ArgumentParser();p.add_argument('--preview',action='store_true');p.add_argument('--frames',default='0,30,60,90');args=p.parse_args()
out=HERE/'output';motion=dict(np.load(out/'motion.npz'));cfg=json.loads((out/'camera.json').read_text())
if not args.preview:
 scene_check=json.loads((out/'scene-check.json').read_text())
 if scene_check['frames']!=len(motion['source_frames']):
  raise RuntimeError('Scene cache contains a preview or mixed camera generations. Full coherent scene render required before encoding.')
cam=camera(np.array(cfg['T_world_camera_opencv']),np.array(cfg['K']),cfg['width'],cfg['height'])
g=avatar();g.active_sh_degree=3 # All stored SH coefficients evaluated in canonical face frames by adapter.
with torch.no_grad():g.update_mesh_properties(torch.tensor(motion['vertices'][30][None],device='cuda',dtype=torch.float32),g.canonical_verts[None])
baseline=capture(g,cam)
far=capture(g,cam,np.full((cfg['height'],cfg['width']),100.,dtype=np.float32))
near=capture(g,cam,np.zeros((cfg['height'],cfg['width']),dtype=np.float32))
depth_check={'unoccluded_max_rgb_error':float((baseline['render']-far['render']).abs().max()),'fully_occluded_max_alpha':float(near['rend_alpha'].abs().max()),'visible_hand_max_alpha':float(baseline['rend_alpha'].max())}
assert depth_check['unoccluded_max_rgb_error']<1e-5 and depth_check['fully_occluded_max_alpha']==0 and depth_check['visible_hand_max_alpha']>.5,depth_check
(out/'depth-clip-check.json').write_text(json.dumps(depth_check,indent=2));print('DEPTH_CLIP_OK',depth_check,flush=True)
ids=[int(x) for x in args.frames.split(',')] if args.preview else range(len(motion['source_frames']))
writer=None if args.preview else iio.get_writer(out/'gaussian-human-ego.mp4',fps=15,codec='libx264',quality=8,macro_block_size=1)
for k in ids:
 verts=torch.tensor(motion['vertices'][k][None],device='cuda',dtype=torch.float32)
 with torch.no_grad():g.update_mesh_properties(verts,g.canonical_verts[None])
 scene=iio.imread(out/'scene'/f'{k:04d}.png')/255.
 z=np.load(out/'scene'/f'{k:04d}-depth.npy')
 result=capture(g,cam,z)
 rgb=result['render'].cpu().numpy().transpose(1,2,0)
 alpha=result['rend_alpha'].cpu().numpy().transpose(1,2,0)
 combined=np.uint8(np.clip(rgb+(1-alpha)*scene,0,1)*255)
 if writer:writer.append_data(combined)
 if k in [0,15,30,45,60,75,90]:
  iio.imwrite(out/f'ego-{k:04d}.png',combined)
  iio.imwrite(out/f'hand-{k:04d}.png',np.uint8(np.clip(rgb+(1-alpha)*.7,0,1)*255))
 if k%15==0:print('GAUSSIAN_FRAME',k,flush=True)
if writer:writer.close()
report={'frames':len(ids),'source_frames':motion['source_frames'].tolist(),'fps':15,'width':cfg['width'],'height':cfg['height'],'avatar':'GHOST public data/point_cloud.ply','gaussians':len(g.get_xyz),'renderer':'GHOST diff-surfel-rasterization; inference-only per-surfel scene-depth clipping extension','mano_driver':'manopth and GHOST GaussianModelManoHybrid.update_mesh_properties','scene':'Isaac Sim 4.1; official object trajectories','appearance':'pretrained SH degree 3; view directions transported into canonical per-face frame','preview':args.preview}
(out/('preview-check.json' if args.preview else 'verification.json')).write_text(json.dumps(report,indent=2));print('GAUSSIAN_DONE',flush=True)
