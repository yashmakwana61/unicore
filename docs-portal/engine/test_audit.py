import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from audit import read_manifest,inspect_python,scan_xml
class AuditTests(unittest.TestCase):
 def test_manifest(self):
  with TemporaryDirectory() as d:
   p=Path(d)/"__manifest__.py";p.write_text("{'name':'test','depends':['base']}")
   self.assertEqual(read_manifest(p)["depends"],["base"])
 def test_code_never_executed(self):
  with TemporaryDirectory() as d:
   p=Path(d)/"__manifest__.py";p.write_text("__import__('os').system('echo bad')")
   with self.assertRaises((ValueError,SyntaxError)):read_manifest(p)
 def test_python(self):
  with TemporaryDirectory() as d:
   p=Path(d)/"m.py";p.write_text("class Student:\n _name='edicai.student'\n")
   self.assertEqual(inspect_python(p)["models"],["edicai.student"])
 def test_xml(self):
  with TemporaryDirectory() as d:
   p=Path(d)/"m.xml";p.write_text('<odoo><menuitem id="x.menu"/></odoo>')
   self.assertEqual(scan_xml(p)["menus"],["x.menu"])
if __name__=="__main__":unittest.main()
