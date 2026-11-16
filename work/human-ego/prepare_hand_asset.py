"""Download the publicly released ManipNet hand asset and extract its rig.
Asset authors: He Zhang, Yuting Ye, Takaaki Shiratori, Taku Komura.
Source: https://github.com/cghezhang/ManipNet ; majority license CC-BY-NC.
Requires UnityPy and numpy. This does not download MANO or model weights.
"""
from pathlib import Path
import urllib.request
import numpy as np
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler

out=Path(__file__).resolve().parent
if (out.parent/'world-tracks.npz').exists():out=out.parent
url='https://raw.githubusercontent.com/cghezhang/ManipNet/b37d47f0e7bc4fc4ca9dda12c8c8685a5dce04ac/Data/HandModel/UnityPrefab/rightHandSkin.asset'
path=out/'rightHandSkin.asset'
if not path.exists():urllib.request.urlretrieve(url,path)
m=next(o for o in UnityPy.load(str(path)).objects if o.type.name=='Mesh').read()
h=MeshHandler(m);h.process()
v=np.asarray(h.m_Vertices)*.085
quads=np.asarray(h.m_IndexBuffer).reshape(-1,4)
faces=np.concatenate([quads[:,[0,1,2]],quads[:,[0,2,3]]])
bind=np.array([[[getattr(a,f'e{i}{j}') for j in range(4)] for i in range(4)] for a in m.m_BindPose])
np.savez(out/'hand-rig.npz',vertices=v,faces=faces,quads=quads,
         weights=h.m_BoneWeights,indices=h.m_BoneIndices,bind=bind)
print('Extracted',len(v),'vertices; 17 skinning entries; hand scaled to adult dimensions.')
