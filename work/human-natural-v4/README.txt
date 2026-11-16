Fresh original-Worker deployment (new-machine path)

See migration/FRESH_EPISODE.md for SDK, selective robot assets and episode export.
python3 migration/bootstrap_worker.py RUN_ROOT
bash migration/run_worker_motion.sh RUN_ROOT

This path sets EGO_WORKER_FRESH=1, uses the native Reallusion Worker USD and
included pose library, and consumes the new immutable human-stack-v3/source.
It does not need the historical human animation, scan hands, anime models or Blender.
A fixed upright standing pose faces 15 degrees toward the right-side workspace.
Native clavicle protraction and arm/finger IK preserve the source bone lengths;
the body support plane may sit below the table support plane. World-space elbow
constraints rotate with the torso. Source object arrays and actual episode length
are verified by verify_fresh.py, not the historical 1507-frame validate.py.
Previous grasp-fit caches are archived before a new solve so the entry point
always starts from the original rig. Start with render_debug.sh: one GPU process
at a time, 640x360 RayTracedLighting, no temporal AA, and a last/first/last RGB
repeatability audit before the complete sampled episode. Default stride is 3;
EGO_DEBUG_STRIDE=1 renders every source frame. Robot and human views use identical
sample indices and hold durations. Debug outputs explicitly say sampled debug;
they preserve task duration but are not full-rate rendered videos.

Each source frame gets a fresh avatar prim. Reusing a prim and updating its
points in place produced stale GPU hand geometry despite correct CPU transforms.
Do not remove this synchronization measure based only on CPU position tests.

For a full-rate deliverable, render_full.sh defaults to one process and the same
low-cost profile. EGO_RENDER_JOBS=2 is the maximum. Set EGO_RENDER_QUALITY=final
explicitly for 1280x720 PathTracing. All profiles keep source objects/timing intact.

The remainder documents the earlier 1507-frame experiment and its old comparison
inputs; those comparison files are not needed by the fresh entry point above.

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
Full rendering splits into three segments per view, with one process by default.
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
