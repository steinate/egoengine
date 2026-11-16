"""Task diagnostics for initial scene / grasp calibration, without changing policy."""
import json
from pathlib import Path
import numpy as np

def install(output_dir):
    import workflows
    original_import=workflows.import_extensions
    def import_extensions(kind):
        original_import(kind)
        from workflows.base import NimbusWorkFlow
        SimBoxDualWorkFlow=NimbusWorkFlow.workflows[kind]
        original=SimBoxDualWorkFlow.generate_seq
        def generate(self):
            out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
            result={'robots':{},'objects':{}}
            for name,r in self.task.robots.items():
                result['robots'][name]={'pose':[np.asarray(x).tolist() for x in r.get_world_pose()],
                    'joints':r.get_joint_positions().tolist()}
            for name,o in self.task.objects.items():
                result['objects'][name]={'pose':[np.asarray(x).tolist() for x in o.get_world_pose()],
                    'scale':o.get_local_scale().tolist()}
            from core.skills.pick import Pick
            p=Pick(self.task.robots['franka'],self.controllers['franka']['left'],self.task,
                   self.task_cfg['skills'][0]['franka'][0]['left'][0])
            targets=p.get_ee_poses('armbase')
            result['grasp_translation_range']=[targets[:,:3,3].min(0).tolist(),targets[:,:3,3].max(0).tolist()]
            ctrl=self.controllers['franka']['left']
            result['current_ee_in_base']=[np.asarray(x).tolist() for x in ctrl.get_ee_pose()]
            original_plan=ctrl.plan
            plan_calls=0
            def checked_plan(*a,**kw):
                nonlocal plan_calls
                if plan_calls==0:
                    print('MOTION_OBSTACLES',{k:[o.name for o in (getattr(ctrl.world_cfg,k,None) or [])] for k in ['mesh','cuboid','sphere','capsule']},flush=True)
                plan_calls+=1
                outcome=original_plan(*a,**kw)
                if not outcome.success.any():
                    print('MOTION_FAILURE',str(outcome.status),'target',str(a[0]),flush=True)
                return outcome
            ctrl.plan=checked_plan
            print('TASK_DIAGNOSTICS',json.dumps(result),flush=True)
            (out/'initial-scene.json').write_text(json.dumps(result,indent=2))
            self.stage.Flatten().Export(str(out/'initial-scene.usdc'))
            import imageio.v2 as imageio
            for _ in range(10):self.world.render()
            for name,c in self.task.cameras.items():
                rgb=c.get_rgba()
                if rgb.size:imageio.imwrite(out/(name+'.png'),rgb.astype(np.uint8))
            try:
                return original(self)
            finally:
                # Diagnostic plans may be failures: never put them in accepted output.
                self.save_seq(str(out/'diagnostic-episode'))
        SimBoxDualWorkFlow.generate_seq=generate
    workflows.import_extensions=import_extensions
