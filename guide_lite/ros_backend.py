"""Actual ROS 2 / Gazebo backend. No mock/fallback mode is provided here.

Requires the teaching image (ROS 2 Humble, CRANE+ V2). This module can be
syntax-checked without ROS, but that is NOT a Gazebo integration test.
"""
from __future__ import annotations
import hashlib
import math
import os
from pathlib import Path
import time
from .core import max_error
from .motion import validate_robot_description, motion_outcome, hold_outcome


class RosArm:
    def __init__(self, config: dict):
        if os.environ.get('PAI_SIMULATION_ONLY') != '1':
            raise RuntimeError('Run inside the supplied isolated simulator container. Physical robots are prohibited.')
        import rclpy
        from rclpy.parameter import Parameter
        from rclpy.action import ActionClient
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, qos_profile_sensor_data
        from sensor_msgs.msg import JointState
        from rosgraph_msgs.msg import Clock
        from std_msgs.msg import String
        from control_msgs.action import FollowJointTrajectory
        self.rclpy=rclpy
        self.config=config
        rclpy.init(args=[])
        self.node=rclpy.create_node('guide_lite_client',parameter_overrides=[Parameter('use_sim_time',value=True)])
        self.state=None
        self.state_received=0.0
        self.state_count=0
        self.clock_received=0.0
        self.clock_advances=0
        self.clock_ns=None
        self.description=None
        self.limits=None
        self.sent_goals=0
        self.active_goal=None
        self._subs=[
            self.node.create_subscription(JointState,config['state_topic'],self._state,qos_profile_sensor_data),
            self.node.create_subscription(Clock,'/clock',self._clock,qos_profile_sensor_data),
            self.node.create_subscription(String,'/robot_description',self._description,
                QoSProfile(depth=1,reliability=ReliabilityPolicy.RELIABLE,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        ]
        self.client=ActionClient(self.node,FollowJointTrajectory,config['action_name'])
        self.action_type=FollowJointTrajectory
        self.preflight_info={}

    def _state(self,msg):
        # Map by names rather than relying on message order.
        values=dict(zip(msg.name,msg.position))
        if all(j in values for j in self.config['joint_names']):
            v=[float(values[j]) for j in self.config['joint_names']]
            if all(math.isfinite(x) for x in v):
                self.state=v
                self.state_received=time.monotonic()
                self.state_count+=1

    def _clock(self,msg):
        ns=int(msg.clock.sec)*1_000_000_000+int(msg.clock.nanosec)
        if self.clock_ns is not None and ns>self.clock_ns:
            self.clock_advances+=1
        self.clock_ns=ns
        self.clock_received=time.monotonic()

    def _description(self,msg):
        self.description=msg.data

    def pump(self,seconds=.1):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            self.rclpy.spin_once(self.node,timeout_sec=min(.05,max(0.0,until-time.monotonic())))

    def wait(self,predicate,timeout,reason):
        deadline=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>deadline:
                raise RuntimeError(reason)
            self.rclpy.spin_once(self.node,timeout_sec=.05)

    def future(self,future,timeout,reason):
        self.wait(future.done,timeout,reason)
        result=future.result()
        if result is None:
            raise RuntimeError(reason)
        return result

    def fresh(self):
        now=time.monotonic()
        limit=self.config['freshness_s']
        if self.state is None or now-self.state_received>limit:
            raise RuntimeError('Fresh joint states unavailable; no further commands will be sent')
        if self.clock_ns is None or now-self.clock_received>limit:
            raise RuntimeError('Fresh /clock unavailable; check Gazebo pause state')

    def no_external_command_source(self):
        infos=self.node.get_publishers_info_by_topic(self.config['command_topic'])
        if infos:
            raise RuntimeError('A trajectory-topic publisher is active. Stop teleop/action_publisher before running this app.')
        names=[n for n,_ in self.node.get_node_names_and_namespaces()]
        if any('teleop' in n.lower() for n in names):
            raise RuntimeError('Teleoperation node detected. Stop it before testing.')

    def prepare(self,timeout=35.0):
        self.wait(lambda:self.state is not None and self.clock_advances>=2,
                  timeout,'Gazebo not ready: /clock must advance and /joint_states must contain four joints')
        self.wait(lambda:self.description is not None,10.0,
                  '/robot_description unavailable. Keep the supplied robot_state_publisher running.')
        self.limits=validate_robot_description(self.description,self.config)
        if not self.client.wait_for_server(timeout_sec=10.0):
            raise RuntimeError('FollowJointTrajectory action server not ready')
        self.pump(.3)
        self.fresh()
        self.no_external_command_source()
        self.preflight_info={
            'backend':'ros2_gazebo', 'clock_advances':self.clock_advances,
            'joint_names':self.config['joint_names'], 'initial_positions':list(self.state),
            'robot_description_sha256':hashlib.sha256(self.description.encode()).hexdigest(),
            'urdf_limits':self.limits,'action_name':self.config['action_name'],
            'node_names':sorted(names for names,_ in self.node.get_node_names_and_namespaces()),
            'ros_distro':os.environ.get('ROS_DISTRO','unknown'),
            'ros_domain_id':os.environ.get('ROS_DOMAIN_ID','unset'),
        }
        return self.preflight_info

    def ensure_home(self):
        self.pump(.25)
        self.fresh()
        if max_error(self.state,self.config['poses']['home'])>self.config['position_tolerance_rad']:
            raise RuntimeError('Not at HOME. Run run.ps1 home, then retry. No automatic reset is done for a HOLD input.')

    def move(self,label):
        from trajectory_msgs.msg import JointTrajectoryPoint
        from builtin_interfaces.msg import Duration
        if label not in ('home','reception','exit'):
            raise ValueError('Movement label is not whitelisted')
        if self.limits is None:
            raise RuntimeError('prepare() is required')
        self.pump(.25)
        self.fresh()
        self.no_external_command_source()
        start=list(self.state)
        target=self.config['poses'][label]
        for j,x in zip(self.config['joint_names'],start):
            if not self.limits[j]['lower']-.05<=x<=self.limits[j]['upper']+.05:
                raise RuntimeError('Current pose outside joint limits')
        duration=float(self.config['duration_s'])
        # Maximum speed of the zero-velocity/acceleration quintic profile is 1.875*distance/T.
        for j,a,b in zip(self.config['joint_names'],start,target):
            if 1.875*abs(a-b)/(duration-.1)>self.limits[j]['velocity']:
                raise RuntimeError('Requested move exceeds the URDF velocity limit')
        goal=self.action_type.Goal()
        goal.trajectory.joint_names=list(self.config['joint_names'])
        for positions,t in [(start,.1),(target,duration)]:
            p=JointTrajectoryPoint()
            p.positions=[float(v) for v in positions]
            p.velocities=[0.0]*4
            p.accelerations=[0.0]*4
            p.time_from_start=Duration(sec=int(t),nanosec=int(round((t-int(t))*1e9)))
            goal.trajectory.points.append(p)
        goal.goal_time_tolerance=Duration(sec=3)
        start_wall=time.monotonic()
        handle=self.future(self.client.send_goal_async(goal),10.0,'Action goal acknowledgement timed out; stop the isolated container if motion continues')
        self.sent_goals+=1
        if not handle.accepted:
            raise RuntimeError('Trajectory goal rejected')
        self.active_goal=handle
        try:
            result_future=handle.get_result_async()
            end=start_wall+self.config['wall_timeout_s']
            while not result_future.done():
                self.pump(.1)
                self.fresh()
                if time.monotonic()>end:
                    raise RuntimeError('Trajectory timed out in wall-clock time')
            response=result_future.result()
            if response is None:
                raise RuntimeError('Missing action result')
            # Wait for a post-result observation; never judge using a pre-move message.
            count=self.state_count
            self.wait(lambda:self.state_count>count,2.0,'No post-motion joint state')
            self.pump(.25)
            self.fresh()
            out=motion_outcome(list(self.state),target,self.config['position_tolerance_rad'],
                               int(response.status),int(response.result.error_code))
            out.update({'label':label,'target':list(target),'actual':list(self.state),
                        'elapsed_wall_s':time.monotonic()-start_wall,'goal_sent':1,
                        'result_message':response.result.error_string})
            self.active_goal=None
            if not out['passed']:
                raise RuntimeError(f'Joint target not reached: {out}')
            return out
        except BaseException:
            self.cancel()
            raise

    def hold_check(self,seconds=2.0):
        self.fresh()
        before=list(self.state)
        sent=self.sent_goals
        samples=[]
        end=time.monotonic()+seconds
        last_count=self.state_count
        while time.monotonic()<end:
            self.pump(.05)
            self.fresh()
            if self.state_count>last_count:
                samples.append(list(self.state))
                last_count=self.state_count
        return hold_outcome(before,samples,sent,self.sent_goals,self.config['hold_tolerance_rad'])

    def cancel(self):
        if self.active_goal is not None:
            try:
                f=self.active_goal.cancel_goal_async()
                self.future(f,2.0,'Cancel timed out')
            except Exception:
                pass  # Best effort; this is not a hardware emergency stop.
            self.active_goal=None

    def close(self):
        self.cancel()
        self.client.destroy()
        self.node.destroy_node()
        if self.rclpy.ok():
            self.rclpy.shutdown()
