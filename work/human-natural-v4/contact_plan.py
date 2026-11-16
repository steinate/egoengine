"""Retarget one immutable official dual-arm episode to a human skeleton.
Object motion is never simulated anew. Human joint angles are not robot joints.
"""
import sys,json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from scipy.optimize import least_squares
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');OUT=ROOT/'human-natural-v4';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'human41'))
from human_control import Human,rot,smooth
h=Human();src=ROOT/'human-stack-v3/source/world-tracks.npz';track=dict(np.load(src));N=len(track['place_object_world']);timing=json.loads((ROOT/'human-stack-v3/source/contact-schedule.json').read_text())
h.world[:3,3]=[0,-.64,-.01]
base=h.priors[0].copy()
def unit(x):return x/max(np.linalg.norm(x),1e-12)
def align(a,b):
 a=unit(a);b=unit(b);v=np.cross(a,b);c=np.dot(a,b)
 if c<-.99999:return Rotation.from_rotvec(unit(np.cross(a,[1,.1,.2]))*np.pi).as_matrix()
 V=np.array([[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0]])
 return np.eye(3)+V+V@V/(1+c)
def chain(p,names,target,pole):
 """Two-bone IK, exact original segment lengths, elbow selected by body pole."""
 a,b,c=[h.idx(n) for n in names];g=h.fk(p);S=g[a,:3,3];d=target-S;dist=np.linalg.norm(d);u=unit(d)
 l1=np.linalg.norm(p[b,:3,3]);l2=np.linalg.norm(p[c,:3,3]);dc=np.clip(dist,abs(l1-l2)+.001,l1+l2-.001)
 axial=(l1*l1-l2*l2+dc*dc)/(2*dc);height=np.sqrt(max(l1*l1-axial*axial,0));v=unit(pole-S-u*np.dot(pole-S,u));E=S+u*axial+v*height;W=S+u*dc
 # Rotate upper bone while retaining roll from the reference pose.
 desired=align(g[b,:3,3]-S,E-S)@g[a,:3,:3];p[a,:3,:3]=g[h.parents[a],:3,:3].T@desired
 g=h.fk(p);desired=align(g[c,:3,3]-g[b,:3,3],W-E)@g[b,:3,:3];p[b,:3,:3]=g[a,:3,:3].T@desired
 return p,float(max(dist-dc,0))

def fingers(side,f,p=None):
 p=(base if p is None else p).copy();s=1 if side=='R' else -1
 # Left local axes are mirrored; preserve the actual left skeleton/mesh.
 for k in [1,2,3]:
  j=h.idx(side+'_Thumb'+str(k));D=rot(0,f[0])@rot(1,s*f[1])@rot(2,s*f[2]) if k==1 else rot(2,s*f[2+k-1]);p[j,:3,:3]=h.rest[j,:3,:3]@D
 for k,name in enumerate(['Index','Mid','Ring','Pinky']):
  ab,mp,pi=f[5+3*k:8+3*k]
  for n,D in [(1,rot(0,ab)@rot(2,s*mp)),(2,rot(2,s*pi)),(3,rot(2,s*.65*pi))]:
   j=h.idx(side+'_'+name+str(n));p[j,:3,:3]=h.rest[j,:3,:3]@D
 return p

def handpoints(side,f,H):
 p=fingers(side,f);g=h.fk(p);g=H@np.linalg.inv(g[h.idx(side+'_Hand')])@g;tips=[];samples=[]
 for name in h.fingers:
  ids=[h.idx(side+'_'+name+str(k)) for k in [1,2,3]];pts=[g[j,:3,3] for j in ids];pts.append(g[ids[-1],:3,3]+g[ids[-1],:3,1]*h.tip_length[name]);tips.append(pts[-1])
  for aa,bb in zip(pts[:-1],pts[1:]):samples.extend(aa+(bb-aa)*v for v in [0,.33,.66,1.])
 return np.array(tips),np.array(samples)

