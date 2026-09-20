"""Generator tests: detection, small-scale generation, reset safety."""

from odoo.tests.common import TransactionCase


class TestDemoGenerator(TransactionCase):

    def _tiny_profile(self, itype='university'):
        return self.env['oacis.demo.profile'].create({
            'name': 'Tiny %s' % itype,
            'code': 'TINY-%s' % itype.upper(),
            'institution_type': itype,
            'faculty_count': 2,
            'staff_count': 1,
            'student_count': 6,
            'course_count': 2,
            'guardian_every_n': 0,
            'attendance_sessions_per_offering': 1,
            'applicants_count': 2,
        })

    def test_resolve_legacy_without_profile(self):
        generator = self.env['oacis.demo.generator']
        company = self.env.company
        company.institution_profile_id = False
        self.assertEqual(generator.resolve_institution_type(company), 'legacy')

    def test_resolve_school_profile(self):
        profile = self.env.ref(
            'oacis_institution_profile.profile_school_k12',
            raise_if_not_found=False)
        if not profile:
            self.skipTest('K-12 institution profile seed not installed')
        company = self.env.company
        company.institution_profile_id = profile.id
        try:
            self.assertEqual(
                self.env['oacis.demo.generator'].resolve_institution_type(company),
                'school')
        finally:
            company.institution_profile_id = False

    def test_generate_reset_small(self):
        generator = self.env['oacis.demo.generator']
        company = self.env.company
        company.institution_profile_id = False
        profile = self._tiny_profile()
        result = generator.generate(company, demo_profile=profile)
        self.assertEqual(result['institution_type'], 'legacy')
        students = self.env['oacis.student'].search(
            [('company_id', '=', company.id),
             ('email', 'like', '@demo.')])
        self.assertEqual(len(students), 6)
        registry = self.env['oacis.demo.record'].search(
            [('company_id', '=', company.id)])
        self.assertTrue(len(registry) > len(students))
        # A manually created student (on legacy, non-demo records) must
        # survive reset.
        legacy_program = self.env['oacis.program'].search(
            [('company_id', '=', company.id),
             ('code', 'not like', 'DEMO-%')], limit=1)
        self.assertTrue(legacy_program, 'legacy program missing')
        legacy_campus = self.env['oacis.campus'].search(
            [('company_id', '=', company.id),
             ('code', 'not like', 'DEMO%')], limit=1)
        self.assertTrue(legacy_campus, 'legacy campus missing')
        legacy_semester = self.env['oacis.semester'].search(
            [('code', 'not like', 'DEMO-%')], limit=1)
        keeper = self.env['oacis.student'].create({
            'name': 'Keeper', 'last_name': 'Real', 'gender': 'male',
            'date_of_birth': '2004-01-01', 'email': 'keeper.real@example.com',
            'mobile': '+919199999999', 'company_id': company.id,
            'campus_id': legacy_campus.id,
            'program_id': legacy_program.id, 'batch_year': 2026,
            'admission_date': '2026-07-01',
            'current_semester_id': legacy_semester.id,
            'student_state': 'enrolled',
        })
        reset = generator.reset_company_demo(company)
        self.assertTrue(reset['removed'] > 0)
        self.assertFalse(self.env['oacis.demo.record'].search(
            [('company_id', '=', company.id)]))
        self.assertTrue(keeper.exists())
        self.assertFalse(students.exists())
        # Regeneration works after reset.
        result2 = generator.generate(company, demo_profile=profile)
        self.assertEqual(
            result2['counts'].get('student'),
            result['counts'].get('student'))
        keeper.unlink()
