"""Calendar-mode wiring: term-based institutions require Term academic years.

Verifies that ``oacis.academic.year`` honors the institution profile's
``calendar_mode``: one-directional enforcement where a term-based profile
requires ``year_type == 'term'`` (and defaults to it), while semester / legacy
companies stay fully flexible.
"""

import odoo
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisCalendarModeTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.profile_school = cls.env.ref(
            'oacis_institution_profile.profile_school_k12')
        cls.profile_legacy = cls.env.ref(
            'oacis_institution_profile.profile_university_legacy')

    def _year(self, code, **kw):
        vals = {
            'name': 'CM %s' % code,
            'code': code,
            'date_start': '2026-04-01',
            'date_end': '2027-03-31',
            'year_state': 'cancelled',
        }
        vals.update(kw)
        return self.env['oacis.academic.year'].create(vals)

    def test_01_term_profile_rejects_semester_year(self):
        """A term-based institution cannot create a semester-based year."""
        self.company.institution_profile_id = self.profile_school.id
        with self.assertRaises(ValidationError):
            self._year('CM1', year_type='semester')

    def test_02_term_profile_defaults_and_accepts_term_year(self):
        """A term-based institution defaults to (and accepts) Term years."""
        self.company.institution_profile_id = self.profile_school.id
        defaulted = self._year('CM2A')
        self.assertEqual(defaulted.year_type, 'term')

        explicit = self._year('CM2B', year_type='term')
        self.assertEqual(explicit.year_type, 'term')

    def test_03_legacy_company_stays_flexible(self):
        """Semester / no-profile companies can still use any year structure."""
        self.company.institution_profile_id = self.profile_legacy.id
        sem = self._year('CM3A', year_type='semester')
        self.assertEqual(sem.year_type, 'semester')
        term = self._year('CM3B', year_type='term')
        self.assertEqual(term.year_type, 'term')

        self.company.institution_profile_id = False
        self._year('CM3C', year_type='annual')
