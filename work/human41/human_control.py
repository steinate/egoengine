"""Character-sized FK, constrained arm IK, and object-centric finger IK.

No robot joint angles or robot bone lengths are consumed. The empirical pose
library is a reference, not a learned human-motion policy or a naturalness proof.
"""
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import least_squares

BASE=Path('/vepfs/public/pengjiaqi/interndata-human-pair/human41')
def rot(axis,a):
 v=np.zeros(3);v[axis]=a;return Rotation.from_rotvec(v).as_matrix()
def smooth(t):
 t=np.clip(t,0,1);return t**3*(10+t*(-15+6*t))

class Human:
 def __init__(self):
  a=np.load(BASE/'output/worker-mocap-prior.npz');self.names=a['names'].tolist();self.short=[n.split('/')[-1] for n in self.names];self.parents=a['parents'];self.rest=a['rest'];self.priors=a['local'];self.labels=a['labels'];self.base=self.priors[0].copy();self.world=np.diag([-1.,-1.,1.,1.]);self.hand=self.idx('R_Hand')
  self.arm_names=['R_Clavicle','R_Upperarm','R_Forearm','R_Hand'];self.fingers=['Thumb','Index','Mid','Ring','Pinky'];self.tip_length=dict(Thumb=.023,Index=.021,Mid=.023,Ring=.020,Pinky=.017)
  self.arm_low=np.array([-.25,-.25,-2.8,-2.8,-2.8,.06,-1.45,-.45,-1.0,-.20]);self.arm_high=np.array([.25,.25,2.8,2.8,2.8,2.45,1.45,.45,1.,.25])
  left=[i for i,n in enumerate(self.names) if '/L_Clavicle' in n];candidates=[]
  for k,reference in enumerate(self.priors):
   pose=self.base.copy();pose[left]=reference[left];wrist=self.fk(pose)[self.idx('L_Hand'),:3,3];candidates.append(np.linalg.norm(wrist-[-.22,.015,.93]))
  selected=int(np.argmin(candidates));self.base[left]=self.priors[selected,left];self.left_reference=self.labels[selected].tolist()
 def idx(self,n):return self.short.index(n)
 def fk(self,local):
  g=local.copy()
  for i,p in enumerate(self.parents):g[i]=(self.world if p<0 else g[p])@local[i]
  return g
 def arm_q(self,pose):
  delta=lambda n:self.rest[self.idx(n),:3,:3].T@pose[self.idx(n),:3,:3]
  upper=Rotation.from_matrix(delta('R_Upperarm')).as_rotvec();elbow=Rotation.from_matrix(delta('R_Forearm')).as_rotvec()[0]
  wrist=Rotation.from_matrix(delta('R_Hand')).as_euler('YXZ')
  return np.clip(np.r_[0.,0.,upper,elbow,wrist,0.],self.arm_low+1e-5,self.arm_high-1e-5)
 def arm_pose(self,q,base=None):
  p=(self.base if base is None else base).copy()
  for n,R in [('R_Clavicle',rot(0,q[0])@rot(2,q[1])),('R_Upperarm',Rotation.from_rotvec(q[2:5]).as_matrix()),('R_Forearm',rot(0,q[5])),('R_Hand',rot(1,q[6])@rot(0,q[7])@rot(2,q[8]))]:
   i=self.idx(n);p[i,:3,:3]=self.rest[i,:3,:3]@R
  i=self.idx('Spine02');p[i,:3,:3]=self.base[i,:3,:3]@rot(0,q[9])
  # Share pronation over auxiliary skinning bones, instead of twisting at cuff.
  for n in ['R_ForearmTwist01','R_ForearmTwist02']:
   i=self.idx(n);p[i,:3,:3]=self.rest[i,:3,:3]@rot(1,q[6]*.5)
  return p
 def solve_arm(self,target,q_previous=None,prior_q=None,multistart=False):
  if prior_q is None:prior_q=self.arm_q(self.base)
  if q_previous is None:q_previous=prior_q
  target=np.asarray(target)
  def residual(q):
   g=self.fk(self.arm_pose(q));H=g[self.hand];elbow=g[self.idx('R_Forearm'),:3,3];shoulder=g[self.idx('R_Upperarm'),:3,3]
   return np.r_[(H[:3,3]-target[:3,3])*350,Rotation.from_matrix(target[:3,:3].T@H[:3,:3]).as_rotvec()*12,
     (q-prior_q)*np.array([1.,1.,.15,.15,.15,.15,.12,.2,.2,.7]),(q-q_previous)*.35,
     max(0.,shoulder[0]-.04-elbow[0])*10,max(0.,elbow[2]-shoulder[2]+.02)*15]
  seeds=[q_previous]
  if multistart:
   globals_=np.array([self.fk(self.arm_pose(self.arm_q(p)))[self.hand,:3,3] for p in self.priors]);ids=np.argsort(np.linalg.norm(globals_-target[:3,3],axis=1))[:6];seeds.extend(self.arm_q(self.priors[k]) for k in ids)
  results=[least_squares(residual,np.clip(q,self.arm_low+1e-6,self.arm_high-1e-6),bounds=(self.arm_low,self.arm_high),max_nfev=80,ftol=1e-7,xtol=1e-7) for q in seeds]
  best=min(results,key=lambda r:np.dot(r.fun,r.fun));return best.x,self.arm_pose(best.x),float(np.linalg.norm(self.fk(self.arm_pose(best.x))[self.hand,:3,3]-target[:3,3]))
 def finger_pose(self,f,base=None):
  p=(self.base if base is None else base).copy()
  # Thumb CMC 3 axes plus MCP/IP flexion; other fingers MCP spread/flexion + PIP, with DIP coupling.
  for i,n in enumerate(['R_Thumb1','R_Thumb2','R_Thumb3']):
   j=self.idx(n);R=(rot(0,f[0])@rot(1,f[1])@rot(2,f[2])) if i==0 else rot(2,f[2+i]);p[j,:3,:3]=self.rest[j,:3,:3]@R
  for k,n in enumerate(['Index','Mid','Ring','Pinky']):
   ab,mp,pi=f[5+3*k:8+3*k]
   for jn,R in [(n+'1',rot(0,ab)@rot(2,mp)),(n+'2',rot(2,pi)),(n+'3',rot(2,.65*pi))]:
    j=self.idx('R_'+jn);p[j,:3,:3]=self.rest[j,:3,:3]@R
  return p
 def hand_geometry(self,local,H=None):
  g=self.fk(local)
  if H is not None:g=H@np.linalg.inv(g[self.hand])@g
  tips=[];segments=[]
  for name in self.fingers:
   ids=[self.idx('R_'+name+str(k)) for k in [1,2,3]];points=[g[j,:3,3] for j in ids];points.append(g[ids[-1],:3,3]+g[ids[-1],:3,1]*self.tip_length[name]);tips.append(points[-1]);segments.extend((points[k],points[k+1],name,k) for k in range(3))
  return np.array(tips),segments,g
 def solve_grasp(self,center,half=.03):
  center=np.asarray(center);R=np.array([[0,0,-1],[0,1,0],[1,0,0.]])
  targets=center+np.array([[0,-half-.008,0],[-.020,half+.007,.003],[0,half+.007,.005],[.018,half+.007,.003],[.026,half+.007,0]])
  f0=np.r_[0.,.25,.35,.6,.5,np.tile([0.,.65,1.0],4)]
  low=np.r_[[-.8,-1.,-.6,0,0],np.tile([-.35,0,0],4)];high=np.r_[[.8,1.3,1.3,1.6,1.5],np.tile([.35,1.65,1.9],4)]
  origin=center+np.array([0,-.075,.105]);x0=np.r_[origin,[0,0,0],f0]
  lower=np.r_[center+[-.05,-.16,.055],[-.7,-.7,-.7],low];upper=np.r_[center+[.07,-.015,.16],[.7,.7,.7],high]
  def unpack(x):
   H=np.eye(4);H[:3,:3]=R@Rotation.from_rotvec(x[3:6]).as_matrix();H[:3,3]=x[:3];p=self.finger_pose(x[6:]);return H,p
  def residual(x):
   H,p=unpack(x);tips,segs,g=self.hand_geometry(p,H);samples=[]
   for aa,bb,name,k in segs:samples.extend(aa+(bb-aa)*u for u in [0,.33,.66,1.])
   samples=np.array(samples);q=np.abs(samples-center)-half;sdf=np.linalg.norm(np.maximum(q,0),axis=1)+np.minimum(q.max(axis=1),0)
   return np.r_[(tips-targets).ravel()*250,np.maximum(.006-sdf,0)*140,(x[:3]-origin)*5,x[3:6]*.15,(x[6:]-f0)*.12,np.maximum(1.002-samples[:,2],0)*100]
  best=least_squares(residual,x0,bounds=(lower,upper),max_nfev=350,ftol=1e-8)
  H,p=unpack(best.x);tips,segs,g=self.hand_geometry(p,H)
  return H,best.x[6:],{'tip_targets_m':targets.tolist(),'tip_positions_m':tips.tolist(),'tip_errors_m':np.linalg.norm(tips-targets,axis=1).tolist(),'objective':float(np.dot(best.fun,best.fun)),'evaluations':best.nfev}
