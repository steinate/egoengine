import json,subprocess,hashlib,shutil
from pathlib import Path
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');BASE=ROOT/'paired-human-ego';OUT=BASE/'fullbody-delivery';OUT.mkdir(exist_ok=True)
r=json.loads((BASE/'fullbody-render/verification.json').read_text());prior=json.loads((BASE/'render/verification.json').read_text())
assert r['source_frames']==list(range(844)) and r['source_animation_sha256']==prior['source_animation_sha256']
assert r['max_object_position_error_m']<1e-6 and r['max_object_rotation_error_rad']<1e-6
original=ROOT/'outputs41/official-dual-grasp/BananaBaseTask/split_aloha/stack_lift_cubes/two_lr/2026-11-12_09_43_18_286976/images.rgb.head/demo.mp4'
human=BASE/'delivery/human-ego.mp4'
def run(args):subprocess.run(args,check=True)
run(['ffmpeg','-v','error','-y','-framerate','15','-i',str(BASE/'fullbody-render/fullbody/%04d.png'),'-frames:v','844','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'human-third-person-fullbody.mp4')])
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';filters=[]
for i,label in enumerate(['Official robot','Human ego','Human full body']):
 filters.append(f"[{i}:v]scale=960:540,pad=960:584:0:44:color=0x111827,drawtext=fontfile={font}:text='{label} | frame %{{n}}':x=20:y=10:fontcolor=white:fontsize=22[v{i}]")
filters.append('[v0][v1][v2]hstack=inputs=3[v]')
run(['ffmpeg','-v','error','-y','-i',str(original),'-i',str(human),'-i',str(OUT/'human-third-person-fullbody.mp4'),'-filter_complex',';'.join(filters),'-map','[v]','-frames:v','844','-r','15','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'robot-ego-fullbody-synchronized.mp4')])
checks={}
for name in ['human-third-person-fullbody.mp4','robot-ego-fullbody-synchronized.mp4']:
 path=OUT/name;probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(path)]))['streams'][0];assert int(probe['nb_read_frames'])==844 and probe['r_frame_rate']=='15/1';checks[name]={'probe':probe,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
r['videos']=checks;r['same_human_animation_as_previous_ego']=True
(OUT/'fullbody-verification.json').write_text(json.dumps(r,indent=2))
shutil.copy(BASE/'fullbody-render/fullbody/0550.png',OUT/'fullbody-frame-550.png')
print('FULLBODY_DONE',json.dumps(checks),flush=True)
