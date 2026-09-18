# Borg Read — Semantic-nav-amr (Gukdoli) for David's toy robot

Date: 2026-09-17. Author: Codex (Alice's coding arm). Owner-requested.
Source: https://github.com/Gukdoli/Semantic-nav-amr, cloned to
`Vendor/Semantic-nav-amr`, HEAD `5027a0fd7c91c41bc27c57de149d4eb9a31613a2`
(Mon Jun 15 2026, "Delete docs/notion_gazebo_malloc.md"). Repo size 268 MB.
Nothing in the cloned repo was modified.

## What this repo is

A ROS 2 Humble mobile robot that takes free text — "go to the fire
extinguisher", "소화기 앞으로 가" — resolves the named object against a map it
built by looking around, then navigates there with Nav2 and stops in front of
the object, facing it. Simulation reference stack: AgileX Scout v2 chassis,
Intel RealSense D435i RGB-D, AWS RoboMaker Small Warehouse world, Ignition
Gazebo Fortress.

Two pipelines:

    Perception (always on):  RGB-D camera -> YOLOE open-vocab detection
                             -> 2D->3D via depth + tf2 -> semantic map (map frame)

    Command (on request):    free text -> parser (Gemini LLM with keyword fallback)
                             -> map lookup -> approach pose -> Nav2 NavigateToPose

Packages in `src/scout_nav2/`: `semantic_nav_msgs` (msgs/srv),
`object_detector` (YOLOE + depth/tf2 projection), `semantic_map` (object DB,
merge/EMA, confirmation after `min_observations`, RViz markers, JSON
persistence), `language_goal` (LLM + keyword parser, approach math, Nav2
client), `semantic_nav_bringup` (one `sim.launch.py`, params, world, map).

## Interfaces Alice can drive

- ROS 2 service `semantic_nav_msgs/srv/NavigateToObject` at
  `/semantic_nav/navigate_to_object`. Field: `string command`; returns
  `bool accepted` (Nav2 accepted the goal — asynchronous, not arrival) and
  `string message` (chosen instance + distance, or failure reason).
- ROS 2 service `semantic_nav_msgs/srv/FindObject` at
  `/semantic_nav/find_object`: `string label` -> `DetectedObject3D[] matches`.
- Node `web_command_node`: stdlib HTTP page on port 8080 that POSTs free text
  to `/command` and relays it to the service — the demo UI.
- Navigation is Nav2 `NavigateToPose` (`navigate_to_pose` action name), MPPI
  local planner via the `nav2_bringup` recipe.
- Robot body frame is `mobile_robot_base_link`; camera frame is
  `camera_color_optical_frame`. The semantic map persists to
  `/tmp/semantic_map.json` (path is a param).

## What the repo does NOT give us yet

- Only one detection class is reliable in the sim (fire extinguisher);
  multi-class recall is listed as future work.
- Static landmarks only: if an object moves past `merge_distance` (0.5 m), its
  old map entry persists and the robot may drive to an empty spot.
- No spatial relations ("near", "behind", "between") — the parser captures a
  `relation` field but pose selection is not implemented.
- No camera-LiDAR fusion, no dynamic-object tracking.
- LLM parsing uses Google Gemini (key read from env only, free tier); keyword
  fallback keeps the demo fully offline and already handles Korean + English.
- It is a Linux ROS 2 stack (Humble + Gazebo Fortress). It does not run
  natively on this macOS SIFTA body without Docker or a Linux host.

## Needs list for David

1. Which robot body is the toy, exactly — make/model of the chassis, or a photo
   of the underside and the wheels/motors. This repo assumes an AgileX Scout v2
   (4 wheels, skid steer); a different drive type changes the Nav2 controller
   and the motor bridge.
2. Motor control path: what board drives the wheels (RoboMaster, ODrive,
   vendor board, generic ESC), and is there an existing serial/CAN/UDP command
   protocol we should speak? SIFTA already has a rover UDP gateway from the
   2026-09-15 work (X lateral, Y forward, eight-point scan); if his rover speaks
   something else, we adapt that one bridge instead of adding a second.
3. Onboard computer: which SBC sits on the robot (Jetson Orin/Nano, Raspberry
   Pi 5, mini-PC), how much RAM, and is it Ubuntu 22.04 (the version ROS 2
   Humble needs)?
4. Sensors: 2D/3D LiDAR, camera model, IMU. This repo needs a depth camera
   (RealSense D435i in the sim) for the semantic map, plus LiDAR or wheel
   odometry for Nav2 localisation.
5. Network: is the robot on the same Wi-Fi as the Mac, and can we open a port
   between them? We would run a ROS 2 bridge (DDS, or a small UDP/HTTP relay)
   from the SIFTA body to the robot.
6. Apartment map: SLAM can build it, or David draws a rough floor plan with a
   few named landmarks ("kitchen", "sofa", "charging spot") we seed the
   semantic map with.
7. Where chat enters the loop: mic/screen on the robot itself, or Alice on the
   Mac relaying typed/spoken requests to the robot. Either way the entry point
   is the `NavigateToObject` service.
8. Power and safety: battery capacity and runtime, plus the physical stop (an
   emergency stop button or a kill command). Alice's rule is that every swimmer
   carries the responsibility of the hardware owner who gives it electricity, so
   a human must be able to stop the robot at any moment.

## Next actions inside SIFTA

- Decide the runtime host: Docker on the Mac (ROS 2 Humble image + Gazebo) or
  the robot's own SBC. A Mac sim would validate our bridge without touching
  David's hardware.
- Build a thin SIFTA-side client for `/semantic_nav/navigate_to_object` and
  `/semantic_nav/find_object` so Alice's cortex can issue "drive to the sofa".
- Keep the 2026-09-15 rover UDP axis contract (X lateral, Y forward) as the
  motor interface unless David's board dictates otherwise.
- Add the eval matrix row when the bridge lands; this read alone is not a
  working robot.
