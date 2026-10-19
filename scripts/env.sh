#!/usr/bin/env bash
# Source explicitly instead of .bashrc (which may return early in non-interactive shells).
set +u
export HOME=/home/ubuntu
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export PYTHONIOENCODING=utf-8
export ROS_DOMAIN_ID=73
export ROS_LOCALHOST_ONLY=1
export PAI_SIMULATION_ONLY=1
export PYTHONPATH="/workspace/guide${PYTHONPATH:+:$PYTHONPATH}"
if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo 'ERROR: ROS 2 Humble is missing. Use the lecture Docker image.' >&2
  return 10
fi
source /opt/ros/humble/setup.bash
for ws in /home/ubuntu/airobot_ws /home/ubuntu/ros2_ws /home/ubuntu/pai_ws; do
  [[ -f "$ws/install/setup.bash" ]] && source "$ws/install/setup.bash"
done
if [[ -z ${DISPLAY:-} ]]; then
  if [[ -S /tmp/.X11-unix/X1 ]]; then
    DISPLAY=:1
  elif [[ -S /tmp/.X11-unix/X0 ]]; then
    DISPLAY=:0
  else
    DISPLAY=:0
  fi
fi
export DISPLAY
export LIBGL_ALWAYS_SOFTWARE=1
cd /workspace/guide
