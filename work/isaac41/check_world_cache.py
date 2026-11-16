"""Regression: replacing a nonempty world must remove cached GPU obstacles."""
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'runtime41/extscache/omni.warp.core-1.2.1'))
from curobo.types.base import TensorDeviceType
from curobo.geom.types import WorldConfig,Cuboid
from curobo.geom.sdf.world import WorldCollisionConfig
from curobo.geom.sdf.world_mesh import WorldMeshCollision
c=WorldMeshCollision(WorldCollisionConfig(tensor_args=TensorDeviceType(),cache={'obb':4,'mesh':4}))
cube=Cuboid(name='regression_box',pose=[.4,0,.1,1,0,0,0],dims=[.04,.04,.04])
w=WorldConfig(cuboid=[cube]);mesh=w.get_mesh_world()
both=WorldConfig(cuboid=[cube],mesh=mesh.mesh)
def counts():return {'mesh':int(c._mesh_tensor_list[2].sum()),'cuboid':int(c._cube_tensor_list[2].sum())}
c.load_collision_model(both);before=counts()
ptrs=[x.data_ptr() for x in c._mesh_tensor_list+c._cube_tensor_list]
c.load_collision_model(WorldConfig());stale=counts()
c.clear_cache();c.load_collision_model(WorldConfig());after=counts()
same_ptrs=ptrs==[x.data_ptr() for x in c._mesh_tensor_list+c._cube_tensor_list]
assert before=={'mesh':1,'cuboid':1} and stale==before
assert after=={'mesh':0,'cuboid':0} and same_ptrs
result={'loaded':before,'unpatched_empty_update':stale,'clear_then_empty_update':after,'cuda_buffer_addresses_preserved':same_ptrs,'passed':True}
(root/'outputs41/world-cache-regression.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
