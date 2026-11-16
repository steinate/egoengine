"""Create a contact sheet and check decoded video content against trajectory."""
import argparse,json
from pathlib import Path
import numpy as np
import imageio.v2 as imageio
from PIL import Image,ImageDraw,ImageFont
p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('tracks');a=p.parse_args()
v=Path(a.video);d=np.load(a.tracks);xyz=d['object_T'][:,:3,3];n=len(xyz)
cmd=d['gripper_open_command'].reshape(n,-1)[:,0];closed=np.flatnonzero(cmd<.5)
indices=[0,int(closed[0]),int(np.argmax(xyz[:,2])),int(closed[-1]),min(n-1,int(closed[-1])+20),n-1]
labels=['Start','Grasp','Lift / transfer','Before release','Release / retreat','End']
reader=imageio.get_reader(v);meta=reader.get_meta_data();frames=reader.count_frames()
canvas=Image.new('RGB',(1280,3*398),(24,28,32));draw=ImageDraw.Draw(canvas)
try:font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
except OSError:font=ImageFont.load_default()
rgb=[]
for j,(i,label) in enumerate(zip(indices,labels)):
    im=reader.get_data(i);rgb.append(im);tile=Image.fromarray(im).resize((640,360))
    x=(j%2)*640;y=(j//2)*398;canvas.paste(tile,(x,y))
    draw.text((x+12,y+367),f'{label} | frame {i} | {i*float(d["dt"]):.2f} s',fill='white',font=font)
canvas.save(v.with_name(v.stem+'-contact-sheet.jpg'),quality=94)
result={'decoded_frames':frames,'trajectory_frames':n,'fps':meta['fps'],'size':list(meta['size']),
        'sample_frame_indices':indices,'sample_spatial_std':[float(f.std()) for f in rgb],
        'start_end_mean_absolute_pixel_difference':float(np.abs(rgb[-1].astype(float)-rgb[0]).mean()),
        'passed':frames==n and min(float(f.std()) for f in rgb)>5}
v.with_name(v.stem+'-content-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
assert result['passed']
