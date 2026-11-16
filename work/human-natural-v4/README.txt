Human natural v4 — complete paired stable-stack episode

Remote working directory:
/vepfs/public/pengjiaqi/interndata-human-pair/human-natural-v4

The source is the verified 1507-frame / 15 fps episode in ../human-stack-v3/source.
Objects and timeline are copied exactly. The robot episode was generated with
InternDataEngine's official pipeline and documented task-local stable_place fixes.
The human is an independent IK retargeting of object contacts, not a new PhysX
human grasp rollout. Final task: stack cubes in tray, retract, lift tray, hold.

Changes:
- Whole-episode sparse IK, stable outward/down elbow plane, joint acceleration costs.
- Human wrist comfort and joint limits; cube grasps refitted around neutral wrists.
- Steadier stance closer to the task; lateral reach distributed through waist.
- Feet planted, unchanged upper-body world transforms after stance correction.
- Continuous anatomical camera-right axis prevents 180-degree Ego flips at vertical view.
- Whole-interval finger contact optimization with angular smoothness costs.
- Approximate fingertip landmarks permit 3 mm target error / 5 mm relative drift.
  These are soft geometric contacts, not deformable pad or force validation.

Reproduction (from ROOT/human41; CPU stages use usd_python.sh):
1. Preserve grasp-refit.npz as the fitted grasp input.
2. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 bash usd_python.sh ../human-natural-v4/optimize.py
3. bash usd_python.sh ../human-natural-v4/fix_stance.py
4. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 bash usd_python.sh ../human-natural-v4/refine_fingers.py
5. bash usd_python.sh ../human-natural-v4/fix_camera.py
   bash usd_python.sh ../human-natural-v4/audit_motion.py
6. bash usd_python.sh ../human-natural-v4/validate.py
7. bash usd_python.sh ../human-natural-v4/bake.py
8. bash usd_python.sh ../human-natural-v4/ego_mask.py
9. bash ../human-natural-v4/render_full.sh

The optional --preview bake/render flags select 11 diagnostic source frames.
Full rendering uses six independent Isaac Sim 4.1 jobs, three segments per view.
encode.py verifies all 1507 frames, source hashes, object poses and decoded video
frame counts before creating the synchronized robot / human ego / human front video.

Trajectory matrices: column-vector 4x4 transforms, translation in meters.
source_frame indexes the original robot episode. video_time_s is frame/15.
paired-world-trajectories.npz contains objects, hands, elbows, camera and arm DOFs.
human-animation.npz additionally contains all 101 local skeletal transforms and
finger parameters. world_transform maps the human root to the simulation world.

Naturalness is not a validated human behavior model. The avatar remains the
existing textured Worker asset, and hand skin / pose realism is still limited by
its rig. Numeric smoothness checks supplement visual inspection; neither proves
anatomical realism or collision-free contact everywhere.
