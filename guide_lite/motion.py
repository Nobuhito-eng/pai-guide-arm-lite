"""Small, separately testable motion validation helpers. No physics simulation."""
from __future__ import annotations
import math
import xml.etree.ElementTree as ET
from .core import max_error


def validate_robot_description(xml: str, config: dict) -> dict:
    root = ET.fromstring(xml)
    markers = ('gazebo_ros2_control', 'ign_ros2_control', 'gz_ros2_control')
    if root.tag != 'robot' or not any(x in xml for x in markers):
        raise ValueError('Simulation control plugin not found; physical robots are unsupported')
    joints = {j.attrib.get('name'): j for j in root.findall('joint')}
    limits = {}
    for name in config['joint_names']:
        if name not in joints:
            raise ValueError(f'Missing joint: {name}')
        lim = joints[name].find('limit')
        if lim is None:
            raise ValueError(f'Missing joint limit: {name}')
        low, high, velocity = (float(lim.attrib[k]) for k in ('lower','upper','velocity'))
        if not all(math.isfinite(x) for x in (low,high,velocity)) or low>=high or velocity<=0:
            raise ValueError(f'Invalid joint limits: {name}')
        limits[name] = {'lower':low, 'upper':high, 'velocity':velocity}
    for pose_name, pose in config['poses'].items():
        for joint, pos in zip(config['joint_names'],pose):
            if not limits[joint]['lower']+.01 <= pos <= limits[joint]['upper']-.01:
                raise ValueError(f'{pose_name} outside URDF limit for {joint}')
    return limits


def motion_outcome(actual: list[float], target: list[float], tolerance: float,
                   action_status: int, error_code: int) -> dict:
    err = max_error(actual,target)
    # ROS action status 4 = SUCCEEDED; FollowJointTrajectory error code 0 = SUCCESSFUL.
    return {'passed':action_status==4 and error_code==0 and err<=tolerance,
            'max_error_rad':err,'action_status':action_status,'action_error_code':error_code}


def hold_outcome(before: list[float], observed: list[list[float]], sent_before: int,
                 sent_after: int, tolerance: float) -> dict:
    if not observed:
        raise ValueError('No fresh state samples: HOLD must not be marked successful')
    drift=max(max_error(x,before) for x in observed)
    return {'passed':sent_before==sent_after and drift<=tolerance,
            'goals_sent':sent_after-sent_before,'max_motion_rad':drift,
            'samples':len(observed)}
