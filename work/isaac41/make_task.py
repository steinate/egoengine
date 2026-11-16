"""Derive a bounded single-arm pick/place task from the upstream Franka task."""
import copy
from pathlib import Path
import yaml

def main():
    root=Path(__file__).resolve().parents[1]
    base=root/'workflows/simbox/core/configs/tasks/pick_and_place/franka/single_pick/omniobject3d-bottle.yaml'
    doc=yaml.safe_load(base.read_text());t=doc['tasks'][0]
    obj=t['objects'][0]
    obj.update(apply_randomization=False,orientation_mode='keep',legacy_task_units=False)
    t.pop('distractors',None)
    t['robots'][0]['left_joint_home_std']=[0.]*7
    t['regions'][0]['random_config']['pos_range']=[[-.10,-.20,0.],[-.08,-.18,0.]]
    t['regions'][0]['random_config']['yaw_rotation']=[0.,0.]
    t['data'].update(task_dir='human_pair/franka_bottle_pick_place',
        language_instruction='Pick up the bottle and place it on the right side of the table.',
        detailed_language_instruction='Pick, lift, move right, release on the table, and retreat.',max_episode_length=800,
        export_replay_scene=True)
    skills=t['skills'][0]['franka'][0]['left']
    skills[0].update(test_mode="forward",filter_z_dir=["downward",45],post_grasp_offset_min=.12,post_grasp_offset_max=.12,gripper_change_steps=15)
    skills.append(dict(name='place',objects=['pick_object_left','table'],place_direction='vertical',
        x_ratio_range=[.62,.66],y_ratio_range=[.30,.35],pre_place_z_offset=.20,place_z_offset=.045,
        position_constraint='object',keep_grasp_orientation=True,ignore_substring=['pick_object_left'],
        post_place_vector=[0.,0.,-.12],gripper_change_steps=20,success_mode='xybbox'))
    skills.append(dict(name='heuristic__skill',mode='home',gripper_state=1.))
    for c in t['cameras']:c['apply_randomization']=False
    target=root/'human_pair/configs';target.mkdir(exist_ok=True)
    arena=yaml.safe_load((root/t['arena_file']).read_text())
    for fixture in arena['fixtures']:fixture.pop('texture',None)
    arena_path=target/'neutral_arena.yaml';arena_path.write_text(yaml.safe_dump(arena,sort_keys=False))
    t['arena_file']=str(arena_path)
    t['env_map']['intensity_range']=[1000,1000]
    task_path=target/'franka_bottle_pick_place.yaml';task_path.write_text(yaml.safe_dump(doc,sort_keys=False))
    for kind in ['plan','render']:
        cfg=yaml.safe_load((root/f'configs/simbox/de_{kind}_template.yaml').read_text())
        cfg['name']='human_pair_'+kind
        cfg['load_stage']['scene_loader']['args']['cfg_path']=str(task_path)
        cfg['load_stage']['scene_loader']['args']['simulator']['multi_gpu']=False
        randomizer=cfg['load_stage']['layout_random_generator']['args']
        deploy=root.parents[1]
        if kind=='plan':randomizer.update(random_num=1,strict_mode=False)
        else:randomizer['input_dir']=str(deploy/'outputs41/plan/BananaBaseTask/plan')
        writer=cfg['store_stage']['writer']['args'];writer['batch_async']=False
        writer['seq_output_dir' if kind=='plan' else 'output_dir']=str(deploy/'outputs41'/kind)
        (target/f'{kind}.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False))
    print(task_path)

if __name__=='__main__':main()
