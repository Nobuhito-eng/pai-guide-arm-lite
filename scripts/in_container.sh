#!/usr/bin/env bash
set -eo pipefail
source /workspace/guide/scripts/env.sh
mode="${1:-help}"
case "$mode" in
  setup)
    /usr/bin/python3 -c 'import rclpy; from control_msgs.action import FollowJointTrajectory; from sensor_msgs.msg import JointState; from rosgraph_msgs.msg import Clock; print("ROS imports OK")'
    ros2 pkg prefix crane_plus_gazebo
    /usr/bin/python3 guide.py ai-check
    /usr/bin/python3 -m unittest discover -s tests -v
    echo 'SETUP PASS. Next: start Gazebo. No AI pip install or API key is needed.'
    ;;
  doctor|check|demo|console|home)
    exec /usr/bin/python3 -u guide.py "$mode" --confirm-simulation
    ;;
  ai-check) exec /usr/bin/python3 guide.py ai-check ;;
  report) exec /usr/bin/python3 guide.py report ;;
  *) echo 'Unknown mode' >&2; exit 2 ;;
esac
