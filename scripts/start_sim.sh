#!/usr/bin/env bash
set -eo pipefail
source /workspace/guide/scripts/env.sh
mkdir -p artifacts
if [[ -f /tmp/pai_guide_gazebo.pid ]] && kill -0 "$(cat /tmp/pai_guide_gazebo.pid)" 2>/dev/null; then
  echo 'Gazebo launcher is already running. Do not launch a second copy.'
  exit 0
fi
ros2 pkg prefix crane_plus_gazebo >/dev/null
display_number=${DISPLAY##*:}
display_number=${display_number%%.*}
display_socket="/tmp/.X11-unix/X${display_number}"
if [[ ! -S "$display_socket" ]]; then
  echo "Waiting for the VNC desktop display ${DISPLAY}..."
  for _ in $(seq 1 30); do
    [[ -S "$display_socket" ]] && break
    sleep 1
  done
fi
if [[ ! -S "$display_socket" ]]; then
  echo "ERROR: Display ${DISPLAY} is unavailable (${display_socket}); Gazebo was not started." >&2
  exit 4
fi
nohup setsid bash -c 'source /workspace/guide/scripts/env.sh; exec ros2 launch crane_plus_gazebo crane_plus_with_table.launch.py' > /workspace/guide/artifacts/gazebo_launch.log 2>&1 < /dev/null &
echo "$!" > /tmp/pai_guide_gazebo.pid
sleep 2
if ! kill -0 "$(cat /tmp/pai_guide_gazebo.pid)" 2>/dev/null; then
  tail -n 60 artifacts/gazebo_launch.log
  exit 3
fi
echo 'Gazebo launch requested. Open http://localhost:6088/ and wait for the arm.'
echo 'This message alone is NOT a successful robot test. Run CHECK next.'
