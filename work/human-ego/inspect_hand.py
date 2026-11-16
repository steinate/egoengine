import UnityPy, numpy as np, json
from UnityPy.helpers.MeshHelper import MeshHandler
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

m = next(iter(UnityPy.load("work/human-ego/rightHandSkin.asset").objects)).read()
h = MeshHandler(m)
h.process()
v = np.array(h.m_Vertices) * 0.085
quads = np.array(h.m_IndexBuffer).reshape(-1, 4)
f = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
p = json.load(open("work/human-ego/Hands.prefab.json"))
rend = next(
    o["data"]
    for o in p.values()
    if o["type"] == "SkinnedMeshRenderer" and o["data"]["m_Mesh"]["m_FileID"] == 3
)
B = np.array([[[getattr(a, f"e{i}{j}") for j in range(4)] for i in range(4)] for a in m.m_BindPose])
G = np.linalg.inv(B)
pts = G[:, :3, 3] * 0.085
for i, b in enumerate(rend["m_Bones"]):
    t = p[str(b["m_PathID"])]["data"]
    name = p[str(t["m_GameObject"]["m_PathID"])]["data"]["m_Name"]
    print(i, name, np.round(pts[i], 3))
fig = plt.figure(figsize=(12, 4))
for k, (el, az) in enumerate([(85, -90), (0, -90), (20, 40)]):
    ax = fig.add_subplot(1, 3, k + 1, projection="3d")
    ax.add_collection3d(
        Poly3DCollection(
            v[f], facecolor=[0.7, 0.45, 0.32], edgecolor=[0.2, 0.1, 0.1], linewidth=0.1
        )
    )
    ax.scatter(*pts.T, c="r")
    for i, pt in enumerate(pts):
        ax.text(*pt, str(i), size=6)
    ax.set(
        xlim=(-0.02, 0.20),
        ylim=(-0.11, 0.11),
        zlim=(-0.1, 0.12),
        xlabel="X",
        ylabel="Y",
        zlabel="Z",
    )
    ax.view_init(el, az)
plt.savefig("work/human-ego/rest-hand.png", dpi=150)
np.savez(
    "work/human-ego/hand-rig.npz",
    vertices=v,
    faces=f,
    quads=quads,
    weights=h.m_BoneWeights,
    indices=h.m_BoneIndices,
    bind=B,
)