def fit_cube(side):
 s=1 if side=='R' else -1;R=rot(2,s*.35)@rot(0,-.50)@np.array([[0,0,-s],[0,1,0],[s,0,0.]])
 targets=np.array([[-.036,-.008,.002],[-.018,.036,.001],[.004,.036,-.003],[.023,.034,-.001],[.034,.022,.004]]);targets[:,0]*=s;targets=targets@rot(2,s*.35).T;targets[:,:2]*=(.036/np.max(np.abs(targets[:,:2]),axis=1))[:,None]
 f0=np.r_[0.,.25,.35,.6,.5,np.tile([0.,.65,1.0],4)];origin=np.array([s*.025,-.080,.110])
 lo=np.r_[[-.065,-.14,.045],[-.3,-.3,-.3],[-1.,-1.3,-1.,0,0],np.tile([-.4,0,0],4)]
 hi=np.r_[[.065,-.015,.14],[.3,.3,.3],[1.,1.3,1.5,1.6,1.5],np.tile([.4,1.7,1.9],4)]
 def unpack(x):
  H=np.eye(4);H[:3,:3]=R@Rotation.from_rotvec(x[3:6]).as_matrix();H[:3,3]=x[:3];return H
 def residual(x):
  tips,pts=handpoints(side,x[6:],unpack(x));q=np.abs(pts)-.029;sdf=np.linalg.norm(np.maximum(q,0),axis=1)+np.minimum(q.max(1),0)
  return np.r_[(tips-targets).ravel()*250,np.maximum(.006-sdf,0)*190,np.maximum(-.021-pts[:,2],0)*200,(x[:3]-origin)*4,x[3:6]*.2,(x[6:]-f0)*.12]
 best=least_squares(residual,np.r_[origin,[0,0,0],f0],bounds=(lo,hi),max_nfev=320)
 H=unpack(best.x);tips,pts=handpoints(side,best.x[6:],H)
 print('CUBE_FIT',side,'wrist',H[:3,3], 'tiperr',np.linalg.norm(tips-targets,axis=1),flush=True)
 return H,best.x[6:],{'tip_error_m':np.linalg.norm(tips-targets,axis=1).tolist(),'wrist':H.tolist()}

def fit_tray(side):
 s=1 if side=='R' else -1
 R=rot(2,s*np.pi/4)@rot(0,-.50)@np.array([[0,0,-s],[0,1,0],[s,0,0.]])
 targets=np.array([[.165,-.028,.010],[.136,-.025,.008],[.136,0,.008],[.136,.024,.008],[.137,.042,.008]]);targets[:,0]*=s
 origin=np.array([s*.215,-.065,.105]);f0=np.r_[0.,.25,.35,.6,.5,np.tile([0.,.8,1.1],4)]
 lo=np.r_[[min(s*.18,s*.29),-.125,.035],[-.35,-.35,-.35],[-1.,-1.3,-1.,0,0],np.tile([-.4,0,0],4)]
 hi=np.r_[[max(s*.18,s*.29),.025,.15],[.35,.35,.35],[1.,1.3,1.5,1.6,1.5],np.tile([.4,1.7,1.9],4)]
 boxes=[(np.array([0,0,-.024]),np.array([.153,.076,.004])),(np.array([.149,0,0]),np.array([.005,.076,.027])),(np.array([-.149,0,0]),np.array([.005,.076,.027])),(np.array([0,.072,0]),np.array([.153,.004,.027])),(np.array([0,-.072,0]),np.array([.153,.004,.027]))]
 def unpack(x):
  H=np.eye(4);H[:3,:3]=R@Rotation.from_rotvec(x[3:6]).as_matrix();H[:3,3]=x[:3];return H
 def residual(x):
  tips,pts=handpoints(side,x[6:],unpack(x));ds=[]
  for center,half in boxes:
   q=np.abs(pts-center)-half;ds.append(np.linalg.norm(np.maximum(q,0),axis=1)+np.minimum(q.max(1),0))
  sdf=np.min(ds,axis=0)
  return np.r_[(tips-targets).ravel()*300,np.maximum(.006-sdf,0)*210,np.maximum(-.020-pts[:,2],0)*220,(x[:3]-origin)*4,x[3:6]*.2,(x[6:]-f0)*.12]
 best=least_squares(residual,np.r_[origin,[0,0,0],f0],bounds=(lo,hi),max_nfev=350)
 H=unpack(best.x);tips,pts=handpoints(side,best.x[6:],H)
 print('TRAY_FIT',side,'wrist',H[:3,3],'tiperr',np.linalg.norm(tips-targets,axis=1),flush=True)
 return H,best.x[6:],{'tip_error_m':np.linalg.norm(tips-targets,axis=1).tolist(),'wrist':H.tolist(),'type':'Thumb outside and four fingers inside the original tray end rim'}

