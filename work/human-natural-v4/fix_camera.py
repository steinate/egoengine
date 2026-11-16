"""Keep anatomical image-right continuous when looking through vertical."""
from arm_model import *
a=dict(np.load(OUT/'human-animation.npz'));C=a['camera_world_usd'].copy()
for i in range(N):
    z=C[i,:3,2];x=np.array([1.,0.,0.]);x=unit(x-z*np.dot(z,x));y=np.cross(z,x)
    C[i,:3,:3]=np.stack([x,y,z],axis=1)
steps=np.rad2deg(Rotation.from_matrix(np.swapaxes(C[:-1,:3,:3],1,2)@C[1:,:3,:3]).magnitude())
assert steps.max()<3.
a['camera_world_usd']=C;np.savez_compressed(OUT/'human-animation.npz',**a)
report={'max_camera_angular_step_deg':float(steps.max()),'image_right_world_x_min':float(C[:,0,0].min()),'camera_origin_unchanged':True,'method':'Project fixed anatomical right axis onto image plane, avoiding world-up singularity at downward view.'}
(OUT/'camera-continuity.json').write_text(json.dumps(report,indent=2));print(report,flush=True)
