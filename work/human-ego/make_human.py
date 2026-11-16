"""Deterministic contact-template animation using ManipNet's released hand mesh.
This does not run ManipNet's neural network, GrabNet, or MANO.
"""
from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from scipy.optimize import least_squares
from scipy.ndimage import gaussian_filter1d

HERE=Path(__file__).resolve().parent
if not (HERE/'hand-rig.npz').exists() and (HERE.parent/'hand-rig.npz').exists():HERE=HERE.parent
raw=np.load(HERE/'hand-rig.npz')
C=np.array([[0,0,-1],[1,0,0],[0,1,0.]])
V=raw['vertices']@C.T
G=np.linalg.inv(raw['bind']);J=(G[:,:3,3]*.085)@C.T
W=raw['weights'];BI=raw['indices'].astype(int)
F=raw['faces'][:,::-1]
P=np.array([-1,-1,0,2,3,0,5,6,0,8,9,0,11,12,0,14,15])
tips=[]
for b in [4,7,10,13,16]:
 direction=J[b]-J[P[b]];direction/=np.linalg.norm(direction)
 score=V@direction
 candidates=np.flatnonzero(np.sum(W*(BI==b),axis=1)>.6)
 tips.append(candidates[np.argsort(score[candidates])[-8:]])

def hand(q,skin=True,details=False):
 # Thumb: three local corrections. Fingers: flexion at MCP/PIP/DIP.
 rr=np.zeros((17,3));rr[2:5]=np.asarray(q[:9]).reshape(3,3)
 for j,b in enumerate([5,8,11,14]):rr[b:b+3,0]=-np.asarray(q[9+3*j:12+3*j])
 A=np.tile(np.eye(3),(17,1,1));pos=J.copy()
 for b in range(2,17):
  pa=P[b];pos[b]=pos[pa]+A[pa]@(J[b]-J[pa]);A[b]=A[pa]@Rotation.from_rotvec(rr[b]).as_matrix()
 if not skin:return pos
 shift=pos-np.einsum('bij,bj->bi',A,J)
 v=np.sum(W[:,:,None]*(np.einsum('vkij,vj->vki',A[BI],V)+shift[BI]),axis=1)
 return (v,pos,A) if details else (v,pos)

NAIL_V=[];NAIL_B=[];NAIL_F=[]
for finger,b in enumerate([4,7,10,13,16]):
 direction=J[b]-J[P[b]];direction/=np.linalg.norm(direction)
 normal=np.array([0.,0.,1.]);normal-=direction*np.dot(normal,direction);normal/=np.linalg.norm(normal)
 lateral=np.cross(direction,normal)
 center=V[tips[finger]].mean(0)-direction*.006+normal*.005
 start=len(NAIL_V);NAIL_V.append(center+normal*.0009);NAIL_B.append(b)
 for angle in np.linspace(0,2*np.pi,20,endpoint=False):
  NAIL_V.append(center+np.cos(angle)*lateral*.0043+np.sin(angle)*direction*.0062);NAIL_B.append(b)
 for k in range(20):NAIL_F.append([start,start+1+k,start+1+(k+1)%20])
NAIL_V=np.array(NAIL_V);NAIL_B=np.array(NAIL_B);NAIL_F=np.array(NAIL_F)

def fit_cube():
 q=np.r_[np.zeros(9),np.tile([.2,1.1,.3],4)]
 x0=np.r_[q,[0,-.111,.054]]
 target=np.array([[-.016,-.031,.0],[-.02,.031,.002],[0,.031,.002],[.023,.031,.004],[.036,.012,.005]])
 def residual(x):
  v,_=hand(x[:21]);v+=x[21:24]
  contacts=np.stack([v[t].mean(0) for t in tips])
  # Smooth box penalty; use the actual nearly cubic mesh's enclosing dimensions.
  dep=np.maximum(np.min(.029-np.abs(v),axis=1),0)
  return np.r_[((contacts-target)*130).ravel(),dep*350,(x[:9])*0.035,(x[9:21]-q[9:21])*.025,(x[21:24]-x0[21:24])*4]
 lo=np.r_[np.full(9,-1.6),np.tile([-.15,0,0],4),[-.03,-.14,.035]]
 hi=np.r_[np.full(9,1.6),np.tile([1.4,1.9,1.4],4),[.03,-.08,.09]]
 opt=least_squares(residual,x0,bounds=(lo,hi),max_nfev=180)
 v,_=hand(opt.x[:21]);v+=opt.x[21:24]
 print('CUBE_FIT',opt.cost,'wrist',opt.x[21:24], 'contacts',np.stack([v[t].mean(0) for t in tips]),flush=True)
 return opt.x[:21],opt.x[21:24]

def smoothstep(x):
 x=np.clip(x,0,1);return x*x*(3-2*x)

def arm_ik(s,w,pole,upper=.32,fore=.29):
 d=np.linalg.norm(w-s);axis=(w-s)/d
 if d>upper+fore:raise ValueError(f'Unreachable arm: {d}')
 bend=pole-s; bend-=np.dot(bend,axis)*axis;bend/=np.linalg.norm(bend)
 a=(upper*upper-fore*fore+d*d)/(2*d)
 return s+a*axis+np.sqrt(max(upper*upper-a*a,0))*bend

