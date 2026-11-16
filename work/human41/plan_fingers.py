"""Object-aware preshape: move pads toward opposing faces, avoiding a sweeping closure."""
import json
from human_control import *
h=Human();s=np.load(BASE/'output/grasp-solution.npz');H=s['H'];closed=s['fingers'];center=np.array([.25,.36,1.031]);target=np.array(json.loads((BASE/'output/grasp-solution.json').read_text())['grasp']['tip_targets_m'])
low=np.r_[[-.8,-1.,-.6,0,0],np.tile([-.35,0,0],4)];high=np.r_[[.8,1.3,1.3,1.6,1.5],np.tile([.35,1.65,1.9],4)]
f=closed.copy();poses=[];errs=[];gaps=np.linspace(0,.018,25)
for gap in gaps:
 goals=target.copy();goals[0,1]-=gap;goals[1:,1]+=gap
 def residual(x):
  tips,segs,_=h.hand_geometry(h.finger_pose(x),H);pts=[];margins=[]
  for aa,bb,name,k in segs:
   for u in [0,.25,.5,.75,1.]:
    pts.append(aa+(bb-aa)*u);margins.append((.008 if name=='Thumb' else .007) if k==2 and u>.5 else (.010 if name=='Thumb' else .009))
  d=np.abs(np.array(pts)-center)-.03;sdf=np.linalg.norm(np.maximum(d,0),axis=1)+np.minimum(d.max(axis=1),0)
  return np.r_[(tips-goals).ravel()*300,np.maximum(np.array(margins)-sdf,0)*500,(x-closed)*.06]
 result=least_squares(residual,f,bounds=(low,high),max_nfev=150,ftol=1e-8);f=result.x;poses.append(f.copy());tips,_,_=h.hand_geometry(h.finger_pose(f),H);errs.append(np.linalg.norm(tips-goals,axis=1).max())
np.savez(BASE/'output/finger-preshape.npz',gaps_m=gaps,fingers=poses,max_tip_errors_m=errs)
print('PRESHAPE',{'max_error_m':float(max(errs)),'closed_error_m':float(errs[0]),'open_error_m':float(errs[-1])},flush=True)
