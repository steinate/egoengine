"""USD MANO mesh + geometric arm preview, attached after recorder initialization.

Arm capsules are a debugging proxy, not a photorealistic body asset.
Use only with WorldRecorder step_replay=False. Scene units must be meters.
"""
import numpy as np

class HumanOverlay:
    def __init__(self, stage, mesh_npz, robot_roots=()):
        from pxr import UsdGeom,UsdShade,Sdf,Gf
        self.UsdGeom,self.Gf=UsdGeom,Gf
        self.data=np.load(mesh_npz,allow_pickle=False)
        self.roots=[stage.GetPrimAtPath(p) for p in robot_roots]
        if any(not p.IsValid() for p in self.roots):raise ValueError('Invalid robot root')
        root='/World/HumanReference'
        if stage.GetPrimAtPath(root).IsValid():raise ValueError('HumanReference already exists')
        UsdGeom.Xform.Define(stage,root)
        self.mesh=UsdGeom.Mesh.Define(stage,root+'/hand')
        f=self.data['faces']
        self.mesh.CreateFaceVertexCountsAttr(np.full(len(f),3,dtype=np.int32).tolist())
        self.mesh.CreateFaceVertexIndicesAttr(f.reshape(-1).tolist())
        self.mesh.CreateSubdivisionSchemeAttr('none')
        self.mesh.CreateDoubleSidedAttr(True)
        material=UsdShade.Material.Define(stage,root+'/Skin')
        shader=UsdShade.Shader.Define(stage,root+'/Skin/Shader')
        shader.CreateIdAttr('UsdPreviewSurface')
        shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set((.52,.29,.19))
        shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.5)
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface')
        UsdShade.MaterialBindingAPI.Apply(self.mesh.GetPrim()).Bind(material)
        self.arms=[]
        for name,radius in [('upper_arm',.045),('forearm',.033)]:
            cap=UsdGeom.Capsule.Define(stage,root+'/'+name)
            cap.CreateRadiusAttr(radius);cap.CreateAxisAttr('Z')
            xf=UsdGeom.Xformable(cap.GetPrim())
            self.arms.append((cap,xf.AddTranslateOp(),xf.AddOrientOp()))
            UsdShade.MaterialBindingAPI.Apply(cap.GetPrim()).Bind(material)

    def __call__(self, frame):
        if frame>=len(self.data['vertices']):raise IndexError('Human/robot frame counts differ')
        self.mesh.GetPointsAttr().Set(self.data['vertices'][frame].tolist())
        # Must hide AFTER original visibility restoration on every frame.
        for root in self.roots:self.UsdGeom.Imageable(root).MakeInvisible()
        points=[self.data[k][frame] for k in ('shoulder','elbow','wrist')]
        for (cap,trans,orient),a,b in zip(self.arms,points[:-1],points[1:]):
            delta=b-a;length=float(np.linalg.norm(delta))
            cap.GetHeightAttr().Set(max(length-2*cap.GetRadiusAttr().Get(),.001))
            trans.Set(self.Gf.Vec3d(*((a+b)/2).tolist()))
            q=self.Gf.Rotation(self.Gf.Vec3d(0,0,1),self.Gf.Vec3d(*(delta/length).tolist())).GetQuat()
            orient.Set(self.Gf.Quatf(q))