def main():
 data=np.load(HERE/'world-tracks.npz');N=len(data['left_ee_world'])
 cube_q,offset=fit_cube();open_q=np.r_[np.zeros(9),np.tile([.08,.12,.07],4)]
 # Tray: curl fingers below the rim; thumb remains above the rim.
 tray_q=np.r_[np.array([.15,.25,-.35, .1,.1,0, .1,0,0]),np.tile([.25,1.25,.65],4)]
 result={'faces':F,'quads':raw['quads'][:,::-1],'nail_faces':NAIL_F,'rest_vertices':V,'template_cube':cube_q,'template_open':open_q,'template_tray':tray_q}
 for side,grasp,release,begin,traybegin,yaw in [('left',140,291,0,660,-.12),('right',451,615,320,660,.12)]:
  mirror=np.diag([-1,1,1]) if side=='left' else np.eye(3)
  obj=data['pick_object_'+side+'1_world'];ee=data[side+'_ee_world'];tray=data['place_object_world']
  grasp_ref=grasp+6
  R0=Rotation.from_euler('z',yaw).as_matrix()
  O=offset.copy();O[0]*=-1 if side=='left' else 1
  graspW=np.eye(4);graspW[:3,:3]=R0;graspW[:3,3]=obj[grasp_ref,:3,3]+R0@O
  lock=np.linalg.inv(obj[grasp_ref])@graspW
  # Inward-facing hands at the left/right rim of the tray.
  tyaw=-np.pi/2 if side=='left' else np.pi/2
  Rt=Rotation.from_euler('z',tyaw).as_matrix()
  trayW=np.eye(4);trayW[:3,:3]=Rt
  sign=-1 if side=='left' else 1
  trayW[:3,3]=tray[800,:3,3]+np.array([sign*.255,-.004,.043])
  tlock=np.linalg.inv(tray[800])@trayW
  vertices=[];joints=[];wrists=[];params=[];arms=[];nails=[]
  # Approach follows the recorded robot EE displacement, with contact-calibrated offset.
  cube_delta=graspW[:3,3]-ee[grasp_ref,:3,3]
  tray_delta=trayW[:3,3]-ee[800,:3,3]
  for i in range(N):
   H=np.eye(4);H[:3,:3]=R0;H[:3,3]=ee[i,:3,3]+cube_delta
   q=open_q.copy()
   close=smoothstep((i-(grasp-12))/18)
   if i<release:
    locked=obj[i]@lock
    alpha=smoothstep((i-(grasp-18))/20)
    H[:3,3]=(1-alpha)*H[:3,3]+alpha*locked[:3,3]
    H[:3,:3]=Slerp([0,1],Rotation.from_matrix([R0,locked[:3,:3]]))([alpha]).as_matrix()[0]
    q=open_q*(1-close)+cube_q*close
   elif i<traybegin:
    H[:3,3]=obj[release,:3,3]+(obj[release,:3,:3]@lock[:3,3])+(ee[i,:3,3]-ee[release,:3,3])
    alpha=smoothstep((i-release)/16);q=cube_q*(1-alpha)+open_q*alpha
   else:
    alpha=smoothstep((i-traybegin)/60)
    H[:3,:3]=Slerp([0,1],Rotation.from_matrix([R0,Rt]))([alpha]).as_matrix()[0]
    H[:3,3]=ee[i,:3,3]+(1-alpha)*cube_delta+alpha*tray_delta
    lockalpha=smoothstep((i-772)/22)
    locked=tray[i]@tlock
    H[:3,3]=(1-lockalpha)*H[:3,3]+lockalpha*locked[:3,3]
    H[:3,:3]=Slerp([0,1],Rotation.from_matrix([H[:3,:3],locked[:3,:3]]))([lockalpha]).as_matrix()[0]
    close=smoothstep((i-779)/20);q=open_q*(1-close)+tray_q*close
   v,j,A=hand(q,details=True)
   nv=np.einsum('vij,vj->vi',A[NAIL_B],NAIL_V-J[NAIL_B])+j[NAIL_B]
   nv=nv@mirror;nails.append(nv@H[:3,:3].T+H[:3,3])
   v=v@mirror;j=j@mirror
   vertices.append(v@H[:3,:3].T+H[:3,3]);joints.append(j@H[:3,:3].T+H[:3,3]);wrists.append(H);params.append(q)
   shoulder=np.array([-.20 if side=='left' else .20,-.64,1.16]);w=H[:3,3]
   # Small torso lean is allowed, with fixed bone lengths.
   if np.linalg.norm(w-shoulder)>.60:shoulder+=(w-shoulder)*(1-.60/np.linalg.norm(w-shoulder))
   elbow=arm_ik(shoulder,w,shoulder+np.array([-.35 if side=='left' else .35,-.15,-.35]))
   arms.append([shoulder,elbow,w])
  result[side+'_vertices']=np.array(vertices,dtype=np.float32);result[side+'_joints']=np.array(joints);result[side+'_wrist_T']=np.array(wrists);result[side+'_pose']=np.array(params);result[side+'_arm']=np.array(arms);result[side+'_nails']=np.array(nails,dtype=np.float32)
 np.savez_compressed(HERE/'human-animation.npz',**result)
 # Inspection image of fitted grasp, without depending on a renderer.
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from mpl_toolkits.mplot3d.art3d import Poly3DCollection
 from itertools import product
 v,_=hand(cube_q);v+=offset
 fig=plt.figure(figsize=(10,5))
 for k,az in enumerate([-70,30]):
  ax=fig.add_subplot(1,2,k+1,projection='3d');ax.add_collection3d(Poly3DCollection(v[F],facecolor=[.7,.44,.3],edgecolor=[.3,.2,.1],linewidth=.1));ax.scatter(*np.array(list(product([-.029,.029],repeat=3))).T,c='b');ax.set(xlim=(-.12,.12),ylim=(-.15,.09),zlim=(-.08,.16));ax.view_init(25,az)
 fig.savefig(HERE/'grasp-fit.png',dpi=150)
 print('ANIMATION_SAVED',N,flush=True)

if __name__=='__main__':main()
