import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
p=Path(__file__).with_name("feature_intelligence.py")
spec=importlib.util.spec_from_file_location("feature_intelligence",p)
fi=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=fi
spec.loader.exec_module(fi)
class FeatureIntelligenceTests(unittest.TestCase):
    def test_manifest_safe(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"__manifest__.py"
            p.write_text("{'name':'Test', 'depends':['base']}")
            self.assertEqual(fi.manifest(p)["name"],"Test")
            p.write_text("__import__('os').system('echo should-not-run')")
            with self.assertRaises(ValueError):fi.manifest(p)
    def test_models_fields_and_actions(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"model.py"
            p.write_text("class Applicant:\n _name='edicai.applicant'\n title=fields.Char(required=True)\n partner_id=fields.Many2one('res.partner')\n def action_confirm(self):\n  pass\n")
            x=fi.python_details(p)
            self.assertEqual(x["models"][0]["model"],"edicai.applicant")
            self.assertEqual([f["kind"] for f in x["fields"]],["Char","Many2one"])
            self.assertEqual(x["methods"][0]["name"],"action_confirm")
    def test_xml(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"test.xml"
            p.write_text('<odoo><menuitem id="m" name="Applicants"/><record id="a" model="ir.actions.act_window"><field name="res_model">edicai.applicant</field></record><record id="v" model="ir.ui.view"><field name="model">edicai.applicant</field></record></odoo>')
            x=fi.xml_details(p)
            self.assertEqual(len(x["menus"]),1)
            self.assertEqual(x["actions"][0]["model"],"edicai.applicant")
            self.assertEqual(len(x["views"]),1)
    def test_report_action(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"report.xml"
            p.write_text('<odoo><record id="report_x" model="ir.actions.report"><field name="name">Student Card</field><field name="model">edicai.student</field></record></odoo>')
            x=fi.xml_details(p)
            self.assertEqual(len(x["reports"]),1)
            self.assertEqual(len(x["actions"]),1)
    def test_acl(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"ir.model.access.csv"
            p.write_text("id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\nx,X,model_x,group_x,1,0,0,0\n")
            self.assertEqual(fi.access_details(p)[0]["read"],"1")
    def test_fixture_end_to_end(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)/"edicai_sample";folder.mkdir()
            (folder/"__manifest__.py").write_text("{'name':'Sample', 'depends':['base']}")
            (folder/"m.py").write_text("class X:\n _name='edicai.sample'\n title=fields.Char()\n")
            data,warnings=fi.inspect(Path(t))
            self.assertEqual(len(data),1)
            self.assertEqual(len(data[0]["fields"]),1)
            self.assertFalse(warnings)
            md,counts=fi.summary(data,warnings)
            self.assertIn("edicai_sample",md)
            self.assertEqual(counts["fields"],1)
if __name__=="__main__":unittest.main()
