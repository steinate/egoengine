"""Continuous whole-episode IK with anatomical elbow planes and acceleration costs."""
from arm_model import *
from scipy.sparse import lil_matrix
from scipy.signal import savgol_filter
import time

old=np.load(ROOT/'human-stack-v3/human-animation.npz')
# A steady working stance, with fewer forward/backward torso excursions.
keys=np.array([0,90,137,260,433,550,621,720,780,930,1044,1140,1191,1331,1431,N-1])
leans=np.deg2rad([27,38,46,37,39,31,31,42,50,36,36,31,33,41,33,33])
def lean_at(i):
    k=min(np.searchsorted(keys,i,side='right')-1,len(keys)-2);u=smooth((i-keys[k])/(keys[k+1]-keys[k]));return leans[k]*(1-u)+leans[k+1]*u
lo=np.r_[[-.14,-.14],[-2.7,-2.7,-2.7],.25,-1.65,-.32,-.65]
hi=np.r_[[.14,.14],[2.7,2.7,2.7],2.40,1.65,.32,.65]
sidelean=lambda i:.08*smooth((i-670)/100)*(1.-smooth((i-800)/110))
bodies=np.array([body_pose(lean_at(i),sidelean(i)) for i in range(N)])

def elbow_goal(S,W,side,l1,l2):
    d=W-S;dist=np.linalg.norm(d,axis=-1);u=d/np.maximum(dist[...,None],1e-8)
    dc=np.clip(dist,abs(l1-l2)+.001,l1+l2-.001)
    along=(l1*l1-l2*l2+dc*dc)/(2*dc);height=np.sqrt(np.maximum(l1*l1-along*along,0))
    sign=1 if side=='R' else -1
    pole=np.array([sign*.80,.12,-.68]);v=pole-np.sum(u*pole,axis=-1)[...,None]*u;v/=np.maximum(np.linalg.norm(v,axis=-1)[...,None],1e-8)
    return S+u*along[...,None]+v*height[...,None]

def local_residual(q,arm,H,prior):
    _,g=arm.fk(q);S,E,W=g[1,:3,3],g[2,:3,3],g[3,:3,3]
    l1=np.linalg.norm(arm.parts[2][:3,3]);l2=np.linalg.norm(arm.parts[3][:3,3]);goal=elbow_goal(S,H[:3,3],arm.side,l1,l2)
    return np.r_[(W-H[:3,3])*700,Rotation.from_matrix(H[:3,:3].T@g[3,:3,:3]).as_rotvec()*25,
                 (E-goal)*16,max(.015-arm.sign*(E[0]-S[0]),0)*300,
                 max(S[1]-.005-E[1],0)*180,(q-prior)*np.array([1.5,1.5,.05,.05,.05,.03,.03,.0,.0]),q[7:9]*1.2]

# Choose a cube-face grasp for each hand using the complete carry's key poses.
# Quarter-turns are true cube symmetries; finger geometry is rotated with the palm.
grasp_report={}
if (OUT/'grasp-refit.npz').exists():
    refits=np.load(OUT/'grasp-refit.npz');grasp_report=json.loads((OUT/'grasp-refit.json').read_text())
    for side in ['L','R']:
        fits[side]=(refits[side+'_H'],refits[side+'_f'],grasp_report[side]);locks[side]=refits[side+'_H']
    print('USING_NEUTRAL_WRIST_GRASPS',grasp_report,flush=True)
else:
    grasp_report={}
    for si,side in enumerate(['L','R']):
        t=timing['left' if side=='L' else 'right'];frames=np.unique(np.linspace(t['grasp'],t['release'],5,dtype=int));candidates=[]
        for deg in [0,90,-90,180]:
            Z=np.eye(4);Z[:3,:3]=rot(2,np.deg2rad(deg));lock=Z@fits[side][0];cost=0.;solutions=[]
            for frame in frames:
                arm=Arm(side,bodies[frame]);H=track[t['object']+'_world'][frame]@lock;prior=old['arm_q'][frame,si].copy()
                result=least_squares(local_residual,np.clip(prior,lo+1e-5,hi-1e-5),args=(arm,H,prior),bounds=(lo,hi),max_nfev=150)
                cost+=float(np.sum(result.fun**2));solutions.append(result.x)
            candidates.append((cost,deg,lock))
        best=min(candidates,key=lambda c:c[0]);locks[side]=best[2];grasp_report[side]={'selected_yaw_degrees':best[1],'candidate_costs':{str(c[1]):c[0] for c in candidates}}
        print('GRASP_SELECTION',side,grasp_report[side],flush=True)

