"""Package reproducibility code and paired data; exclude supplier mesh assets."""
from pathlib import Path
import hashlib, json, shutil, zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

B = Path(__file__).resolve().parent
D = B / 'delivery'
report = json.loads((D / 'video-verification.json').read_text())
assert report['frames'] == 1507 and report['source_objects_unchanged']
shutil.copy2(B / 'README.txt', D / 'README.txt')
animation=np.load(B/'scan-animation.npz')
motion={}
for side in ['L','R']:
    delta=np.diff(animation[side+'_q'],axis=0)
    motion[side]={'max_joint_step_deg':float(np.rad2deg(abs(delta).max())), 'max_step_frame':int(np.unravel_index(abs(delta).argmax(),delta.shape)[0]+1)}
(D/'final-motion-report.json').write_text(json.dumps(motion,indent=2))
shutil.copy2(B/'native-hand-verification.json',D/'native-hand-verification.json')
for name in ['contact-schedule.json', 'robot-stack-validation.json',
             'robot-source-verification.json', 'scene-meta.json', 'events.json']:
    shutil.copy2(B / 'source' / name, D / name)

# Prove paired delivery still contains the exact arrays in the source NPZ.
paired = np.load(D / 'paired-world-trajectories.npz')
source = np.load(B / 'source/world-tracks.npz')
for key in source.files:
    assert np.array_equal(source[key], paired[key]), key
np.testing.assert_array_equal(paired['source_frame'], np.arange(1507))
np.testing.assert_allclose(paired['video_time_s'], np.arange(1507) / 15)
report['paired_arrays_equal_source'] = list(source.files)
report['asset'] = 'DRL native right-hand scan and original 8K diffuse; mirrored left; corrected UV V and dorsal/palmar alignment; unchanged Worker body'
report['status'] = 'complete_verified_render'
report['physical_rollout'] = False
previous = B.with_name('human-scan-v5')
old_pose = np.load(previous/'scan-animation.npz')
for side in ['L','R']:
    np.testing.assert_array_equal(animation[side+'_wrist_world'],old_pose[side+'_wrist_world'])
for name in ['ego-body-template.usdc','visual-body-template.usdc']:
    assert hashlib.sha256((B/name).read_bytes()).digest()==hashlib.sha256((previous/name).read_bytes()).digest()
report['actor_body_templates_identical_to_previous'] = True
report['wrist_trajectories_identical_to_previous'] = True
report['provenance'] = 'InternDataEngine official pipeline with prior task-local stable_place fixes; exact saved object replay'
report['limitations'] = [
    'Scan joint centres are estimated; anatomical and contact models are approximate.',
    'Contact reports sample representative frames, not continuous collision or force validation.',
    'Existing Worker body and upper-body trajectory are reused; CC5 was not acquired.',
    'Single scan mirrored for the opposite hand; texture does not include supplied normal or displacement maps.',
    'This is a research preview, not a claim of photorealism or a fully cleared training asset set.'
]
(D / 'completion-report.json').write_text(json.dumps(report, indent=2))

font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font = ImageFont.truetype(font_path, 18)
for side,source_name in [('back','plus_y'),('palm','minus_y')]:
    shutil.copy2(B/f'audit-{source_name}-native_fixed.png',D/f'native-scan-{side}.png')
comparison=Image.new('RGB',(1280,392),'#111827');draw=ImageDraw.Draw(comparison)
for index,(path,title) in enumerate([
    (previous/'delivery/ego-0137.png','Previous: UV and hand-side errors'),
    (B/'render/ego/0137.png','Corrected: native scan, same actor and frame 137')]):
    with Image.open(path) as im:comparison.paste(im.resize((640,360),Image.Resampling.LANCZOS),(index*640,32))
    draw.text((index*640+8,7),title,fill='white',font=font)
comparison.save(D/'native-hand-before-after.jpg',quality=95)
frames = [(0, 'Start'), (137, 'Left grasp'), (433, 'Left release'),
          (780, 'Right grasp'), (1044, 'Right release'),
          (1331, 'Tray grasp'), (1506, 'Final hold')]
for view in ['ego', 'front']:
    sheet = Image.new('RGB', (960, 4 * 302), '#111827')
    draw = ImageDraw.Draw(sheet)
    for index, (frame, label) in enumerate(frames):
        x = (index % 2) * 480; y = (index // 2) * 302
        with Image.open(B / f'render/{view}/{frame:04d}.png') as im:
            sheet.paste(im.resize((480, 270), Image.Resampling.LANCZOS), (x, y + 32))
        draw.text((x + 8, y + 7), f'{label} | frame {frame} | {frame / 15:.2f}s', fill='white', font=font)
    sheet.save(D / f'{view}-complete-contact-sheet.jpg', quality=94)

with zipfile.ZipFile(D / 'paired-data-and-code.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for pattern in ['*.py', '*.sh']:
        for path in sorted(B.glob(pattern)):
            if path.name in ['render_perf.py', 'render-before-persistent.py', 'fix_native_uv.py']:
                continue
            archive.write(path, 'code/' + path.name)
    for path in sorted(D.iterdir()):
        if path.suffix in ['.json', '.txt', '.npz'] and path.name != 'checksums.json':
            archive.write(path, path.name)
    archive.write(B / 'source/world-tracks.npz', 'source/world-tracks.npz')

checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(D.iterdir()) if p.is_file() and p.name != 'checksums.json'}
(D / 'checksums.json').write_text(json.dumps(checksums, indent=2))
print('DELIVERY_PACKAGED', len(checksums), 'files', flush=True)