def mix(A,B,u):
 C=np.eye(4);C[:3,3]=A[:3,3]*(1-u)+B[:3,3]*u;C[:3,:3]=Slerp([0,1],Rotation.from_matrix(np.array([A[:3,:3],B[:3,:3]])))(float(u)).as_matrix();return C

# One contact template per hand, attached in the OBJECT frame through the carry.
fits={s:fit_cube(s) for s in ['L','R']};trayfits={s:fit_tray(s) for s in ['L','R']};allposes=[];alltargets=[];errors=[];eyes=[];cameras=[];elbows=[]
fopen=np.r_[0.,.05,.10,.12,.10,np.tile([0.,.12,.12],4)]
rests={};locks={};traylocks={}
for side,sign,ref,obj in [('L',-1,timing['left']['grasp'],'pick_object_left1'),('R',1,timing['right']['grasp'],'pick_object_right1')]:
 H= fits[side][0].copy();H[:3,3]+=track[obj+'_world'][ref,:3,3];locks[side]=np.linalg.inv(track[obj+'_world'][ref])@H
 Hrest=fits[side][0].copy();Hrest[:3,3]=[sign*.26,-.43,1.08];rests[side]=Hrest
 # Fingers curl around the real outer tray rim, not an imaginary wider tray.
 Htray=trayfits[side][0].copy();Htray[:3,3]+=track['place_object_world'][timing['tray']['grasp'],:3,3]
 traylocks[side]=np.linalg.inv(track['place_object_world'][timing['tray']['grasp']])@Htray

def schedule(side,i):
 t=timing['left' if side=='L' else 'right'];obj=t['object'];begin=t['begin'];grasp=t['grasp'];release=t['release'];tray_begin=timing['tray']['begin'];tray_grasp=timing['tray']['grasp']
 locked=track[obj+'_world'][i]@locks[side];H=rests[side].copy();f=fopen.copy();closed=fits[side][1]
 if begin<=i<grasp:
  pre=locked.copy();pre[:3,3]+=[0,-.035,.085];mid=grasp-36
  if i<mid:H=mix(rests[side],pre,smooth((i-begin)/max(mid-begin,1)))
  else:H=mix(pre,locked,smooth((i-mid)/(grasp-mid)))
  f=fopen+(closed-fopen)*smooth((i-(grasp-24))/24)
 elif grasp<=i<=release:H=locked;f=closed.copy()
 elif release<i<release+60:
  start=track[obj+'_world'][release]@locks[side];end=start.copy();end[:3,3]+=[0,-.065,.12];u=smooth((i-release)/60);H=mix(start,end,u);f=closed+(fopen-closed)*smooth((i-release)/20)
 elif release+60<=i<tray_begin:
  start=track[obj+'_world'][release]@locks[side];start[:3,3]+=[0,-.065,.12];H=mix(start,rests[side],smooth((i-release-60)/50))
 if i>=tray_begin:
  tray=track['place_object_world'][i]@traylocks[side];pre=tray.copy();pre[:3,3]+=[0,-.02,.07]
  arrive=tray_grasp-25
  if i<arrive:H=mix(rests[side],pre,smooth((i-tray_begin)/(arrive-tray_begin)))
  elif i<tray_grasp:H=mix(pre,tray,smooth((i-arrive)/(tray_grasp-arrive)))
  else:H=tray
  f=fopen+(trayfits[side][1]-fopen)*smooth((i-arrive)/(tray_grasp-arrive))
 return H,f
