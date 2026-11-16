import json,subprocess,shutil,hashlib
from pathlib import Path
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');BASE=ROOT/'paired-human-ego';OUT=BASE/'delivery';OUT.mkdir(exist_ok=True)
render=json.loads((BASE/'render/verification.json').read_text());assert render['source_frames']==list(range(844)) and render['frames']==844
assert render['max_object_position_error_m']<1e-6 and render['max_object_rotation_error_rad']<1e-6
original=ROOT/'outputs41/official-dual-grasp/BananaBaseTask/split_aloha/stack_lift_cubes/two_lr/2026-11-12_09_43_18_286976/images.rgb.head/demo.mp4'
def run(args):subprocess.run(args,check=True)
run(['ffmpeg','-v','error','-y','-framerate','15','-start_number','0','-i',str(BASE/'render/ego/%04d.png'),'-frames:v','844','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'human-ego.mp4')])
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
fc=f"[0:v]scale=960:540,pad=960:584:0:44:color=0x111827,drawtext=fontfile={font}:text='Official robot | frame %{{n}}':x=20:y=10:fontcolor=white:fontsize=22[r];[1:v]scale=960:540,pad=960:584:0:44:color=0x111827,drawtext=fontfile={font}:text='Human ego | same source frame %{{n}}':x=20:y=10:fontcolor=white:fontsize=22[h];[r][h]hstack=inputs=2[v]"
run(['ffmpeg','-v','error','-y','-i',str(original),'-i',str(OUT/'human-ego.mp4'),'-filter_complex',fc,'-map','[v]','-frames:v','844','-r','15','-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'robot-human-synchronized.mp4')])
checks={}
for name in ['human-ego.mp4','robot-human-synchronized.mp4']:
 path=OUT/name;probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(path)]))['streams'][0];assert int(probe['nb_read_frames'])==844 and probe['r_frame_rate']=='15/1';checks[name]={'probe':probe,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
report=json.loads((OUT/'pair-verification.json').read_text());report['render_verification']=render;report['videos']=checks;(OUT/'pair-verification.json').write_text(json.dumps(report,indent=2))
shutil.copy(BASE/'retarget-report.json',OUT/'retarget-report.json');shutil.copy(BASE/'skin-cache/manifest.json',OUT/'skinning-verification.json');shutil.copy(BASE/'ego-visibility.json',OUT/'ego-visibility.json');shutil.copy(BASE/'render/ego/0843.png',OUT/'human-ego-tray-lift.png');shutil.copy(BASE/'render/ego/0140.png',OUT/'human-ego-left-grasp.png')
print('ENCODE_AND_VERIFY_DONE',json.dumps(checks),flush=True)
