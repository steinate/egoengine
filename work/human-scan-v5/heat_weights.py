"""Compute smooth anatomical skin weights with Blender bone heat diffusion."""
import bpy,numpy as np,json
from pathlib import Path
B=Path('/vepfs/public/pengjiaqi/interndata-human-pair/human-scan-v5');a=np.load(B/'rig-input.npz')
bpy.ops.wm.read_factory_settings(use_empty=True);m=bpy.data.meshes.new('Scan');m.from_pydata(a['points'].tolist(),[],a['faces'].tolist());m.update();o=bpy.data.objects.new('Scan',m);bpy.context.collection.objects.link(o)
arm=bpy.data.armatures.new('AnatomicalHand');obj=bpy.data.objects.new('AnatomicalHand',arm);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
fore=arm.edit_bones.new('B16');fore.head=(0,-.055,0);fore.tail=(0,0,0)
wrist=arm.edit_bones.new('B00');wrist.head=(0,0,0);wrist.tail=(0,.065,.012);wrist.parent=fore
for f in range(5):
 prev=wrist
 for k in range(3):
  bone=arm.edit_bones.new(f'B{1+f*3+k:02d}');bone.head=a['joints'][f,k];bone.tail=a['joints'][f,k+1];bone.parent=prev;bone.use_connect=k>0;prev=bone
bpy.ops.object.mode_set(mode='OBJECT');o.select_set(True);bpy.context.view_layer.objects.active=obj
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
weights=np.zeros((len(m.vertices),17),np.float32);mapping={g.index:int(g.name[1:]) for g in o.vertex_groups}
for vertex in m.vertices:
 for group in vertex.groups:weights[vertex.index,mapping[group.group]]=group.weight
assert np.min(weights.sum(1))>.5,float(weights.sum(1).min())
weights/=weights.sum(1,keepdims=True);np.savez_compressed(B/'heat-weights.npz',weights=weights)
bpy.ops.wm.save_as_mainfile(filepath=str(B/'scan-rigged.blend'))
print('HEAT_WEIGHTS_DONE',len(weights),'influences',int((weights>1e-4).sum()),flush=True)
