"""Create an isolated task variant; do not edit the official task or skills."""
from pathlib import Path
import yaml
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair')
BASE=ROOT/'robot-stack-v2';BASE.mkdir(exist_ok=True)
ENGINE=ROOT/'src/InternDataEngine41'
source=ENGINE/'workflows/simbox/core/configs/tasks/basic/split_aloha/stack_cubes_lift/lr.yaml'
cfg=yaml.safe_load(source.read_text());task=cfg['tasks'][0]
task['data']['collect_info']='stack_verified_v2'
task['data']['max_episode_length']=5000
task['data']['language_instruction']='Place the left cube on the tray, stack the right cube on top of the left cube, then lift the tray with both arms while keeping the cubes stacked.'
task['data']['detailed_language_instruction']=task['data']['language_instruction']
seq=task['skills'][0]['split_aloha']
for side,index in [('left',0),('right',1)]:
    p=seq[index][side][-1]
    p['name']='stable_place'
    p.update(pre_place_z_offset=.17,hesitate_steps=15,gripper_change_steps=30,
             post_place_vector=[0,0,-.14],t_eps=.001,o_eps=.008,slow_factor=.45)
    if side=='right':
        p['objects']=['pick_object_right1','pick_object_left1']
        p['place_z_offset']=.031
        p['align_place_obj_axis']=[0,0,1]
    seq[index][side].append({'name':'gripper__action','gripper_state':1,'wait_steps':30})
for side in ['left','right']:
    seq[-1][side][0]['move_steps']=140
seq.append({side:[{'name':'gripper__action','gripper_state':-1,'wait_steps':60}] for side in ['left','right']})
(BASE/'task.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False))
p=yaml.safe_load((ENGINE/'configs/simbox/de_plan_with_render_template.yaml').read_text())
p['load_stage']['scene_loader']['args']['cfg_path']=str(BASE/'task.yaml')
p['load_stage']['layout_random_generator']['args'].update(random_num=1,strict_mode=False)
p['store_stage']['writer']['args']['output_dir']=str(BASE/'official-output')
(BASE/'pipeline.yaml').write_text(yaml.safe_dump(p,sort_keys=False))
print(BASE/'pipeline.yaml')
