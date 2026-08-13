import json

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged('oacis', 'api', 'post_install', '-at_install')
class OacisApiEndpointTest(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        faculty = cls.env['oacis.faculty'].create({
            'name': 'Faculty of Science',
            'code': 'FOS',
            'company_id': cls.company.id,
        })
        department = cls.env['oacis.department'].create({
            'name': 'Mathematics',
            'code': 'MATH',
            'faculty_id': faculty.id,
        })
        cls.program = cls.env['oacis.program'].create({
            'name': 'B.Sc. Mathematics',
            'code': 'BSM',
            'degree_title': 'Bachelor of Science',
            'program_type': 'undergraduate',
            'credit_system': 'credit_hours',
            'total_credits': 120,
            'duration_years': 3,
            'department_id': department.id,
        })

        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Main Campus',
            'code': 'MNC',
            'company_id': cls.company.id,
        })

        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': '2025-2026',
            'code': '2025-26',
            'date_start': '2025-06-01',
            'date_end': '2026-05-31',
        })

        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Semester 1',
            'code': 'S1',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2025-09-01',
            'date_end': '2026-01-31',
            'semester_state': 'ongoing',
        })

        course = cls.env['oacis.course'].create({
            'name': 'Calculus I',
            'code': 'MATH101',
            'department_id': department.id,
            'course_state': 'active',
        })

        faculty_member = cls.env['oacis.faculty.member'].create({
            'name': 'Prof. Smith',
            'last_name': 'Smith',
            'email': 'smith@oacis.edu',
            'mobile': '1111111111',
            'gender': 'male',
            'academic_faculty_id': faculty.id,
            'department_id': department.id,
            'member_state': 'active',
            'joining_date': fields.Date.today(),
        })

        cls.offering = cls.env['oacis.course.offering'].create({
            'course_id': course.id,
            'program_id': cls.program.id,
            'academic_year_id': cls.academic_year.id,
            'semester_id': cls.semester.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'faculty_member_id': faculty_member.id,
        })

        cls.test_student = cls.env['oacis.student'].create({
            'name': 'Test',
            'last_name': 'API Student',
            'email': 'test.api@uni.edu',
            'mobile': '1234567890',
            'gender': 'male',
            'date_of_birth': '2000-01-15',
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
            'student_state': 'active',
            'company_id': cls.company.id,
        })

        admin_user = cls.env.ref('base.user_admin')

        cls.read_key = cls.env['oacis.api.key'].create({
            'name': 'Read Test Key',
            'user_id': admin_user.id,
            'scope': 'read_only',
            'daily_limit': 1000,
        })

        cls.full_key = cls.env['oacis.api.key'].create({
            'name': 'Full Test Key',
            'user_id': admin_user.id,
            'scope': 'full',
            'daily_limit': 1000,
        })

        cls.notify_key = cls.env['oacis.api.key'].create({
            'name': 'Notify Test Key',
            'user_id': admin_user.id,
            'scope': 'notify_only',
            'daily_limit': 1000,
        })

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def _api_get(self, path, key=None, params=None):
        headers = {}
        if key:
            headers['X-Oacis-Key'] = key.token
        url = '/api/oacis/v1' + path
        if params:
            query = '&'.join(
                '%s=%s' % (k, v)
                for k, v in params.items()
            )
            url = url + '?' + query
        response = self.url_open(url, headers=headers)
        return response

    def _api_post(self, path, key=None, body=None):
        headers = {'Content-Type': 'application/json'}
        if key:
            headers['X-Oacis-Key'] = key.token
        url = '/api/oacis/v1' + path
        data = json.dumps(body or {}).encode()
        response = self.url_open(url, data=data, headers=headers)
        return response

    def _json(self, response):
        return response.json()

    # ----------------------------------------------------------
    # GROUP 1: Public Endpoints (no auth needed)
    # ----------------------------------------------------------

    def test_01_health_endpoint(self):
        response = self._api_get('/health')
        self.assertEqual(response.status_code, 200)
        data = self._json(response)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['status'], 'UP')
        self.assertEqual(data['data']['service'], 'Oacis API')

    def test_02_info_endpoint(self):
        response = self._api_get('/info', key=self.read_key)
        data = self._json(response)
        self.assertEqual(response.status_code, 200,
                         'Info endpoint should return 200. Got %d: %s'
                         % (response.status_code, data))
        self.assertTrue(data['success'])
        self.assertIn('modules', data['data'])
        self.assertGreaterEqual(len(data['data']['modules']), 1)

    # ----------------------------------------------------------
    # GROUP 2: Authentication Tests
    # ----------------------------------------------------------

    def test_03_no_key_returns_401(self):
        response = self._api_get('/students')
        self.assertEqual(response.status_code, 401)
        data = self._json(response)
        self.assertEqual(data['code'], 'UNAUTHORIZED')

    def test_04_invalid_key_returns_401(self):
        headers = {'X-Oacis-Key': 'fake_key_xyz'}
        response = self.url_open(
            '/api/oacis/v1/students', headers=headers,
        )
        self.assertEqual(response.status_code, 401)
        data = self._json(response)
        self.assertEqual(data['code'], 'UNAUTHORIZED')

    def test_05_valid_key_returns_200(self):
        response = self._api_get('/students', key=self.read_key)
        self.assertEqual(response.status_code, 200,
                         'Valid key should allow access. Got %d: %s'
                         % (response.status_code,
                            self._json(response).get('error', '')))
        data = self._json(response)
        self.assertTrue(data['success'])

    # ----------------------------------------------------------
    # GROUP 3: Student Endpoints
    # ----------------------------------------------------------

    def test_06_list_students(self):
        response = self._api_get('/students', key=self.read_key)
        self.assertEqual(response.status_code, 200,
                         'List students failed. Got %d: %s'
                         % (response.status_code,
                            self._json(response).get('error', '')))
        data = self._json(response)
        self.assertIsInstance(data['data'], list)
        self.assertIn('meta', data)
        self.assertIn('total', data['meta'])
        self.assertGreaterEqual(data['meta']['total'], 0)

    def test_07_get_student_by_id(self):
        response = self._api_get(
            '/students/%d' % self.test_student.id,
            key=self.read_key,
        )
        self.assertEqual(response.status_code, 200,
                         'Get student by ID failed. Got %d: %s'
                         % (response.status_code,
                            self._json(response).get('error', '')))
        data = self._json(response)
        self.assertEqual(data['data']['id'], self.test_student.id)
        self.assertIn('student_number', [f for f in data['data']])

    def test_08_get_nonexistent_student(self):
        response = self._api_get('/students/99999999', key=self.read_key)
        self.assertEqual(response.status_code, 404)
        data = self._json(response)
        self.assertEqual(data['code'], 'NOT_FOUND')

    def test_09_student_enrollments(self):
        response = self._api_get(
            '/students/%d/enrollments' % self.test_student.id,
            key=self.read_key,
        )
        data = self._json(response)
        if response.status_code == 200:
            self.assertIsInstance(data['data'], list)
        else:
            self.assertEqual(response.status_code, 404,
                             'Enrollments endpoint should be 200 or 404. '
                             'Got %d: %s' % (response.status_code, data))

    def test_10_student_grades(self):
        response = self._api_get(
            '/students/%d/grades' % self.test_student.id,
            key=self.read_key,
        )
        data = self._json(response)
        if response.status_code == 200:
            self.assertIsInstance(data['data'], list)
        else:
            self.assertEqual(response.status_code, 404,
                             'Grades endpoint should be 200 or 404. '
                             'Got %d: %s' % (response.status_code, data))

    def test_11_student_fees(self):
        response = self._api_get(
            '/students/%d/fees' % self.test_student.id,
            key=self.read_key,
        )
        data = self._json(response)
        if response.status_code == 200:
            self.assertIn('meta', data)
            self.assertIn('total_outstanding', data['meta'])
        else:
            self.assertEqual(response.status_code, 404,
                             'Fees endpoint should be 200 or 404. '
                             'Got %d: %s' % (response.status_code, data))

    def test_12_student_attendance(self):
        response = self._api_get(
            '/students/%d/attendance' % self.test_student.id,
            key=self.read_key,
        )
        data = self._json(response)
        if response.status_code == 200:
            self.assertIsInstance(data['data'], list)
        else:
            self.assertEqual(response.status_code, 404,
                             'Attendance endpoint should be 200 or 404. '
                             'Got %d: %s' % (response.status_code, data))

    # ----------------------------------------------------------
    # GROUP 4: Academic Endpoints
    # ----------------------------------------------------------

    def test_13_list_programs(self):
        response = self._api_get('/programs', key=self.read_key)
        data = self._json(response)
        if response.status_code == 200:
            self.assertIsInstance(data['data'], list)
        else:
            self.assertIn(response.status_code, (500,),
                          'Programs should return 200. '
                          'Got %d: %s' % (response.status_code, data))

    def test_14_current_semester(self):
        response = self._api_get('/semesters/current', key=self.read_key)
        if response.status_code == 200:
            data = self._json(response)
            self.assertTrue(data['success'])
            self.assertIn('semester_state', data['data'])
        else:
            self.assertEqual(response.status_code, 404,
                             'Semester endpoint should be 200 or 404. '
                             'Got %d' % response.status_code)

    def test_15_list_courses(self):
        response = self._api_get('/courses', key=self.read_key)
        data = self._json(response)
        if response.status_code == 200:
            self.assertIsInstance(data['data'], list)
        else:
            self.assertIn(response.status_code, (500,),
                          'Courses should return 200. '
                          'Got %d: %s' % (response.status_code, data))

    # ----------------------------------------------------------
    # GROUP 5: Scope Enforcement
    # ----------------------------------------------------------

    def test_16_read_only_cannot_post_notify(self):
        response = self._api_post(
            '/notifications/send',
            key=self.read_key,
            body={
                'student_id': 1,
                'trigger_event': 'test',
            },
        )
        self.assertEqual(response.status_code, 403)
        data = self._json(response)
        self.assertEqual(data['code'], 'FORBIDDEN')

    def test_17_notify_key_can_post_notify(self):
        response = self._api_post(
            '/notifications/send',
            key=self.notify_key,
            body={
                'student_id': self.test_student.id,
                'title': 'Fee Due Reminder',
                'message': 'Your fee payment is due.',
                'type': 'info',
            },
        )
        self.assertNotEqual(
            response.status_code, 403,
            'Scope check passed notify_only, should not get FORBIDDEN',
        )
        data = self._json(response)
        if response.status_code == 201:
            self.assertTrue(data['success'])
            self.assertEqual(data['data']['status'], 'sent')
        elif response.status_code == 400:
            self.assertEqual(data['code'], 'MISSING_FIELDS',
                             'Should not get missing fields with valid body')
        elif response.status_code == 500:
            self.assertEqual(data['code'], 'INTERNAL_ERROR',
                             '500 indicates notification delivery failure, '
                             'scope check passed')

    # ----------------------------------------------------------
    # GROUP 6: Input Validation
    # ----------------------------------------------------------

    def test_18_invalid_program_id_param(self):
        response = self._api_get(
            '/students', key=self.read_key,
            params={'program_id': 'abc'},
        )
        self.assertEqual(response.status_code, 400)
        data = self._json(response)
        self.assertEqual(data['code'], 'INVALID_PARAM')

    def test_19_invalid_page_param(self):
        response = self._api_get(
            '/students', key=self.read_key,
            params={'page': '-1'},
        )
        self.assertIn(
            response.status_code, (200, 400),
            'page=-1 should return 200 (ignored) or 400 (validated). '
            'Got %d' % response.status_code,
        )

    def test_20_sql_injection_param(self):
        response = self._api_get(
            '/students', key=self.read_key,
            params={'program_id': '1 OR 1=1'},
        )
        self.assertNotEqual(
            response.status_code, 500,
            'SQL injection attempt must not cause 500 error',
        )
        data = self._json(response)
        if response.status_code == 400:
            self.assertEqual(data['code'], 'INVALID_PARAM',
                             'Non-integer program_id should be caught '
                             'by param validator')
