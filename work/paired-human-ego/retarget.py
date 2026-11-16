"""Retarget one immutable official dual-arm episode to a human skeleton.
Object motion is never simulated anew. Human joint angles are not robot joints.
"""
import sys,json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from scipy.optimize import least_squares
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');OUT=ROOT/'paired-human-ego';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'human41'))
from human_control import Human,rot,smooth
h=Human();src=ROOT/'outputs41/human-ego/world-tracks.npz';track=dict(np.load(src));N=844
h.world[:3,3]=[0,-.52,-.21]
base=h.base.copy()
# Shared torso, legs, neck and both arms belong to ONE complete skeleton.
i=h.idx('Spine01');base[i,:3,:3]=h.base[i,:3,:3]@rot(0,.30)
# Set a forward-facing head, looking down toward the unchanged work surface.
grest=h.fk(h.rest)
for name,pitch in [('NeckTwist01',-.32),('Head',-.90)]:
 g=h.fk(base);j=h.idx(name);base[j,:3,:3]=g[h.parents[j],:3,:3].T@rot(0,pitch)@grest[j,:3,:3]
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
# Bend the knees to preserve feet on the original floor after lowering the pelvis.
for side,sign in [('L',-1),('R',1)]:
 base,_=chain(base,[side+'_Thigh',side+'_Calf',side+'_Foot'],np.array([sign*.13,-.58,.065]),np.array([sign*.15,-.20,.45]))
 g=h.fk(base);j=h.idx(side+'_Foot');base[j,:3,:3]=g[h.parents[j],:3,:3].T@grest[j,:3,:3]

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
 s=1 if side=='R' else -1;R=np.array([[0,0,-s],[0,1,0],[s,0,0.]])
 targets=np.array([[-.036,-.008,.002],[-.018,.036,.001],[.004,.036,-.003],[.023,.034,-.001],[.034,.022,.004]]);targets[:,0]*=s
 f0=np.r_[0.,.25,.35,.6,.5,np.tile([0.,.65,1.0],4)];origin=np.array([0,-.075,.095])
 lo=np.r_[[-.065,-.14,.045],[-.7,-.7,-.7],[-1.,-1.3,-1.,0,0],np.tile([-.4,0,0],4)]
 hi=np.r_[[.065,-.015,.14],[.7,.7,.7],[1.,1.3,1.5,1.6,1.5],np.tile([.4,1.7,1.9],4)]
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
 R=rot(2,s*np.pi/2)@np.array([[0,0,-s],[0,1,0],[s,0,0.]])
 targets=np.array([[.165,-.028,.010],[.136,-.025,.008],[.136,0,.008],[.136,.024,.008],[.137,.042,.008]]);targets[:,0]*=s
 origin=np.array([s*.240,0,.082]);f0=np.r_[0.,.25,.35,.6,.5,np.tile([0.,.8,1.1],4)]
 lo=np.r_[[min(s*.20,s*.29),-.055,.035],[-.8,-.8,-.8],[-1.,-1.3,-1.,0,0],np.tile([-.4,0,0],4)]
 hi=np.r_[[max(s*.20,s*.29),.055,.13],[.8,.8,.8],[1.,1.3,1.5,1.6,1.5],np.tile([.4,1.7,1.9],4)]
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
for side,sign,ref,obj in [('L',-1,146,'pick_object_left1'),('R',1,457,'pick_object_right1')]:
 H= fits[side][0].copy();H[:3,3]+=track[obj+'_world'][ref,:3,3];locks[side]=np.linalg.inv(track[obj+'_world'][ref])@H
 Hrest=fits[side][0].copy();Hrest[:3,3]=[sign*.26,-.48,.93];rests[side]=Hrest
 # Fingers curl around the real outer tray rim, not an imaginary wider tray.
 Htray=trayfits[side][0].copy();Htray[:3,3]+=track['place_object_world'][800,:3,3]
 traylocks[side]=np.linalg.inv(track['place_object_world'][800])@Htray

