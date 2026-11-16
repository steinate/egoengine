"""Let fingers absorb small palm IK residuals while maintaining cube/rim contact."""
from arm_model import *
from scipy.sparse import lil_matrix
a=dict(np.load(OUT/'human-animation.npz'));h.world=a['world_transform'];refits=np.load(OUT/'grasp-refit.npz')
# Reconstruct baseline: reruns never compound corrections.
for side in ['L','R']:
    fits[side]=(refits[side+'_H'],refits[side+'_f'],{});locks[side]=refits[side+'_H']
baseline=np.array([[schedule(s,i)[1] for s in ['L','R']] for i in range(N)])
idle=np.r_[0.,.10,.20,.25,.20,np.tile([0.,.30,.38],4)]
for si,side in enumerate(['L','R']):
    t=timing['left' if side=='L' else 'right']
    for i in range(N):
        before=1.-smooth((i-(t['begin']-25))/50) if i<t['grasp'] else 0.
        after=smooth((i-t['release']-45)/45)*(1.-smooth((i-timing['tray']['begin']+25)/50))
        blend=max(before,after);baseline[i,si]=baseline[i,si]*(1-blend)+idle*blend
restg=h.fk(h.rest);newf=baseline.copy();stats={}
for si,side in enumerate(['L','R']):
    sign=1 if side=='R' else -1;hand=h.idx(side+'_Hand');chains=[]
    restg=h.fk(fingers(side,np.zeros(17)))
    for name in h.fingers:
        ids=[h.idx(side+'_'+name+str(k)) for k in [1,2,3]]
        root=np.linalg.inv(restg[hand])@restg[ids[0]]
        children=[np.linalg.inv(restg[ids[j-1]])@restg[ids[j]] for j in [1,2]]
        chains.append((name,[root,*children]))
    def fast_points(f,H):
        tips=[];points=[]
        for j,(name,chain) in enumerate(chains):
            if j==0:D=[rot(0,f[0])@rot(1,sign*f[1])@rot(2,sign*f[2]),rot(2,sign*f[3]),rot(2,sign*f[4])]
            else:
                ab,mp,pi=f[5+3*(j-1):8+3*(j-1)];D=[rot(0,ab)@rot(2,sign*mp),rot(2,sign*pi),rot(2,sign*.65*pi)]
            T=H.copy()
            for C,delta in zip(chain,D):
                local=C.copy();local[:3,:3]=local[:3,:3]@delta;T=T@local;points.append(T[:3,3])
            tip=T[:3,3]+T[:3,1]*h.tip_length[name];tips.append(tip);points.append(tip)
        return np.array(tips),np.array(points)
    referenceH=refits[side+'_H'];referencef=refits[side+'_f']
    assert np.max(np.abs(fast_points(referencef,referenceH)[0]-handpoints(side,referencef,referenceH)[0]))<1e-8
    t=timing['left' if side=='L' else 'right'];intervals=[(t['object'],t['grasp'],t['release'],referenceH,referencef),('place_object',1331,N-1,traylocks[side],trayfits[side][1])]
    for name,start,end,lock,closed in intervals:
        target,_=fast_points(closed,lock);K=end-start+1
        Hs=np.array([np.linalg.inv(a[name+'_world'][i])@h.fk(a['local'][i])[hand] for i in range(start,end+1)])
        def rb(axis,v):
            r=np.zeros((K,3));r[:,axis]=v;return Rotation.from_rotvec(r).as_matrix()
        def batch_points(f):
            tips=[]
            for j,(finger,chain) in enumerate(chains):
                if j==0:D=[rb(0,f[:,0])@rb(1,sign*f[:,1])@rb(2,sign*f[:,2]),rb(2,sign*f[:,3]),rb(2,sign*f[:,4])]
                else:
                    ab,mp,pi=f[:,5+3*(j-1):8+3*(j-1)].T;D=[rb(0,ab)@rb(2,sign*mp),rb(2,sign*pi),rb(2,sign*.65*pi)]
                R=Hs[:,:3,:3];T=Hs[:,:3,3]
                for C,delta in zip(chain,D):
                    T=T+R@C[:3,3];R=R@C[:3,:3]@delta
                tips.append(T+R[:,:,1]*h.tip_length[finger])
            return np.stack(tips,axis=1)
        lower=np.r_[[-1,-1.3,-1,0,0],np.tile([-.4,0,0],4)];upper=np.r_[[1,1.3,1.5,1.6,1.5],np.tile([.4,1.7,1.9],4)]
        def residual(flat):
            f=flat.reshape(K,17)
            return np.r_[np.c_[(batch_points(f)-target).reshape(K,15)*1200,(f-closed)*2.].ravel(),(np.diff(f,axis=0)*10).ravel(),(np.diff(f,2,axis=0)*35).ravel()]
        sp=lil_matrix((K*32+(K-1)*17+(K-2)*17,K*17),dtype=np.int8)
        for i in range(K):sp[i*32:(i+1)*32,i*17:(i+1)*17]=1
        for i in range(K-1):sp[K*32+i*17:K*32+(i+1)*17,i*17:(i+2)*17]=1
        off=K*32+(K-1)*17
        for i in range(K-2):sp[off+i*17:off+(i+1)*17,i*17:(i+3)*17]=1
        initial=np.tile(closed,(K,1));fit=least_squares(residual,np.clip(initial,lower+1e-6,upper-1e-6).ravel(),bounds=(np.tile(lower,K),np.tile(upper,K)),jac_sparsity=sp.tocsr(),max_nfev=60,ftol=1e-5,xtol=1e-6)
        newf[start:end+1,si]=fit.x.reshape(K,17);errors=np.linalg.norm(batch_points(fit.x.reshape(K,17))-target,axis=-1).max(axis=1)
        firstdelta=newf[start,si]-baseline[start,si];lastdelta=newf[end,si]-baseline[end,si]
        for i in range(max(0,start-20),start):newf[i,si]+=firstdelta*smooth((i-start+20)/20)
        for i in range(end+1,min(N,end+21)):newf[i,si]+=lastdelta*(1-smooth((i-end)/20))
        stats[side+'_'+name]={'max_fingertip_target_error_m':max(errors),'frames':[start,end]};print('FINGER_CONTACT',side,name,max(errors),flush=True)
for i in range(N):
    for si,side in enumerate(['L','R']):a['local'][i]=fingers(side,newf[i,si],a['local'][i])
a['finger_q']=newf;np.savez_compressed(OUT/'human-animation.npz',**a)
stats['max_finger_parameter_step_deg']=float(np.rad2deg(np.abs(np.diff(newf,axis=0))).max())
(OUT/'finger-contact-refinement.json').write_text(json.dumps(stats,indent=2));print('FINGER_REFINEMENT_DONE',stats,flush=True)
