import copy
import json
from pathlib import Path
import tempfile
import unittest

from guide_lite.core import Classifier, Decision, ROOT, load_motion_config, max_error, normalize, plan_for
from guide_lite.motion import validate_robot_description, motion_outcome, hold_outcome


class ClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=Classifier()

    def test_01_development_examples(self):
        for row in json.loads((ROOT/'data/checks.json').read_text(encoding='utf-8')):
            with self.subTest(text=row['text']):
                self.assertEqual(self.c.decide(row['text']).label,row['expected'])

    def test_02_export_matches_sklearn_reference(self):
        # Scores exported by sklearn itself during training. No Gazebo is involved.
        for row in json.loads((ROOT/'model/reference_scores.json').read_text(encoding='utf-8')):
            got=self.c.predict_proba(row['text'])
            for label,value in row['scores'].items():
                self.assertAlmostEqual(got[label],value,places=10)

    def test_03_scores_sum_to_one(self):
        self.assertAlmostEqual(sum(self.c.predict_proba('受付').values()),1.0,places=12)
    def test_04_no_features_holds(self):
        self.assertEqual(self.c.decide('zxq873920').reason,'unknown')
    def test_05_empty_holds(self):
        self.assertEqual(self.c.decide('   ').label,'hold')
    def test_06_long_text_holds(self):
        self.assertEqual(self.c.decide('受付'*100).reason,'too_long')
    def test_07_escape_sequence_holds(self):
        self.assertEqual(self.c.decide('\x1b[31m受付').reason,'control_chars')
    def test_08_negated_reception_holds(self):
        self.assertEqual(self.c.decide('受付には行かない').label,'hold')
    def test_09_two_destinations_holds(self):
        self.assertEqual(self.c.decide('受付と出口に行く').reason,'multiple_destinations')
    def test_10_stop_holds(self):
        self.assertEqual(self.c.decide('停止してください').label,'hold')
    def test_11_wrong_input_type(self):
        with self.assertRaises(TypeError): self.c.decide(None)
    def test_12_unicode_normalization(self):
        self.assertEqual(normalize(' ＡＢＣ  受付 '),'abc 受付')
    def test_13_missing_model_raises(self):
        with self.assertRaises(FileNotFoundError): Classifier(ROOT/'does_not_exist.json')
    def test_14_corrupt_model_raises(self):
        d=json.loads((ROOT/'model/intent_model.json').read_text(encoding='utf-8'));d['coef'][0]=[]
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.json';p.write_text(json.dumps(d),encoding='utf-8')
            with self.assertRaises(ValueError): Classifier(p)
    def test_15_nan_model_raises(self):
        d=json.loads((ROOT/'model/intent_model.json').read_text(encoding='utf-8'));d['intercept'][0]=float('nan')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'model.json';p.write_text(json.dumps(d),encoding='utf-8')
            with self.assertRaises(ValueError): Classifier(p)
    def test_16_model_class_hold(self):
        self.assertEqual(self.c.decide('あちらをお願いします').reason,'model_hold')
    def test_17_low_score_holds(self):
        c=Classifier();c.threshold=1.0
        self.assertEqual(c.decide('受付はどちらですか').reason,'low_score')
    def test_18_small_margin_holds(self):
        c=Classifier();c.margin_threshold=1.0
        self.assertEqual(c.decide('受付はどちらですか').reason,'small_margin')


class MotionLogicTests(unittest.TestCase):
    def setUp(self): self.cfg=load_motion_config()
    def urdf(self,marker='ign_ros2_control/IgnitionSystem'):
        return '<robot name="test">'+''.join(
            f'<joint name="{j}" type="revolute"><limit lower="-2" upper="2" velocity="2"/></joint>'
            for j in self.cfg['joint_names'])+f'<ros2_control><hardware><plugin>{marker}</plugin></hardware></ros2_control></robot>'
    def test_19_hold_has_no_motion(self):
        self.assertIsNone(plan_for(Decision('hold','empty',{}),self.cfg))
    def test_20_two_destinations_distinct(self):
        a=plan_for(Decision('reception','classified',{}),self.cfg)
        b=plan_for(Decision('exit','classified',{}),self.cfg)
        self.assertNotEqual(a,b)
    def test_21_unknown_label_rejected(self):
        with self.assertRaises(ValueError): plan_for(Decision('other','classified',{}),self.cfg)
    def test_22_urdf_limits_validated(self):
        self.assertEqual(len(validate_robot_description(self.urdf(),self.cfg)),4)
    def test_23_physical_hardware_rejected(self):
        with self.assertRaises(ValueError): validate_robot_description(self.urdf('real_driver'),self.cfg)
    def test_24_missing_joint_rejected(self):
        with self.assertRaises(ValueError): validate_robot_description(self.urdf().replace('crane_plus_joint2','another'),self.cfg)
    def test_25_pose_outside_urdf_rejected(self):
        with self.assertRaises(ValueError): validate_robot_description(self.urdf().replace('upper="2"','upper="0.2"'),self.cfg)
    def test_26_action_success_needs_position(self):
        self.assertFalse(motion_outcome([.8,0,0,0],[0,0,0,0],.05,4,0)['passed'])
    def test_27_action_failure_never_passes(self):
        self.assertFalse(motion_outcome([0]*4,[0]*4,.05,6,-1)['passed'])
    def test_28_motion_success(self):
        self.assertTrue(motion_outcome([.01]*4,[0]*4,.05,4,0)['passed'])
    def test_29_hold_needs_no_commands(self):
        self.assertFalse(hold_outcome([0]*4,[[0]*4],0,1,.02)['passed'])
    def test_30_hold_needs_no_drift(self):
        self.assertFalse(hold_outcome([0]*4,[[.1]*4],0,0,.02)['passed'])
    def test_31_hold_needs_samples(self):
        with self.assertRaises(ValueError): hold_outcome([0]*4,[],0,0,.02)
    def test_32_hold_with_samples_passes(self):
        self.assertTrue(hold_outcome([0]*4,[[.001]*4,[0]*4],0,0,.02)['passed'])
    def test_33_nan_state_rejected(self):
        with self.assertRaises(ValueError): max_error([float('nan')],[0])
    def test_34_mismatched_state_rejected(self):
        with self.assertRaises(ValueError): max_error([0,1],[0])
    def test_35_pose_config_rejects_large_angle(self):
        d=copy.deepcopy(self.cfg);d['poses']['reception'][0]=3.0
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'config.json';p.write_text(json.dumps(d),encoding='utf-8')
            with self.assertRaises(ValueError): load_motion_config(p)
    def test_36_no_ros_without_simulation_flag(self):
        from unittest.mock import patch
        from guide_lite.ros_backend import RosArm
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(RuntimeError): RosArm(self.cfg)

if __name__=='__main__': unittest.main()