targets=[];finger_values=[]
for i in range(N):
    body=h.fk(bodies[i])
    for side,sign in [('L',-1),('R',1)]:
        shoulder=body[h.idx(side+'_Upperarm'),:3,3]
        rests[side]=fits[side][0].copy();rests[side][:3,3]=shoulder+[sign*.07,.16,-.39]
        rests[side][:3,:3]=rot(2,sign*.20)@rot(0,-.35)@np.array([[0,0,-sign],[0,1,0],[sign,0,0.]])
    result=[schedule(s,i) for s in ['L','R']];targets.append([x[0] for x in result]);finger_values.append([x[1] for x in result])
targets=np.array(targets);finger_values=np.array(finger_values)
idle=np.r_[0.,.10,.20,.25,.20,np.tile([0.,.30,.38],4)]
for si,side in enumerate(['L','R']):
    t=timing['left' if side=='L' else 'right']
    for i in range(N):
        before=1.-smooth((i-(t['begin']-25))/50) if i<t['grasp'] else 0.
        after=smooth((i-t['release']-45)/45)*(1.-smooth((i-timing['tray']['begin']+25)/50))
        blend=max(before,after)
        finger_values[i,si]=finger_values[i,si]*(1-blend)+idle*blend

def axis_batch(axis,angles):
    v=np.zeros((len(angles),3));v[:,axis]=angles;return Rotation.from_rotvec(v).as_matrix()

allq=[];allg=[];global_reports=[]
for si,side in enumerate(['L','R']):
    arms=[Arm(side,p) for p in bodies];parent=np.array([arm.parent for arm in arms]);part=np.array([arm.parts for arm in arms]);sign=1 if side=='R' else -1
    l1=np.linalg.norm(part[0,2,:3,3]);l2=np.linalg.norm(part[0,3,:3,3]);H=targets[:,si]
    def batch_fk(q):
        D=[axis_batch(0,q[:,0])@axis_batch(2,q[:,1]),Rotation.from_rotvec(q[:,2:5]).as_matrix(),axis_batch(0,q[:,5]),axis_batch(1,q[:,6])@axis_batch(0,q[:,7])@axis_batch(2,q[:,8])]
        rotations=[];positions=[];R=parent[:,:3,:3];T=parent[:,:3,3]
        for j in range(4):
            T=T+np.einsum('nij,nj->ni',R,part[:,j,:3,3]);R=R@part[:,j,:3,:3]@D[j];positions.append(T);rotations.append(R)
        return np.stack(positions,axis=1),np.stack(rotations,axis=1)
    # A continuous initializer with fixed references; no nearest-neighbour pose switching.
    init=[];previous=old['arm_q'][0,si].copy()
    for i,arm in enumerate(arms):
        result=least_squares(local_residual,np.clip(previous,lo+1e-5,hi-1e-5),args=(arm,H[i],previous),bounds=(lo,hi),max_nfev=60)
        previous=result.x;init.append(previous)
    init=np.array(init);reference_q=savgol_filter(init,31,3,axis=0)
    reference_q=np.clip(reference_q,lo+1e-6,hi-1e-6)
    def residual(flat):
        q=flat.reshape(N,9);P,R=batch_fk(q);S,E,W=P[:,1],P[:,2],P[:,3]
        desired=elbow_goal(S,H[:,:3,3],side,l1,l2)
        orientation=Rotation.from_matrix(np.swapaxes(H[:,:3,:3],1,2)@R[:,3]).as_rotvec()
        local=np.c_[(W-H[:,:3,3])*700,orientation*25,(E-desired)*16,
                    np.maximum(.015-sign*(E[:,0]-S[:,0]),0)*300,
                    np.maximum(S[:,1]-.005-E[:,1],0)*180,
                    (q-reference_q)*np.array([1.5,1.5,.05,.05,.05,.03,.03,0,0]),q[:,7:9]*1.2]
        return np.r_[local.ravel(),(np.diff(q,axis=0)*.35).ravel(),(np.diff(q,2,axis=0)*14).ravel(),(np.diff(E,2,axis=0)*90).ravel()]
    local_size=22
    assert residual(reference_q.ravel()).size==N*local_size+(N-1)*9+(N-2)*12
    rows=N*local_size+(N-1)*9+(N-2)*12;sp=lil_matrix((rows,N*9),dtype=np.int8)
    for i in range(N):sp[i*local_size:(i+1)*local_size,i*9:(i+1)*9]=1
    off=N*local_size
    for i in range(N-1):sp[off+i*9:off+(i+1)*9,i*9:(i+2)*9]=1
    off+=(N-1)*9
    for i in range(N-2):sp[off+i*9:off+(i+1)*9,i*9:(i+3)*9]=1
    off+=(N-2)*9
    for i in range(N-2):sp[off+i*3:off+(i+1)*3,i*9:(i+3)*9]=1
    print('GLOBAL_START',side,flush=True);t0=time.time()
    result=least_squares(residual,reference_q.ravel(),bounds=(np.tile(lo,N),np.tile(hi,N)),jac_sparsity=sp.tocsr(),tr_solver='lsmr',max_nfev=100,ftol=1e-5,xtol=1e-6,verbose=1)
    q=result.x.reshape(N,9);allq.append(q);allg.append(batch_fk(q));global_reports.append({'side':side,'cost':float(result.cost),'evaluations':result.nfev,'time_s':time.time()-t0,'optimality':float(result.optimality)})
    print('GLOBAL_DONE',global_reports[-1],flush=True)

