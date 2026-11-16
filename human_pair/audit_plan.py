"""Inspect a trusted engine plan pickle without importing Isaac Sim.

Never use this on untrusted pickle files. Public LeRobot files are not plans.
"""
import argparse,json,pickle
from pathlib import Path

def inspect(path):
    cfg_b,rec_b,log_b=pickle.loads(Path(path).read_bytes())
    cfg,rec,log=map(pickle.loads,(cfg_b,rec_b,log_b))
    return {'format':'InternDataEngine plan tuple','mode':rec.get('mode','prim_pose'),
        'num_steps':rec['num_steps'],'prim_paths':rec.get('prim_paths'),
        'legacy_order_only': 'prim_paths' not in rec,
        'task':cfg.get('task'),'objects':[{k:o.get(k) for k in ['name','path','scale','prim_path_child']} for o in cfg.get('objects',[])],
        'object_log_keys':{r:list(v) for r,v in log.get('object_data_logger',{}).items()},
        'proprio_keys':{r:list(v) for r,v in log.get('proprio_data_logger',{}).items()}}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('plan');args=ap.parse_args()
    print(json.dumps(inspect(args.plan),indent=2,ensure_ascii=False))
