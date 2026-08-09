"""Institution-profile academic unit level enforcement (config wiring).

Verifies that ``unicore.academic.unit`` honors the institution profile's
``academic_unit_level_ids`` allow-list: strict when the list is non-empty,
unrestricted when the profile is absent or the list is empty. UNI_LEGACY lists
all eight unit types so the backfilled default never blocks anything.

Lives in this module (not unicore_academic_generic) because the enforcement is
wired from here — the generic module cannot reference the profile without a
circular dependency.
"""

import odoo
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'unit')
class UniCoreAcademicUnitLevelsTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.profile_school = cls.env.ref(
            'unicore_institution_profile.profile_school_k12')
        cls.profile_legacy = cls.env.ref(
            'unicore_institution_profile.profile_university_legacy')
        cls.type_faculty = cls.env.ref(
            'unicore_academic_generic.unit_type_faculty')
        cls.type_grade_level = cls.env.ref(
            'unicore_academic_generic.unit_type_grade_level')

    def _new_unit(self, name, code, unit_type):
        return self.env['unicore.academic.unit'].create({
            'name': name,
            'code': code,
            'unit_type_id': unit_type.id,
            'company_id': self.company.id,
        })

    def test_01_school_profile_rejects_non_grade_levels(self):
        """A school profile (GRADE only) rejects a Faculty unit."""
        self.company.institution_profile_id = self.profile_school.id
        with self.assertRaises(ValidationError):
            self._new_unit('Faculty of Arts', 'FART', self.type_faculty)

    def test_02_school_profile_accepts_grade_level(self):
        """A school profile accepts a Grade Level unit."""
        self.company.institution_profile_id = self.profile_school.id
        grade = self._new_unit('Grade 5', 'G5', self.type_grade_level)
        self.assertEqual(grade.unit_type_id, self.type_grade_level)

    def test_03_no_profile_is_unrestricted(self):
        """No profile (or an empty allow-list) keeps legacy flexibility."""
        self.company.institution_profile_id = False
        faculty = self._new_unit('Faculty of Science', 'FSCI', self.type_faculty)
        self.assertEqual(faculty.unit_type_id, self.type_faculty)

        # An explicit profile with an empty allow-list is also unrestricted.
        profile_empty = self.env['unicore.institution.profile'].create({
            'name': 'Empty Levels', 'code': 'EMPTY_LVL',
            'is_legacy_university': False,
        })
        self.company.institution_profile_id = profile_empty.id
        self.assertFalse(profile_empty.academic_unit_level_ids)
        self._new_unit('Faculty of Law', 'FLAW', self.type_faculty)

    def test_04_legacy_profile_accepts_all_types(self):
        """UNI_LEGACY lists all eight types, so Faculty is still accepted."""
        self.company.institution_profile_id = self.profile_legacy.id
        faculty = self._new_unit('Faculty of Eng', 'FENG', self.type_faculty)
        self.assertEqual(faculty.unit_type_id, self.type_faculty)
