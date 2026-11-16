import subprocess,json,hashlib
from pathlib import Path
root=Path('/vepfs/public/pengjiaqi/interndata-human-pair');base=root/'human-natural-v4';out=base/'delivery';N=1507
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
f=[]
for i,label in enumerate(['Before - human IK','After - continuous human IK']):
 f.append(f"[{i}:v]scale=960:540,pad=960:584:0:44:color=0x111827,drawtext=fontfile={font}:text='{label} | frame %{{n}}':x=14:y=10:fontcolor=white:fontsize=21[v{i}]")
f.append('[v0][v1]hstack=inputs=2[v]')
path=out/'front-before-after-full.mp4'
subprocess.run(['ffmpeg','-v','error','-y','-i',str(root/'human-stack-v3/delivery/human-front-full.mp4'),'-i',str(out/'human-front-full.mp4'),'-filter_complex',';'.join(f),'-map','[v]','-frames:v',str(N),'-r','15','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(path)],check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(path)]))['streams'][0]
assert int(probe['nb_read_frames'])==N and probe['r_frame_rate']=='15/1'
(out/'before-after-verification.json').write_text(json.dumps({'probe':probe,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
print('COMPARISON_DONE',probe)
