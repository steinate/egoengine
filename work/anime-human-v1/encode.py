"""Encode only complete verified 1507-frame paired videos."""
import json,hashlib,subprocess,shutil,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageOps
B=Path(__file__).resolve().parent;D=B/'delivery';D.mkdir(exist_ok=True);N=1507
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
motion=json.loads((B/'motion-verification.json').read_text());assert motion['source_objects_bitwise_equal']
parts=[json.loads((B/'render'/f'verification-{v}-full.json').read_text()) for v in ['ego','front']]
for p in parts:
 assert p['source_frames']==list(range(N))
 assert p['animation_sha256']==sha(B/'anime-animation.npz')==motion['animation_sha256']
 assert p['render_script_sha256']==sha(B/'render.py')
 assert p['max_object_position_error_m']<1e-6 and p['max_object_rotation_error_rad']<1e-6
def run(args):subprocess.run(args,check=True)
for v in ['ego','front']:
 assert sorted(int(p.stem) for p in (B/'render'/v).glob('*.png'))==list(range(N))
 run(['ffmpeg','-v','error','-y','-framerate','15','-i',str(B/f'render/{v}/%04d.png'),'-frames:v',str(N),'-c:v','libx264','-preset','medium','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(D/f'amber-{v}-full.mp4')])
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';filters=[]
for i,label in enumerate(['Source robot | original episode','Amber ego | native rig IK','Amber front | same timeline']):
 filters.append(f"[{i}:v]scale=960:540,pad=960:584:0:44:color=0x111827,drawtext=fontfile={font}:text='{label} | %{{n}}':x=14:y=10:fontcolor=white:fontsize=20[v{i}]")
filters.append('[v0][v1][v2]hstack=inputs=3[v]')
run(['ffmpeg','-v','error','-y','-i',str(B/'source/robot-full.mp4'),'-i',str(D/'amber-ego-full.mp4'),'-i',str(D/'amber-front-full.mp4'),'-filter_complex',';'.join(filters),'-map','[v]','-frames:v',str(N),'-r','15','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(D/'robot-ego-front-full.mp4')])
videos={}
for p in D.glob('*.mp4'):
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(p)]))['streams'][0]
 assert int(probe['nb_read_frames'])==N and probe['r_frame_rate']=='15/1'
 videos[p.name]={'probe':probe,'sha256':sha(p)}
data=np.load(B/'anime-animation.npz');tracks=dict(np.load(B/'source/world-tracks.npz'))
for k in ['source_frame','video_time_s','L_q','R_q','L_canonical_wrist_world','R_canonical_wrist_world','camera_world_usd','elbows','torso_lean_rad','avatar_root_world','nominal_support_plane_z_m']:tracks[k]=data[k]
tracks['ego_camera_K']=np.array(parts[0]['camera_K']);tracks['front_camera_world_usd']=np.array(parts[0]['front_camera_world_usd']);tracks['front_camera_K']=np.array([[1280*24/36,0,640],[0,1280*24/36,360],[0,0,1]])
np.savez_compressed(D/'paired-world-trajectories.npz',**tracks)
for name in ['ik-report.json','motion-verification.json','asset-audit.json','provenance.json','camera-framing.json','README.txt']:shutil.copy2(B/name,D/name)
shutil.copy2(B/'source/contact-schedule.json',D/'contact-schedule.json');shutil.copy2(B/'source/robot-stack-validation.json',D/'robot-stack-validation.json')
for v in ['ego','front']:
 frames=[0,137,433,780,1044,1331,1506];sheet=Image.new('RGB',(3*480,3*290),'#111827');draw=ImageDraw.Draw(sheet)
 for k,i in enumerate(frames):
  image=Image.open(B/f'render/{v}/{i:04d}.png');image.thumbnail((480,270));x=(k%3)*480;y=(k//3)*290;sheet.paste(image,(x,y));draw.text((x+10,y+272),f'{v} | source frame {i} | {i/15:.2f}s',fill='white')
 sheet.save(D/f'{v}-complete-contact-sheet.jpg',quality=92)
 for i in [137,780,1331,1506]:shutil.copy2(B/f'render/{v}/{i:04d}.png',D/f'{v}-{i:04d}.png')
report={'frames':N,'fps':15,'duration_s':N/15,'videos':videos,'renders':parts,'motion':motion,
 'source_scene_sha256':sha(B/'source/source-scene.usdc'),'source_robot_sha256':sha(B/'source/robot-full.mp4')}
(D/'video-verification.json').write_text(json.dumps(report,indent=2))
with zipfile.ZipFile(D/'trajectories-and-code.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in B.glob('*.py'):z.write(p,'code/'+p.name)
 for p in B.glob('*.sh'):z.write(p,'code/'+p.name)
 for p in D.iterdir():
  if p.suffix in ['.npz','.json','.txt']:z.write(p,'data/'+p.name)
(D/'checksums.json').write_text(json.dumps({p.name:sha(p) for p in D.iterdir() if p.name!='checksums.json'},indent=2))
print('FULL_PAIR_COMPLETE',json.dumps(videos),flush=True)
