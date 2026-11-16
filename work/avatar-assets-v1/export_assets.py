"""Independent body-size IK and finger-deformation smoke test; no task replay."""
import bpy,math,json,numpy as np,os
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
B=Path('/vepfs/public/pengjiaqi/interndata-human-pair/avatar-assets-v1');out=B/'usd';out.mkdir(exist_ok=True)
reports=[]
def worldhead(a,p):return a.matrix_world@p.head
def rotate_world(a,p,Q):
    W=a.matrix_world@p.matrix;T=W.translation.copy();W=Q.to_matrix().to_4x4()@W;W.translation=T;p.matrix=a.matrix_world.inverted()@W;bpy.context.view_layer.update()
def align(a,p,child,target):
    old=worldhead(a,child)-worldhead(a,p);desired=target-worldhead(a,p)
    rotate_world(a,p,old.normalized().rotation_difference(desired.normalized()))
for file in sorted((B/'converted').glob('*.blend')):
    if os.environ.get('ASSET_ONLY') and file.stem!=os.environ['ASSET_ONLY']:continue
    bpy.ops.wm.open_mainfile(filepath=str(file));name=file.stem;scan=name.startswith('rp_')
    arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');arm.animation_data_clear();meshes=[o for o in bpy.data.objects if o.type=='MESH']
    for o in meshes:
        o.animation_data_clear()
        for f in o.data.polygons:f.use_smooth=True
    if scan:
        folder=next((B/'assets/renderpeople').glob(name+'_FBX'));dif=next((folder/'tex').glob('*_dif.jpg'));normal=next((folder/'tex').glob('*_norm.jpg'))
        mat=bpy.data.materials.new(name+'_PBR');mat.use_nodes=True;nodes=mat.node_tree.nodes;links=mat.node_tree.links;bsdf=nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.58
        tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(dif),check_existing=True);links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
        tx=nodes.new('ShaderNodeTexImage');tx.image=bpy.data.images.load(str(normal),check_existing=True);tx.image.colorspace_settings.name='Non-Color';nm=nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.7;links.new(tx.outputs['Color'],nm.inputs['Color']);links.new(nm.outputs['Normal'],bsdf.inputs['Normal'])
        for o in meshes:o.data.materials.clear();o.data.materials.append(mat)
    if not scan:
        for o in meshes:
            if o.data.shape_keys:
                mixed=o.shape_key_add(name='FrozenPhenotype',from_mix=True);v=np.array([list(p.co) for p in mixed.data]);o.shape_key_clear()
                for vert,co in zip(o.data.vertices,v):vert.co=co
        bpy.context.view_layer.update()
        points=np.array([list(o.matrix_world@v.co) for o in meshes for v in o.data.vertices]);scale=1.75/(points[:,2].max()-points[:,2].min());arm.scale*=scale;bpy.context.view_layer.update()
    coords=np.array([list(o.matrix_world@v.co) for o in meshes for v in o.data.vertices]);height=coords[:,2].max();errors=[];hands=[]
    def names(side):
        if scan:
            s=side.lower();return {'upper':'upperarm_'+s,'lower':'lowerarm_'+s,'hand':'hand_'+s,'fingers':[[f'{f}_{j:02d}_{s}' for j in [1,2,3]] for f in ['thumb','index','middle','ring','pinky']]}
        prefix='mixamorig:'+('Left' if side=='L' else 'Right');return {'upper':prefix+'Arm','lower':prefix+'ForeArm','hand':prefix+'Hand','fingers':[[prefix+'Hand'+f+str(j) for j in [1,2,3]] for f in ['Thumb','Index','Middle','Ring','Pinky']]}
    rignames={s:names(s) for s in ['L','R']};weights={}
    for side,n in rignames.items():
        for fn in sum(n['fingers'],[]):
            weights[fn]=sum(sum(1 for v in o.data.vertices if any(g.group==o.vertex_groups[fn].index and g.weight>1e-5 for g in v.groups)) for o in meshes if fn in o.vertex_groups)
    bpy.context.scene.frame_start=0;bpy.context.scene.frame_end=60;bpy.context.scene.render.fps=15
    for i in range(61):
        bpy.context.scene.frame_set(i)
        for p in arm.pose.bones:p.rotation_mode='QUATERNION';p.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update();phase=math.sin(math.pi*i/60)**2;frame_hands=[]
        for side,sign in [('L',1),('R',-1)]:
            n=rignames[side];U=arm.pose.bones[n['upper']];E=arm.pose.bones[n['lower']];H=arm.pose.bones[n['hand']]
            S=worldhead(arm,U);e=worldhead(arm,E);w=worldhead(arm,H);l1=(e-S).length;l2=(w-e).length
            target=Vector((sign*.22,-.30-.06*phase,height*.61));d=target-S;dist=d.length;u=d.normalized();dc=min(dist,l1+l2-.003)
            if dc<dist:target=S+u*dc
            along=(l1*l1-l2*l2+dc*dc)/(2*dc);bend=math.sqrt(max(0,l1*l1-along*along));pole=Vector((sign*.85,-.10,-.5));v=(pole-u*pole.dot(u)).normalized();elbow=S+u*along+v*bend
            align(arm,U,E,elbow);align(arm,E,H,target)
            F=n['fingers'];I=worldhead(arm,arm.pose.bones[F[1][0]]);P=worldhead(arm,arm.pose.bones[F[4][0]]);M=worldhead(arm,arm.pose.bones[F[2][0]]);forward=(M-worldhead(arm,H)).normalized();normal=((I-P).cross(forward)*(-sign)).normalized();normal=(normal-forward*normal.dot(forward)).normalized()
            tf=Vector((0,-1,-.10)).normalized();tn=Vector((0,0,-1));tn=(tn-tf*tn.dot(tf)).normalized()
            old=Matrix((forward,normal,forward.cross(normal))).transposed();new=Matrix((tf,tn,tf.cross(tn))).transposed();rotate_world(arm,H,(new@old.transposed()).to_quaternion())
            for fi,chain in enumerate(F):
                for j,bn in enumerate(chain):
                    pb=arm.pose.bones[bn];direction=(arm.matrix_world.to_3x3()@(pb.tail-pb.head)).normalized();axis=direction.cross(tn).normalized();angle=math.radians(([18,35,30] if fi==0 else [40,65,40])[j])*phase
                    rotate_world(arm,pb,Quaternion(axis,angle))
            errors.append((worldhead(arm,H)-target).length);frame_hands.append(list(worldhead(arm,H)))
        for pb in arm.pose.bones:
            pb.keyframe_insert(data_path='location',frame=i);pb.keyframe_insert(data_path='rotation_quaternion',frame=i);pb.keyframe_insert(data_path='scale',frame=i)
        hands.append(frame_hands)
    bpy.context.scene.frame_set(30)
    assert max(errors)<.002,(name,max(errors))
    bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{name}-driven.blend'))
    dest=out/name;dest.mkdir(exist_ok=True)
    bpy.ops.wm.usd_export(filepath=str(dest/'rigged.usdc'),export_animation=True,export_armatures=True,only_deform_bones=False,export_shapekeys=False,export_materials=True,export_textures=True,relative_paths=True,root_prim_path='/Avatar',export_lights=False,export_cameras=False)
    r={'name':name,'height_m':float(height),'bones':len(arm.data.bones),'frames':61,'fps':15,'max_independent_arm_ik_error_m':max(errors),'finger_weighted_vertices':weights,'hand_world':hands,'rig_map':rignames,'usd':str(dest/'rigged.usdc'),'purpose':'Standalone asset appearance / articulation preview; not a replacement task rollout or training dataset.'}
    reports.append(r);print('EXPORTED',name,'bones',r['bones'],'max_IK',max(errors),'finger_weight_min',min(weights.values()),flush=True)
if os.environ.get('ASSET_ONLY'):
    previous=json.loads((B/'asset-drive-verification.json').read_text());replace={r['name']:r for r in reports};reports=[replace.get(r['name'],r) for r in previous]
(B/'asset-drive-verification.json').write_text(json.dumps(reports,indent=2))
