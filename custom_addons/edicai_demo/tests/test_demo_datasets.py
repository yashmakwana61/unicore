"""Dataset definition tests (no database required)."""

from odoo.tests.common import TransactionCase

from ..models.demo_datasets import DATASETS, TERMS


class TestDemoDatasets(TransactionCase):

    def test_all_institution_types_covered(self):
        for itype in ('university', 'college', 'school', 'training',
                      'academy', 'coaching', 'legacy'):
            self.assertIn(itype, DATASETS, 'missing dataset: %s' % itype)

    def test_dataset_structure(self):
        for itype, ds in DATASETS.items():
            if itype == 'legacy':
                continue
            self.assertIn(ds.get('year_type'), TERMS,
                          '%s: unknown year_type' % itype)
            self.assertTrue(ds.get('faculties'), '%s: no faculties' % itype)
            self.assertTrue(ds.get('departments'), '%s: no departments' % itype)
            self.assertTrue(ds.get('programs'), '%s: no programs' % itype)
            self.assertTrue(ds.get('courses'), '%s: no courses' % itype)
            self.assertTrue(ds.get('fee_lines'), '%s: no fee lines' % itype)
            for prog in ds['programs']:
                # 8-tuple rigid style or 4-tuple unit-anchored style.
                self.assertIn(len(prog), (4, 8),
                              '%s: bad program tuple %r' % (itype, prog))
            for course in ds['courses']:
                # 6-tuple rigid style or 5-tuple generic style.
                self.assertIn(len(course), (5, 6),
                              '%s: bad course tuple %r' % (itype, course))

    def test_department_faculty_links(self):
        for itype, ds in DATASETS.items():
            if itype == 'legacy':
                continue
            fac_codes = {code for _name, code in ds['faculties']}
            for _name, code, fac in ds['departments']:
                self.assertIn(fac, fac_codes,
                              '%s: dept %s links unknown faculty' % (itype, code))

    def test_program_anchors(self):
        for itype, ds in DATASETS.items():
            if itype == 'legacy':
                continue
            dept_codes = {code for _n, code, _f in ds['departments']}
            unit_codes = {code for _n, code, _t in ds.get('units', [])}
            for prog in ds['programs']:
                if len(prog) == 8:
                    self.assertIn(prog[2], dept_codes,
                                  '%s: program %s bad dept' % (itype, prog[1]))
                else:
                    self.assertIn(prog[1] and prog[2], unit_codes,
                                  '%s: program %s bad unit' % (itype, prog[1]))
