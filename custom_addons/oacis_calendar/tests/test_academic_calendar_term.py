"""Phase 8 regression suite: academic calendar Term structure.

Verifies K-12 Term support on oacis.academic.year / oacis.semester:

* A Term-based year accepts only Term semesters (term_1..term_4).
* Adding a non-Term semester to a Term year is rejected (via the year's
  one2many AND via direct semester creation).
* Switching an existing semester-based year to Term is rejected when it
  holds non-Term semesters.
* Legacy (semester) years are 100% unchanged.
"""

import odoo
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisCalendarTermTest(TransactionCase):

    def _year(self, code, year_type='semester', semester_ids=None, **kw):
        vals = {
            'name': 'P8 %s' % code,
            'code': code,
            'date_start': '2026-04-01',
            'date_end': '2027-03-31',
            'year_state': 'cancelled',
            'year_type': year_type,
        }
        if semester_ids is not None:
            vals['semester_ids'] = semester_ids
        vals.update(kw)
        return self.env['oacis.academic.year'].create(vals)

    def _sem(self, code, semester_type, date_start, date_end):
        return {
            'name': 'P8 %s' % code,
            'code': code,
            'semester_type': semester_type,
            'date_start': date_start,
            'date_end': date_end,
        }

    def test_01_term_year_with_term_semesters(self):
        """A Term-based year accepts First/Second/Third Term semesters."""
        year = self._year('P8TERM1', year_type='term', semester_ids=[
            (0, 0, self._sem('P8T1', 'term_1', '2026-04-01', '2026-07-31')),
            (0, 0, self._sem('P8T2', 'term_2', '2026-08-01', '2026-11-30')),
            (0, 0, self._sem('P8T3', 'term_3', '2026-12-01', '2027-03-31')),
        ])
        self.assertEqual(year.year_type, 'term')
        self.assertEqual(year.semester_count, 3)
        self.assertEqual(
            year.semester_ids.mapped('semester_type'),
            ['term_1', 'term_2', 'term_3'],
        )

    def test_02_term_year_rejects_odd_semester(self):
        """Adding a non-Term semester to a Term year is rejected."""
        year = self._year('P8TERM2', year_type='term')
        # Through the year's one2many (UI path).
        with self.assertRaises(ValidationError):
            year.write({'semester_ids': [
                (0, 0, self._sem('P8TODD', 'odd', '2026-04-01', '2026-07-31')),
            ]})
        # Direct creation on the semester model is also rejected.
        with self.assertRaises(ValidationError):
            self.env['oacis.semester'].create({
                'name': 'P8 Direct Odd',
                'code': 'P8DO',
                'semester_type': 'odd',
                'academic_year_id': year.id,
                'date_start': '2026-08-01',
                'date_end': '2026-11-30',
            })

    def test_03_switch_existing_year_to_term_rejected(self):
        """A year holding odd/even semesters cannot become Term-based."""
        year = self._year('P8SWITCH', year_type='semester', semester_ids=[
            (0, 0, self._sem('P8S1', 'odd', '2026-04-01', '2026-07-31')),
            (0, 0, self._sem('P8S2', 'even', '2026-08-01', '2026-11-30')),
        ])
        with self.assertRaises(ValidationError):
            year.write({'year_type': 'term'})

    def test_04_legacy_semester_year_unchanged(self):
        """Legacy semester-based years are untouched by Term rules."""
        year = self._year('P8LEG', year_type='semester', semester_ids=[
            (0, 0, self._sem('P8L1', 'odd', '2026-04-01', '2026-07-31')),
            (0, 0, self._sem('P8L2', 'even', '2026-08-01', '2026-11-30')),
        ])
        self.assertEqual(year.year_type, 'semester')
        self.assertEqual(year.semester_count, 2)
        # Legacy years may even use Term semester types (flexible calendar).
        year.write({'semester_ids': [
            (0, 0, self._sem('P8LT', 'term_1', '2026-12-01', '2027-03-31')),
        ]})
        self.assertEqual(year.semester_count, 3)
