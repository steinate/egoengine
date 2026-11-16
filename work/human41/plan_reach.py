"""Plan an independent human reach/grasp/lift; object path is not an input."""
import json
from human_control import *
h=Human();sol=np.load(BASE/'output/grasp-solution.npz');H=sol['H'];closed=sol['fingers'];opened=closed.copy();opened[2:5]*=.25
for k in range(4):opened[6+3*k:8+3*k]*=.2
preshape=np.load(BASE/'output/finger-preshape.npz')['fingers']
fps=30;times=np.arange(259)/fps;qs=[];fs=[];errors=[];goals=[];q=None;prior=None;worlds=[]
for i,t in enumerate(times):
 target=H.copy();reach=smooth(t/1.8);target[:3,3]+=np.array([0,-.08,.16])*(1-reach)
 close=smooth((t-1.8)/1.0)*(1-smooth((t-7.)/.8));lift=.15*smooth((t-3.4)/1.4)*(1-smooth((t-5.8)/1.2));target[2,3]+=lift
 if t>7.8:target[:3,3]+=np.array([0,-.08,.16])*smooth((t-7.8)/.8)
 q,p,err=h.solve_arm(target,q,prior,multistart=(q is None))
 if prior is None:prior=q.copy()
 u=(1-close)*(len(preshape)-1);j=min(int(u),len(preshape)-2);alpha=u-j;f=preshape[j]*(1-alpha)+preshape[j+1]*alpha;local=h.finger_pose(f,p);g=h.fk(local);qs.append(q);fs.append(f);errors.append(err);goals.append(target);worlds.append(g)
 if i%30==0:print('PLANNED',i,'wrist_error_m',err,flush=True)
worlds=np.array(worlds);qs=np.array(qs)
lengths={}
for a,b in [('R_Upperarm','R_Forearm'),('R_Forearm','R_Hand')]:
 d=np.linalg.norm(worlds[:,h.idx(a),:3,3]-worlds[:,h.idx(b),:3,3],axis=1);lengths[a+'_'+b]={'length_m':float(d.mean()),'range_m':float(np.ptp(d))}
np.savez_compressed(BASE/'output/human-plan.npz',time_s=times,arm_q=qs,fingers=fs,target_wrist=goals,joint_world=worlds)
report={'frames':len(times),'fps':fps,'duration_s':float(times[-1]),'max_wrist_position_error_m':float(max(errors)),'bone_lengths':lengths,'max_arm_step_rad':float(np.abs(np.diff(qs,axis=0)).max()),'max_arm_rate_rad_s':float(np.abs(np.diff(qs,axis=0)).max()*fps),'robot_kinematics_used':False,'input':'object size and initial pose; character skeleton and empirical mocap pose references','human_joint_constraints':'hinge elbow; limited wrist deviation/flexion and forearm pronation; coupled DIP/PIP flexion; bounded clavicle/spine; previous-frame continuity','not_implemented':'learned VPoser/GRAB grasp prior; torque-controlled articulated body; full-body balance and soft skin contact'}
(BASE/'output/human-plan.json').write_text(json.dumps(report,indent=2));print('PLAN_DONE',report,flush=True)
