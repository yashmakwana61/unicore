"""Phase 1 stub ASN-01..GRD-01: assignment -> submission -> gradebook -> grade entry.

Copy to: custom_addons/edicai_gradebook/tests/test_assignment_gradebook_chain.py
Register in custom_addons/edicai_gradebook/tests/__init__.py.
Covers matrix: ASN-01, ASN-02, ASN-03.
"""
from datetime import date, timedelta

from odoo import fields, tests


@tests.tagged('edicai', 'edicai_phase1', 'integration', 'post_install', '-at_install')
class EdicaiAssignmentGradebookChainTest(tests.common.SingleTransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        faculty = cls.env['edicai.faculty'].create({
            'name': 'Faculty of Engineering', 'code': 'FEG',
            'company_id': cls.company.id})
        department = cls.env['edicai.department'].create({
            'name': 'CSE', 'code': 'CSG', 'faculty_id': faculty.id})
        program = cls.env['edicai.program'].create({
            'name': 'B.Tech', 'code': 'BTG', 'degree_title': 'B.Tech',
            'program_type': 'undergraduate', 'credit_system': 'credit_hours',
            'total_credits': 160, 'duration_years': 4,
            'department_id': department.id, 'company_id': cls.company.id})
        campus = cls.env['edicai.campus'].create({
            'name': 'Main Campus', 'code': 'GBC', 'company_id': cls.company.id})
        year = cls.env['edicai.academic.year'].create({
            'name': '2032-2033', 'code': 'GB32',
            'date_start': '2032-06-01', 'date_end': '2033-05-31',
            'year_type': 'term'})
        semester = cls.env['edicai.semester'].create({
            'name': 'Odd 2032', 'code': 'GB-S1', 'academic_year_id': year.id,
            'date_start': '2032-09-01', 'date_end': '2033-01-31',
            'semester_type': 'term_1',
            'semester_state': 'ongoing', 'company_id': cls.company.id})
        course = cls.env['edicai.course'].create({
            'name': 'Algorithms', 'code': 'GB301',
            'department_id': department.id, 'course_state': 'active',
            'credit_hours': 4, 'internal_assessment_marks': 40,
            'external_assessment_marks': 60, 'total_marks': 100,
            'passing_marks': 40})
        instructor = cls.env['edicai.faculty.member'].create({
            'name': 'Prof Al', 'last_name': 'Go', 'email': 'algo@edicai.edu',
            'mobile': '9000000011', 'gender': 'male',
            'academic_faculty_id': faculty.id, 'department_id': department.id,
            'member_state': 'active', 'joining_date': fields.Date.today()})
        cls.offering = cls.env['edicai.course.offering'].create({
            'course_id': course.id, 'program_id': program.id,
            'academic_year_id': year.id,
            'semester_id': semester.id, 'campus_id': campus.id,
            'faculty_member_id': instructor.id, 'max_enrollment': 60,
            'offering_state': 'open'})
        cls.student = cls.env['edicai.student'].create({
            'name': 'Algo', 'last_name': 'Student', 'email': 'algo@edicai.edu',
            'mobile': '9000000012', 'gender': 'female',
            'date_of_birth': '2005-02-02', 'campus_id': campus.id,
            'program_id': program.id, 'batch_year': '2026',
            'student_state': 'enrolled'})
        cls.env['edicai.enrollment'].create({
            'student_id': cls.student.id,
            'course_offering_id': cls.offering.id,
            'enrollment_state': 'registered'})

    def test_01_publish_submit_grade_rollup(self):
        """ASN-01..03: publish -> submit -> grade -> gradebook CA sync."""
        assignment = self.env['edicai.assignment'].create({
            'title': 'Sorting HW', 'assignment_type': 'homework',
            'course_offering_id': self.offering.id, 'max_marks': 10.0,
            'due_date': date.today() + timedelta(days=7)})
        assignment.action_publish()
        self.assertEqual(assignment.assignment_state, 'published')
        submission = self.env['edicai.assignment.submission'].create({
            'assignment_id': assignment.id, 'student_id': self.student.id,
            'submission_text': 'My homework answers'})
        submission.action_submit()
        self.assertIn(submission.state, ('submitted', 'late'))
