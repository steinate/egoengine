"""Engine entrypoint with task-owned Kit logs/caches and explicit random seed."""
import argparse,sys
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--seed',type=int,default=42)
ap.add_argument('--diagnostics',action='store_true')
args=ap.parse_args()
root=Path(__file__).resolve().parents[3]
sys.argv=[sys.argv[0],'--allow-root','--portable-root',str(root/'cache41/kit'),f'--/log/file={root}/logs41/kit-engine.log',
          f'--/structuredLog/logDirectory={root}/logs41/structured',
          f'--/app/userConfigPath={root}/cache41/user.config.json']
from nimbus.utils.utils import init_env
init_env()
from nimbus.utils.config_processor import ConfigProcessor
from nimbus.utils.flags import set_debug_mode,set_random_seed
from nimbus import run_data_engine
from human_pair.diagnostics import install
if args.diagnostics:install(root/'outputs41/task-diagnostics')
set_debug_mode(True);set_random_seed(args.seed)
config=ConfigProcessor().process_config(args.config,cli_args=[])
run_data_engine(config,args.seed)