def schedule(side,i):
 obj,begin,grasp,release=('pick_object_left1',0,135,291) if side=='L' else ('pick_object_right1',320,445,615)
 locked=track[obj+'_world'][i]@locks[side];H=rests[side].copy();f=fopen.copy();closed=fits[side][1]
 if begin<=i<grasp:
  # Lift over the original table and settle from above at the original contact time.
  pre=locked.copy();pre[:3,3]+=[0,-.035,.085];mid=grasp-36
  if i<mid:H=mix(rests[side],pre,smooth((i-begin)/max(mid-begin,1)))
  else:H=mix(pre,locked,smooth((i-mid)/(grasp-mid)))
  f=fopen+(closed-fopen)*smooth((i-(grasp-24))/24)
 elif grasp<=i<=release:H=locked;f=closed.copy()
 elif release<i<release+38:
  start=track[obj+'_world'][release]@locks[side];end=start.copy();end[:3,3]+=[0,-.065,.085];u=smooth((i-release)/38);H=mix(start,end,u);f=closed+(fopen-closed)*smooth((i-release)/20)
 elif release+38<=i<660:
  start=track[obj+'_world'][release]@locks[side];start[:3,3]+=[0,-.065,.085];H=mix(start,rests[side],smooth((i-release-38)/38))
 if i>=660:
  tray=track['place_object_world'][i]@traylocks[side];pre=tray.copy();pre[:3,3]+=[0,-.02,.07]
  start_tray=rests[side]
  if side=='R':
   start_tray=track[obj+'_world'][release]@locks[side];start_tray[:3,3]+=[0,-.065,.085];start_tray=mix(start_tray,rests[side],smooth((660-release-38)/38))
  if i<690:H=mix(start_tray,pre,smooth((i-660)/30))
  elif i<708:H=mix(pre,tray,smooth((i-690)/18))
  else:H=tray
  f=fopen+(trayfits[side][1]-fopen)*smooth((i-690)/18)
 return H,f

for i in range(N):
 p=base.copy();targets=[];es=[]
 for side,sign in [('L',-1),('R',1)]:
  H,f=schedule(side,i);p,e=chain(p,[side+'_Upperarm',side+'_Forearm',side+'_Hand'],H[:3,3],H[:3,3]-H[:3,1]*.30+np.array([sign*.045,-.035,-.055]));g=h.fk(p);jfore=h.idx(side+'_Forearm');jhand=h.idx(side+'_Hand');axis=unit(p[jhand,:3,3]);aim=g[jfore,:3,:3].T@H[:3,0];ref=np.array([1.,0,0]);ref=unit(ref-axis*np.dot(ref,axis));aim=unit(aim-axis*np.dot(aim,axis));angle=np.arctan2(np.dot(axis,np.cross(ref,aim)),np.dot(ref,aim));p[jfore,:3,:3]=p[jfore,:3,:3]@Rotation.from_rotvec(axis*angle).as_matrix();g=h.fk(p);j=h.idx(side+'_Hand');p[j,:3,:3]=g[h.parents[j],:3,:3].T@H[:3,:3];p=fingers(side,f,p)
  # Keep auxiliary twist bones aligned to their parent; their rest offsets remain intact.
  for limb in ['Upperarm','Forearm']:
   for suffix in ['Twist01','Twist02']:
    j=h.idx(side+'_'+limb+suffix);p[j,:3,:3]=h.rest[j,:3,:3]
  targets.append(H);es.append(e)
 g=h.fk(p);eye=(g[h.idx('L_Eye'),:3,3]+g[h.idx('R_Eye'),:3,3])/2;target=np.array([eye[0],-.15,.86]);forward=unit(target-eye);eye=eye+forward*.018
 z=-forward;x=unit(np.cross([0,0,1],z));y=np.cross(z,x);C=np.eye(4);C[:3,:3]=np.stack([x,y,z],1);C[:3,3]=eye
 allposes.append(p);alltargets.append(targets);errors.append(es);eyes.append(eye);cameras.append(C);elbows.append(g[[h.idx('L_Forearm'),h.idx('R_Forearm')],:3,3])
assert np.max(errors)<.003, ('Unreachable human wrist target',np.max(errors))
np.savez_compressed(OUT/'human-animation.npz',local=np.array(allposes),world_transform=h.world,names=h.names,parents=h.parents,source_frame=np.arange(N),video_time_s=np.arange(N)/15,nominal_sim_time_s=np.arange(N)/30,wrist_targets=np.array(alltargets),arm_reach_error_m=np.array(errors),eye_world=np.array(eyes),camera_world_usd=np.array(cameras),elbows=np.array(elbows),**track)
report={'source_world_tracks':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'frames':N,'fps':15,'object_motion':'Exact original official episode, no new object physics','human_motion':'Object-relative grasp locks and full character two-bone IK with elbow poles; fixed bone lengths; no robot joint angles','camera':'Midpoint of actual posed L_Eye/R_Eye bones plus 18mm along gaze; 84 degree horizontal FOV','max_unreachable_distance_m':np.max(errors).item(),'fits':{s:fits[s][2] for s in fits},'tray_fits':{s:trayfits[s][2] for s in trayfits},'world_transform':h.world.tolist(),'eye':eyes[0].tolist(),'contact_events':{'left_grasp':135,'left_release':291,'right_grasp':445,'right_release':615,'tray_lock':708},'quality_limit':'Geometric retargeting, not a learned human motion policy; fingers approximated from skeleton contact constraints'}
(OUT/'retarget-report.json').write_text(json.dumps(report,indent=2));print('DONE',report['max_unreachable_distance_m'],'eye',eyes[0],flush=True)
