"""Map legacy CC3 PBR inputs to Isaac 4.1 OmniPBR, retaining source textures."""

from pxr import UsdShade, UsdGeom, Sdf, Gf


def repair_materials(stage, root="/World/Human"):
    report = []
    for p in list(stage.Traverse()):
        if (
            str(p.GetPath()).startswith(root)
            and p.GetTypeName() == "GeomSubset"
            and p.GetRelationship("material:binding")
        ):
            UsdGeom.Subset(p).CreateFamilyNameAttr("materialBind")
            UsdGeom.Subset.SetFamilyType(
                UsdGeom.Imageable(p.GetParent()), "materialBind", "partition"
            )
            UsdShade.MaterialBindingAPI.Apply(p)
    for p in list(stage.Traverse()):
        if not str(p.GetPath()).startswith(root) or p.GetTypeName() != "Material":
            continue
        old = [c for c in p.GetChildren() if c.GetTypeName() == "Shader"]
        if not old:
            continue
        old = old[0]
        diffuse = old.GetAttribute("inputs:diffuse_texture").Get()
        if diffuse is None:
            continue
        m = UsdShade.Material(p)
        s = UsdShade.Shader.Define(stage, str(p.GetPath()) + "/IsaacPBR")
        s.CreateImplementationSourceAttr("sourceAsset")
        s.SetSourceAsset(Sdf.AssetPath("OmniPBR.mdl"), "mdl")
        s.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
        s.CreateOutput("out", Sdf.ValueTypeNames.Token)
        files = {}
        for n in [
            "diffuse_texture",
            "normalmap_texture",
            "reflectionroughness_texture",
            "metallic_texture",
            "ao_texture",
        ]:
            value = old.GetAttribute("inputs:" + n).Get()
            if value is not None:
                resolved = value.resolvedPath or value.path
                s.CreateInput(n, Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(resolved))
                files[n] = resolved
        s.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1.0))
        s.CreateInput("metallic_constant", Sdf.ValueTypeNames.Float).Set(0.0)
        s.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(0.45)
        for o in ["surface", "displacement", "volume"]:
            m.CreateOutput("mdl:" + o, Sdf.ValueTypeNames.Token).ConnectToSource(
                s.ConnectableAPI(), "out"
            )
        report.append({"material": str(p.GetPath()), "textures": files})
    return report
