"""Report-generation tests use temporary synthetic files, not Gazebo evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import guide_lite.report as report
from guide_lite.core import ROOT

class ReportTests(unittest.TestCase):
    def make_root(self,temp):
        p=Path(temp)
        for folder in ['model','config','artifacts']: (p/folder).mkdir()
        for source in ['model/intent_model.json','config/motion.json']:
            (p/source).write_bytes((ROOT/source).read_bytes())
        return p
    def test_37_missing_result_is_draft(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.make_root(t)
            with patch.object(report,'ROOT',p):
                s=report.generate_report().read_text(encoding='utf-8')
            self.assertIn('Gazebo確認が未実施',s)
            self.assertNotIn('6回の自動確認がPASS（',s)
    def test_38_wrong_model_never_passes(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.make_root(t)
            d={'kind':'GAZEBO_CHECK','status':'PASS','rows':[{'status':'PASS'}]*6,'model_sha256':'wrong','motion_sha256':'wrong'}
            (p/'artifacts/latest_gazebo_check.json').write_text(json.dumps(d),encoding='utf-8')
            with patch.object(report,'ROOT',p):
                s=report.generate_report().read_text(encoding='utf-8')
            self.assertIn('未完成',s)
    def test_39_incomplete_run_never_passes(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.make_root(t)
            d={'kind':'GAZEBO_CHECK','status':'STARTED','rows':[]}
            (p/'artifacts/latest_gazebo_check.json').write_text(json.dumps(d),encoding='utf-8')
            with patch.object(report,'ROOT',p):
                s=report.generate_report().read_text(encoding='utf-8')
            self.assertIn('未完成',s)
    def test_40_account_is_escaped(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.make_root(t)
            with patch.object(report,'ROOT',p):
                s=report.generate_report('<script>alert(1)</script>').read_text(encoding='utf-8')
            self.assertNotIn('<script>',s)
            self.assertIn('&lt;script&gt;',s)

if __name__=='__main__': unittest.main()