poses=[];errors=[];elbows=[];feet=[];cameras=[]
for i in range(N):
    p=bodies[i].copy();frame_errors=[]
    for si,side in enumerate(['L','R']):
        q=allq[si][i];arm=Arm(side,p);parts,g=arm.fk(q);p[arm.ids]=parts;p=fingers(side,finger_values[i,si],p)
        twist=axial_y(h.rest[h.idx(side+'_Upperarm'),:3,:3].T@p[h.idx(side+'_Upperarm'),:3,:3])
        for name,angle in [('UpperarmTwist01',-.5*twist),('UpperarmTwist02',.5*twist),('ForearmTwist01',0.),('ForearmTwist02',.5*q[6])]:
            j=h.idx(side+'_'+name);p[j,:3,:3]=h.rest[j,:3,:3]@rot(1,angle)
        H=targets[i,si];frame_errors.append([np.linalg.norm(g[-1,:3,3]-H[:3,3]),Rotation.from_matrix(H[:3,:3].T@g[-1,:3,:3]).magnitude()])
    g=h.fk(p);eye=(g[h.idx('L_Eye'),:3,3]+g[h.idx('R_Eye'),:3,3])/2;target=np.array([eye[0],-.12,.84]);forward=unit(target-eye);eye+=forward*.018;z=-forward;x=unit(np.cross([0,0,1],z));y=np.cross(z,x);C=np.eye(4);C[:3,:3]=np.stack([x,y,z],1);C[:3,3]=eye
    poses.append(p);errors.append(frame_errors);cameras.append(C);elbows.append(g[[h.idx('L_Forearm'),h.idx('R_Forearm')],:3,3]);feet.append(g[[h.idx('L_Foot'),h.idx('R_Foot')],:3,3])
errors=np.array(errors)
np.savez_compressed(OUT/'human-animation.npz',local=np.array(poses),world_transform=h.world,names=h.names,parents=h.parents,source_frame=np.arange(N),video_time_s=np.arange(N)/15,wrist_targets=targets,arm_q=np.stack(allq,axis=1),finger_q=finger_values,ik_errors=errors,camera_world_usd=np.array(cameras),elbows=np.array(elbows),feet=np.array(feet),hip_lean_rad=np.array([lean_at(i) for i in range(N)]),**track)
report={'frames':N,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'max_wrist_position_error_m':float(errors[:,:,0].max()),'max_wrist_orientation_error_deg':float(np.rad2deg(errors[:,:,1].max())),'grasp_selection':grasp_report,'global_solves':global_reports,'method':'Whole-episode sparse IK; continuous outward/down elbow pole; fixed continuous posture reference; angular and elbow acceleration penalties; neutral wrist costs; cube-frame grasp selection'}
(OUT/'retarget-report.json').write_text(json.dumps(report,indent=2));print('OPTIMIZATION_DONE',report,flush=True)
