"""Smoke / regression suite for unicore_academic_generic (Phase 0).

Covers the generic academic-unit tree: seeded unit-type taxonomy, hierarchy
creation, parent-type allow-list enforcement, cycle detection, uniqueness, and
the child-opening action. This is the regression baseline for the Phase 1
wiring of unicore.program.academic_unit_id.
"""

from psycopg2 import IntegrityError

import odoo
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'unit')
class UniCoreAcademicUnitTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        UnitType = cls.env['unicore.academic.unit.type']

        cls.type_faculty = cls.env.ref('unicore_academic_generic.unit_type_faculty')
        cls.type_department = cls.env.ref('unicore_academic_generic.unit_type_department')
        cls.type_grade_level = cls.env.ref('unicore_academic_generic.unit_type_grade_level')
        cls.type_wing = cls.env.ref('unicore_academic_generic.unit_type_wing')
        cls.type_other = cls.env.ref('unicore_academic_generic.unit_type_other')
        cls.type_division = cls.env.ref('unicore_academic_generic.unit_type_division')
        cls.type_stream = cls.env.ref('unicore_academic_generic.unit_type_stream')
        cls.type_batch_group = cls.env.ref('unicore_academic_generic.unit_type_batch_group')
        # Unused here but kept to assert the full seed set exists.
        assert UnitType.search_count([]) >= 8

    def _new_unit(self, name, code, unit_type, parent=None):
        return self.env['unicore.academic.unit'].create({
            'name': name,
            'code': code,
            'unit_type_id': unit_type.id,
            'parent_id': parent.id if parent else False,
            'company_id': self.company.id,
        })

    def test_01_seeded_unit_type_taxonomy(self):
        """All eight seed unit types exist with the intended allow-list."""
        self.assertEqual(self.type_faculty.code, 'FAC')
        self.assertEqual(self.type_department.code, 'DEP')
        self.assertEqual(self.type_grade_level.code, 'GRADE')
        self.assertEqual(self.type_wing.code, 'WING')
        self.assertEqual(self.type_stream.code, 'STREAM')
        self.assertEqual(self.type_division.code, 'DIV')
        self.assertEqual(self.type_batch_group.code, 'BATCH')
        self.assertEqual(self.type_other.code, 'OTHER')

        # Faculty may only contain departments; Wing may only contain grade levels.
        self.assertEqual(
            self.type_faculty.allowed_child_type_ids, self.type_department)
        self.assertEqual(
            self.type_wing.allowed_child_type_ids, self.type_grade_level)
        # Department allows Division / Stream / Wing.
        self.assertEqual(
            set(self.type_department.allowed_child_type_ids.ids),
            {self.type_division.id, self.type_stream.id, self.type_wing.id},
        )

    def test_02_valid_hierarchy_tree(self):
        """Faculty -> Department and Wing -> Grade Level trees build cleanly."""
        faculty = self._new_unit('Faculty of Engineering', 'FENG', self.type_faculty)
        dept = self._new_unit('Software Engineering', 'SE', self.type_department,
                              parent=faculty)
        self.assertEqual(dept.parent_id, faculty)
        self.assertEqual(faculty.child_ids, dept)
        self.assertEqual(faculty.unit_count, 1)

        wing = self._new_unit('Primary Wing', 'PW', self.type_wing)
        grade = self._new_unit('Grade 5', 'G5', self.type_grade_level, parent=wing)
        self.assertEqual(grade.parent_id, wing)
        self.assertEqual(wing.unit_count, 1)

    def test_03_computed_display_name_and_path(self):
        """display_name embeds the unit type; path joins ancestors."""
        faculty = self._new_unit('Faculty of Science', 'FSCI', self.type_faculty)
        dept = self._new_unit('Physics', 'PHY', self.type_department, parent=faculty)
        self.assertEqual(faculty.display_name, 'Faculty of Science (Faculty)')
        self.assertEqual(faculty.path, 'Faculty of Science')
        self.assertEqual(dept.path, 'Faculty of Science / Physics')

    def test_04_disallowed_child_type_rejected(self):
        """A unit type not in the parent's allow-list is rejected."""
        faculty = self._new_unit('Faculty of Arts', 'FARTS', self.type_faculty)
        with self.assertRaises(ValidationError):
            # Faculty allow-list only contains Department — a Wing under Faculty is illegal.
            self._new_unit('Primary Wing', 'W1', self.type_wing, parent=faculty)

    def test_05_cycle_detection(self):
        """A unit cannot be its own ancestor."""
        node_type = self.env['unicore.academic.unit.type'].create({
            'name': 'Test Node', 'code': 'NODE',
        })
        node_type.allowed_child_type_ids = [(6, 0, [node_type.id])]

        a = self._new_unit('Node A', 'A', node_type)
        b = self._new_unit('Node B', 'B', node_type, parent=a)
        c = self._new_unit('Node C', 'C', node_type, parent=b)

        with self.assertRaises(ValidationError):
            a.parent_id = c

    def test_06_unique_code_rejected_same_company(self):
        """Duplicate unit codes in the same company are rejected.

        Per-company scope is enforced by the UNIQUE(code, company_id) DB
        constraint; the same code may legitimately repeat across companies.
        (Deliberately no cross-company sub-assert here: creating a second
        res.company in Odoo 19 CE triggers an unrelated NOT NULL quirk on the
        internally-created res.partner.)
        """
        self._new_unit('Faculty of Medicine', 'FMED', self.type_faculty)
        with self.assertRaises(IntegrityError):
            self._new_unit('Faculty of Law', 'FMED', self.type_faculty)

    def test_07_action_open_children(self):
        """action_open_children returns a window action filtered to children."""
        faculty = self._new_unit('Faculty of Commerce', 'FCOM', self.type_faculty)
        self._new_unit('Accounting', 'ACC', self.type_department, parent=faculty)
        action = faculty.action_open_children()
        self.assertEqual(action['res_model'], 'unicore.academic.unit')
        self.assertEqual(action['view_mode'], 'list,form,kanban')
        self.assertEqual(action['domain'], [('parent_id', '=', faculty.id)])
        self.assertEqual(action['context']['default_parent_id'], faculty.id)

    def test_08_multi_level_department_nesting(self):
        """Department -> Stream -> Grade Level nests (K-12 style)."""
        dept = self._new_unit('Academic', 'ACD', self.type_department)
        stream = self._new_unit('Science Stream', 'SCI', self.type_stream, parent=dept)
        grade = self._new_unit('Grade 9', 'G9', self.type_grade_level, parent=stream)
        self.assertEqual(grade.path, 'Academic / Science Stream / Grade 9')
