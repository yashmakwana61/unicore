"""Edicai Demo — institution-aware demo data generator.

Conceptual flow::

    res.company.institution_profile_id -> institution_type
        -> demo profile (volumes) + dataset (names / structure)
        -> feature gates via company.has_feature(code)
        -> records created in dependency-safe order, tracked in registry

Only the dataset matching the company's institution type is generated, so a
K-12 school never receives university structures and vice versa.  All demo
rows are registered in ``edicai.demo.record`` scoped to the company, which
makes reset safe for multi-institution databases.

Re-running for the same company requires ``reset_first=True`` (the wizard
default) or raises a UserError — this is what keeps repeated execution
duplicate-free.
"""

import logging
import random
from datetime import datetime, timedelta

from odoo import _, api, models
from odoo.exceptions import UserError

from .demo_datasets import (
    DATASETS,
    FIRST_NAMES_FEMALE,
    FIRST_NAMES_MALE,
    LAST_NAMES,
    TERMS,
)

_logger = logging.getLogger(__name__)

# Reverse-dependency order is handled by registry sequence; this lists the
# creation order for readability and for the run summary.
BUILD_STEPS = [
    'accounting', 'campus', 'structure', 'calendar', 'people', 'admissions',
    'enrollments', 'timetable', 'attendance', 'exams', 'grading', 'fees',
    'support',
]


class EdicaiDemoGenerator(models.AbstractModel):
    _name = 'edicai.demo.generator'
    _description = 'Edicai Institution-Aware Demo Generator'

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------
    @api.model
    def resolve_institution_type(self, company):
        """Map a company to its demo dataset key.

        Uses the existing institution architecture: companies without a
        profile (or with the legacy university profile) resolve to the
        legacy university dataset.
        """
        company.ensure_one()
        profile = company.institution_profile_id
        if not profile or profile.is_legacy_university:
            return 'legacy'
        itype = profile.institution_type or 'university'
        if itype not in DATASETS:
            _logger.warning(
                'Unknown institution_type %r on %s; falling back to legacy.',
                itype, company.display_name)
            return 'legacy'
        return itype

    @api.model
    def existing_demo_count(self, company):
        return self.env['edicai.demo.record'].search_count([
            ('company_id', '=', company.id),
        ])

    @api.model
    def generate(self, company, demo_profile=None, reset_first=True):
        """Generate the institution-specific demo dataset for ``company``."""
        company.ensure_one()
        if reset_first and self.existing_demo_count(company):
            self.reset_company_demo(company)
        elif self.existing_demo_count(company):
            raise UserError(_(
                'Institution %s already has demo data. '
                'Reset it first, or enable "Replace existing demo data".',
            ) % company.display_name)

        itype = self.resolve_institution_type(company)
        dataset = DATASETS[itype]
        if demo_profile is None:
            demo_profile = self.env['edicai.demo.profile'].search([
                ('institution_type', '=', itype if itype != 'legacy' else 'university'),
            ], limit=1)
        run_key = 'demo-%s-%s' % (itype, company.id)
        builder = _DemoBuilder(self.env, company, itype, dataset,
                               demo_profile, run_key)
        summary = builder.build()
        summary['institution_type'] = itype
        summary['run_key'] = run_key
        return summary

    @api.model
    def reset_company_demo(self, company):
        """Delete only generator-created rows for ``company``.

        Reverse creation order; registry rows are removed as their targets
        are deleted.  Real institution data (never registered) is untouched.
        """
        company.ensure_one()
        entries = self.env['edicai.demo.record'].search([
            ('company_id', '=', company.id),
        ])
        removed = 0
        skipped = []
        for entry in entries:
            model_name, res_id = entry.model_name, entry.res_id
            target = entry._target()
            entry.unlink()
            if target:
                try:
                    # Per-record savepoint: a real (non-demo) record may still
                    # reference a demo row via RESTRICT. Roll back just that
                    # delete, keep the blocker, and continue with the rest.
                    with self.env.cr.savepoint():
                        target.unlink()
                    removed += 1
                except Exception:  # noqa: BLE001 - best effort cleanup
                    skipped.append('%s #%s' % (model_name, res_id))
                    _logger.warning(
                        'Could not delete demo %s #%s during reset; '
                        'it may still be referenced by real data.',
                        model_name, res_id, exc_info=True)
        return {'removed': removed, 'skipped': skipped}


class _DemoBuilder:
    """Stateful per-run builder; keeps generate() readable."""

    def __init__(self, env, company, itype, dataset, profile, run_key):
        # Odoo 19: scope the environment to the target company via context
        # (with_company was removed). company_id defaults still resolve.
        self.env = env(context=dict(
            env.context,
            allowed_company_ids=[company.id],
            force_company=company.id,
        ))
        self.company = company
        self.itype = itype
        self.ds = dataset
        self.profile = profile
        self.run_key = run_key
        self.seq = 0
        self.rng = random.Random(abs(hash('edicai-demo-%s' % itype)) % (2 ** 31))
        self.counts = {}
        # Cross-step references.
        self.campus = None
        self.rooms = []
        self.faculties = {}
        self.departments = {}
        self.units = {}
        self.programs = {}
        self.courses = []
        self.offerings = []
        self.faculty_members = []
        self.students = []
        self.year = None
        self.terms = []
        self.currency = company.currency_id
        self.country = company.country_id or self.env.ref(
            'base.in', raise_if_not_found=False)

    # -- helpers ------------------------------------------------------
    def _vol(self, field, default):
        if self.profile and self.profile[field]:
            return self.profile[field]
        return default

    def _track(self, record, label=None):
        self.seq += 1
        self.env['edicai.demo.record'].log(
            self.run_key, record, self.company, self.itype, self.seq)
        key = (label or record._name).split('.')[-1]
        self.counts[key] = self.counts.get(key, 0) + 1
        return record

    def _make(self, model, label=None, **vals):
        if model not in self.env:
            _logger.warning('Skipping demo %s: model not installed.', model)
            return None
        record = self.env[model].create(vals)
        return self._track(record, label=label or model)

    def _has_feature(self, code):
        company = self.company
        if hasattr(company, 'has_feature'):
            try:
                return company.has_feature(code)
            except Exception:  # noqa: BLE001 - profile data may be absent
                _logger.warning('has_feature(%s) failed; assuming enabled.', code)
        return True

    def _email(self, prefix, i):
        return '%s%s@demo.%s.local' % (prefix, i, self.itype)

    def _pick_year_window(self):
        """Choose a July-June window that overlaps no existing academic year
        of the company (the legacy static dataset ships 2026-27). All demo
        dates derive from the chosen base year so the dataset stays
        internally consistent."""
        year_model = self.env['edicai.academic.year']
        base = 2026
        for _ in range(20):
            start = '%d-07-01' % base
            end = '%d-06-30' % (base + 1)
            clash = year_model.search([
                ('company_id', '=', self.company.id),
                ('date_start', '<=', end),
                ('date_end', '>=', start),
            ], limit=1)
            if not clash:
                return base
            base -= 1
        raise UserError(_(
            'No free academic-year window found for demo data on %s.') % (
                self.company.display_name,))

    def _code(self, code, size=20):
        """Namespace generator codes so they never collide with legacy,
        manual, or other-profile data in the same company."""
        namespaced = 'DEMO-%s' % code
        return namespaced[-size:] if len(namespaced) > size else namespaced

    def _alpha_code(self, code, size=10):
        """Letters-only uppercase variant for faculty codes (isalpha rule)."""
        cleaned = ''.join(ch for ch in code.upper() if ch.isalpha())
        namespaced = '%sX' % cleaned
        return namespaced[-size:] if len(namespaced) > size else namespaced

    def _phone(self, i):
        return '+9191%07d' % (100000 + i)

    # -- build --------------------------------------------------------
    def build(self):
        self.y0 = self._pick_year_window()
        self.y1 = self.y0 + 1
        self._setup_accounting()
        self._build_campus()
        self._build_structure()
        self._build_calendar()
        self._build_people()
        self._build_admissions()
        self._build_enrollments()
        self._build_timetable()
        self._build_attendance()
        self._build_exams()
        self._build_grading()
        self._build_fees()
        self._build_support()
        return {'counts': dict(self.counts)}

    # -- steps ----------------------------------------------------------
    def _setup_accounting(self):
        self.env['edicai.demo.setup']._setup_accounting(company=self.company)

    def _build_campus(self):
        campus = self._make('edicai.campus', 'campus',
                            name='Demo Main Campus', code='DEMO',
                            company_id=self.company.id, campus_type='main',
                            is_main_campus=True,
                            city=self.company.city or 'Demo City',
                            country_id=self.country.id if self.country else False,
                            student_capacity=2000, campus_state='active')
        self.campus = campus
        building = self._make('edicai.building', 'building',
                              name='Demo Academic Block', code='DEMO-A',
                              campus_id=campus.id, building_type='academic',
                              construction_year=2020, sequence=10)
        floors = []
        for idx, fname in enumerate(['Ground Floor', 'First Floor']):
            floors.append(self._make('edicai.floor', 'floor', name=fname,
                                     floor_number=idx, building_id=building.id))
        room_defs = [
            ('Demo Lecture Hall', 'D101', 'lecture_hall', 60, 50),
            ('Demo Classroom', 'D102', 'classroom', 40, 35),
            ('Demo Computer Lab', 'D201', 'computer_lab', 30, 25),
        ]
        for name, code, rtype, cap, exam_cap in room_defs:
            self.rooms.append(self._make(
                'edicai.room', 'room', name=name, code=code,
                floor_id=floors[0].id if code != 'D201' else floors[1].id,
                room_type=rtype, capacity=cap, exam_capacity=exam_cap,
                has_projector=True, has_internet=True, room_state='available'))
        self._make('edicai.facility', 'facility', name='Demo Cafeteria',
                   facility_type='canteen', campus_id=campus.id, capacity=150)

    def _build_structure(self):
        for name, code in self.ds.get('faculties', []):
            self.faculties[code] = self._make(
                'edicai.faculty', 'faculty', name='Demo %s' % name,
                code=self._alpha_code(code),
                company_id=self.company.id, faculty_state='active', sequence=10)
        for name, code, fac_code in self.ds.get('departments', []):
            self.departments[code] = self._make(
                'edicai.department', 'department', name='Demo %s' % name,
                code=self._alpha_code(code),
                faculty_id=self.faculties[fac_code].id, dept_state='active')
        # Generic units (grade levels / batches) for non-rigid profiles.
        unit_type_ids = {
            t.code: t.id
            for t in self.env['edicai.academic.unit.type'].search([]) if t.code
        } if 'edicai.academic.unit.type' in self.env else {}
        for name, code, type_code in self.ds.get('units', []):
            vals = {'name': name, 'code': 'DEMO-%s' % code,
                    'company_id': self.company.id}
            if type_code in unit_type_ids:
                vals['unit_type_id'] = unit_type_ids[type_code]
            else:
                _logger.warning('Unit type %s not found; skipping unit %s.',
                                type_code, code)
                continue
            self.units[code] = self._make('edicai.academic.unit', 'unit', **vals)
        for spec in self.ds.get('programs', []):
            if len(spec) == 8:
                (name, code, dept_code, ptype, degree, years, credits, fee) = spec
                unit = None
            else:
                (name, code, unit_code, fee) = spec
                dept_code = next(iter(self.departments))
                ptype, degree, years, credits = self._program_kind()
                unit = self.units[unit_code]
            vals = {'name': 'Demo %s' % name, 'code': self._code(code, 20),
                    'department_id': self.departments[dept_code].id,
                    'program_type': ptype, 'degree_title': degree,
                    'duration_years': years, 'credit_system': 'credit_hours',
                    'total_credits': credits, 'program_state': 'active',
                    'tuition_fee_per_semester': fee}
            if unit is not None:
                vals['academic_unit_id'] = unit.id
                vals['cohort_kind'] = self._cohort_kind()
            self.programs[code] = self._make('edicai.program', 'program', **vals)
        for name, code, prog_code in self.ds.get('specialisations', []):
            self._make('edicai.specialisation', 'specialisation', name=name,
                       code=self._code(code, 20),
                       program_id=self.programs[prog_code].id,
                       min_credits=30)

    def _program_kind(self):
        if self.itype in ('school',):
            return ('diploma', 'School Diploma', 1.0, 10)
        return ('certificate', 'Completion Certificate', 1.0, 10)

    def _cohort_kind(self):
        if self.itype == 'school':
            return 'grade_batch'
        if self.itype in ('training', 'academy', 'coaching'):
            return 'rolling'
        return 'academic_year'

    def _build_calendar(self):
        year_type = self.ds.get('year_type', 'semester')
        year_code = 'DEMO-AY-%d' % self.y0
        # Only one active year per institution: stay 'confirmed' when the
        # company already runs an active year (e.g. the legacy dataset).
        has_active = bool(self.env['edicai.academic.year'].search([
            ('company_id', '=', self.company.id),
            ('year_state', '=', 'active'),
        ], limit=1))
        self.year = self._make(
            'edicai.academic.year', 'year',
            name='Demo Academic Year %d-%d' % (self.y0, self.y1),
            code=year_code, company_id=self.company.id,
            date_start='%d-07-01' % self.y0, date_end='%d-06-30' % self.y1,
            year_type=year_type,
            year_state='confirmed' if has_active else 'active')
        term_defs = TERMS.get(year_type, TERMS['semester'])
        dates = [('%d-07-15' % self.y0, '%d-11-30' % self.y0, 'ongoing'),
                 ('%d-01-05' % self.y1, '%d-05-31' % self.y1, 'confirmed')]
        for idx, ((stype, label), (dstart, dend, state)) in enumerate(
                zip(term_defs, dates)):
            exam_start = (datetime.strptime(dend, '%Y-%m-%d').date()
                          - timedelta(days=18)).isoformat()
            self.terms.append(self._make(
                'edicai.semester', 'semester',
                name='Demo %s %d' % (label, self.y0),
                code='DEMO-%s-%d' % (stype.upper(), idx + 1),
                academic_year_id=self.year.id, semester_type=stype, sequence=10 * (idx + 1),
                date_start=dstart, date_end=dend,
                registration_start='%d-07-01' % self.y0,
                registration_end='%d-07-20' % self.y0,
                exam_start=exam_start, exam_end=dend, semester_state=state))
        holidays = [
            ('Demo Cultural Break', '%d-10-20' % self.y0, '%d-10-24' % self.y0, 'cultural'),
            ('Demo National Holiday', '%d-08-15' % self.y0, '%d-08-15' % self.y0, 'national'),
        ]
        for name, dstart, dend, htype in holidays:
            self._make('edicai.holiday', 'holiday', name=name,
                       company_id=self.company.id, academic_year_id=self.year.id,
                       semester_id=self.terms[0].id, date_start=dstart, date_end=dend,
                       holiday_type=htype, affects_attendance=True)

    def _build_people(self):
        dept_codes = list(self.departments)
        n_faculty = self._vol('faculty_count', 6)
        designations = ['professor', 'assoc_professor', 'asst_professor',
                        'lecturer', 'instructor']
        for i in range(n_faculty):
            dept = self.departments[dept_codes[i % len(dept_codes)]]
            male = (i % 2 == 0)
            member = self._make(
                'edicai.faculty.member', 'faculty.member',
                name=self._first(male, i), last_name=LAST_NAMES[i % len(LAST_NAMES)],
                gender='male' if male else 'female',
                date_of_birth='19%02d-%02d-%02d' % (75 + (i % 15), 1 + (i % 12), 1 + (i % 27)),
                email=self._email('faculty.', i), mobile=self._phone(i),
                company_id=self.company.id,
                academic_faculty_id=dept.faculty_id.id, department_id=dept.id,
                designation=designations[i % len(designations)],
                employment_type='full_time', joining_date='2020-07-01',
                member_state='active', primary_campus_id=self.campus.id)
            self.faculty_members.append(member)
        for i in range(min(2, n_faculty)):
            self._make('edicai.faculty.qualification', 'qualification',
                       faculty_member_id=self.faculty_members[i].id,
                       qualification_level='masters' if i else 'phd',
                       degree_title='M.Sc Demo Field' if i else 'PhD Demo Field',
                       field_of_study='Demo Studies', institution_name='Demo University',
                       year_of_completion=2015 + i, is_highest=True, is_verified=True)
        roles = ['registrar', 'admin_officer', 'finance_officer']
        for i in range(self._vol('staff_count', 1)):
            self._make('edicai.staff.member', 'staff.member',
                       name=self._first(True, 100 + i),
                       last_name=LAST_NAMES[(100 + i) % len(LAST_NAMES)],
                       gender='male', email=self._email('staff.', i),
                       mobile=self._phone(900 + i), company_id=self.company.id,
                       campus_id=self.campus.id, staff_role=roles[i % len(roles)],
                       employment_type='full_time', joining_date='2021-01-10',
                       staff_state='active')
        self._build_courses()
        self._build_students()

    def _first(self, male, i):
        pool = FIRST_NAMES_MALE if male else FIRST_NAMES_FEMALE
        return pool[i % len(pool)]

    def _build_courses(self):
        dept_codes = list(self.departments)
        prog_codes = list(self.programs)
        wanted = self._vol('course_count', 8)
        for i, spec in enumerate(self.ds.get('courses', [])[:wanted]):
            if len(spec) == 6:
                (name, code, dept_code, cat, ctype, credits) = spec
            else:
                (name, code, cat, ctype, credits) = spec
                dept_code = dept_codes[i % len(dept_codes)]
            course = self._make(
                'edicai.course', 'course', name='Demo %s' % name,
                code=self._code(code, 20),
                company_id=self.company.id,
                department_id=self.departments[dept_code].id,
                course_category=cat, course_type=ctype, credit_hours=credits,
                theory_hours=credits, internal_assessment_marks=40.0,
                external_assessment_marks=60.0, passing_marks=40.0,
                course_state='active')
            self.courses.append(course)
        first_prog = self.programs[prog_codes[0]]
        curriculum = self._make(
            'edicai.curriculum', 'curriculum',
            name='Demo Curriculum %d' % self.y0, program_id=first_prog.id,
            version='1.0', effective_from_year=self.y0,
            curriculum_state='active')
        for i, course in enumerate(self.courses[:4]):
            self._make('edicai.curriculum.line', 'curriculum.line',
                       curriculum_id=curriculum.id, course_id=course.id,
                       semester_number=1, sequence=10 * (i + 1), is_mandatory=True)
        for i, course in enumerate(self.courses):
            program = self.programs[prog_codes[i % len(prog_codes)]]
            instructor = self.faculty_members[i % len(self.faculty_members)] \
                if self.faculty_members else None
            vals = {'course_id': course.id, 'program_id': program.id,
                    'semester_number': 1, 'academic_year_id': self.year.id,
                    'semester_id': self.terms[0].id, 'company_id': self.company.id,
                    'campus_id': self.campus.id, 'section_code': 'A',
                    'max_enrollment': 40, 'min_enrollment': 5,
                    'offering_state': 'open'}
            if instructor is not None:
                vals['faculty_member_id'] = instructor.id
            self.offerings.append(self._make('edicai.course.offering', 'offering', **vals))

    def _build_students(self):
        prog_codes = list(self.programs)
        n_students = self._vol('student_count', 60)
        grade_units = [u for u in self.units.values()]
        every_n = self._vol('guardian_every_n', 2) if 'edicai.guardian' in self.env else 0
        for i in range(n_students):
            male = (i % 2 == 0)
            program = self.programs[prog_codes[i % len(prog_codes)]]
            vals = {
                'name': self._first(male, i),
                'last_name': LAST_NAMES[(i * 3) % len(LAST_NAMES)],
                'gender': 'male' if male else 'female',
                'date_of_birth': '20%02d-%02d-%02d' % (2 + (i % 4), 1 + (i % 12), 1 + (i % 27)),
                'email': self._email('student.', i), 'mobile': self._phone(100 + i),
                'company_id': self.company.id, 'campus_id': self.campus.id,
                'program_id': program.id, 'batch_year': self.y0,
                'admission_date': '%d-07-%02d' % (self.y0, 1 + (i % 27)),
                'current_year_of_study': 1,
                'current_semester_id': self.terms[0].id,
                'student_state': 'enrolled',
            }
            if grade_units and self.itype == 'school':
                vals['grade_level_id'] = grade_units[i % len(grade_units)].id
            if self._cohort_kind() == 'rolling':
                vals['cohort_start_date'] = '%d-07-01' % self.y0
            student = self._make('edicai.student', 'student', **vals)
            self.students.append(student)
            if i % 3 == 0:
                self._make('edicai.student.emergency.contact', 'emergency.contact',
                           student_id=student.id, name='Emergency Contact %d' % i,
                           relationship='father' if male else 'mother',
                           mobile=self._phone(800 + i))
            if every_n and i % every_n == 0:
                guardian = self._make(
                    'edicai.guardian', 'guardian', name=self._first(not male, i + 50),
                    last_name=student.last_name, gender='female' if male else 'male',
                    email=self._email('guardian.', i), mobile=self._phone(500 + i),
                    company_id=self.company.id)
                self._make('edicai.guardian.student.rel', 'guardian.rel',
                           guardian_id=guardian.id, student_id=student.id,
                           relationship_type='mother' if male else 'father',
                           is_primary_guardian=True, is_financial_guarantor=True,
                           company_id=self.company.id)

    def _build_admissions(self):
        if 'edicai.admission.cycle' not in self.env:
            return
        cycle = self._make(
            'edicai.admission.cycle', 'admission.cycle',
            name='Demo Admissions %d' % self.y0,
            code='DEMO-ADM', campus_id=self.campus.id, academic_year_id=self.year.id,
            start_date='%d-03-01' % self.y0, end_date='%d-06-30' % self.y0,
            state='closed', company_id=self.company.id)
        for code, program in self.programs.items():
            self._make('edicai.admission.cycle.seat', 'admission.seat',
                       cycle_id=cycle.id, program_id=program.id,
                       total_seats=60, reserved_seats=15)
        states = ['inquiry', 'applied', 'under_review', 'shortlisted',
                  'offer_sent', 'confirmed', 'rejected', 'waitlisted']
        prog_codes = list(self.programs)
        for i in range(self._vol('applicants_count', 6)):
            male = (i % 2 == 1)
            state = states[i % len(states)]
            program = self.programs[prog_codes[i % len(prog_codes)]]
            vals = {'name': self._first(male, 200 + i),
                    'last_name': LAST_NAMES[(200 + i) % len(LAST_NAMES)],
                    'email': self._email('applicant.', i), 'mobile': self._phone(400 + i),
                    'gender': 'male' if male else 'female',
                    'date_of_birth': '2005-01-%02d' % (1 + (i % 27)),
                    'cycle_id': cycle.id, 'campus_id': self.campus.id,
                    'program_id': program.id,
                    'aggregate_percentage': 65.0 + (i * 3.5) % 30,
                    'state': state, 'company_id': self.company.id}
            if program.cohort_kind == 'grade_batch' and program.academic_unit_id:
                vals['grade_level_id'] = program.academic_unit_id.id
            if state == 'rejected':
                vals['rejection_reason'] = 'Incomplete documentation (demo)'
            self._make('edicai.admission.applicant', 'applicant', **vals)

    def _build_enrollments(self):
        model = 'edicai.enrollment'
        if model not in self.env:
            return
        self.enrollments = []
        for student in self.students:
            mine = [o for o in self.offerings
                    if o.program_id.id == student.program_id.id] or self.offerings[:2]
            for offering in mine[:2]:
                self.enrollments.append(self.env[model].with_context(
                    force_enrollment_override=True, auto_waitlist=False).create({
                        'student_id': student.id,
                        'course_offering_id': offering.id,
                        'enrollment_state': 'registered',
                        'registration_type': 'self',
                    }))
                self.seq += 1
                self.env['edicai.demo.record'].log(
                    self.run_key, self.enrollments[-1], self.company,
                    self.itype, self.seq)
        self.counts['enrollment'] = len(self.enrollments)

    def _free_start(self, duration, after=7.0):
        """Earliest start time with no overlap against existing company slots
        (seeded day slots and legacy demo slots included)."""
        taken = [(s.start_time, s.end_time)
                 for s in self.env['edicai.time.slot'].search(
                     [('company_id', '=', self.company.id)])]
        candidate = after
        while candidate + duration <= 22.0:
            if all(candidate + duration <= s or candidate >= e for s, e in taken):
                return round(candidate, 2)
            candidate = round(candidate + 0.25, 2)
        raise UserError(_('No free demo time slot found for %s.') % (
            self.company.display_name,))

    def _build_timetable(self):
        if 'edicai.timetable.entry' not in self.env:
            return
        self.tt_entries = []
        lec_start = self._free_start(1.0)
        lab_start = self._free_start(1.5, after=lec_start + 1.0)
        slots = [
            self._make('edicai.time.slot', 'time.slot', name='Demo Period 1',
                       start_time=lec_start, end_time=lec_start + 1.0,
                       sequence=10,
                       company_id=self.company.id, slot_type='lecture'),
            self._make('edicai.time.slot', 'time.slot', name='Demo Lab Slot',
                       start_time=lab_start, end_time=lab_start + 1.5,
                       sequence=20,
                       company_id=self.company.id, slot_type='lab'),
        ]
        for i, offering in enumerate(self.offerings):
            self.tt_entries.append(self._make(
                'edicai.timetable.entry', 'timetable.entry',
                course_offering_id=offering.id,
                day_of_week=str(1 + (i % 5)),
                time_slot_id=slots[i % len(slots)].id,
                room_id=self.rooms[i % len(self.rooms)].id,
                instructor_id=offering.faculty_member_id.id
                if offering.faculty_member_id else self.faculty_members[0].id,
                semester_id=self.terms[0].id, entry_state='confirmed'))

    def _build_attendance(self):
        if 'edicai.attendance.session' not in self.env or not getattr(
                self, 'tt_entries', None):
            return
        self._make('edicai.attendance.policy', 'attendance.policy',
                   name='Demo 75% Policy', company_id=self.company.id,
                   policy_scope='global', min_attendance_percentage=75.0,
                   warning_threshold_percentage=80.0,
                   is_exam_eligibility_linked=True)
        n_sessions = self._vol('attendance_sessions_per_offering', 2)
        for entry in self.tt_entries:
            for s in range(n_sessions):
                session = self._make(
                    'edicai.attendance.session', 'attendance.session',
                    timetable_entry_id=entry.id,
                    session_date='%d-08-%02d' % (self.y0, 4 + s * 7),
                    session_state='closed')
                enrolls = [e for e in self.enrollments
                           if e.course_offering_id.id == entry.course_offering_id.id]
                for j, enroll in enumerate(enrolls):
                    if j % 9 == 8:
                        status, late = 'absent', {}
                    elif j % 7 == 6:
                        status, late = 'late', {'late_minutes': 5}
                    else:
                        status, late = 'present', {}
                    self._make('edicai.attendance.record', 'attendance.record',
                               session_id=session.id, student_id=enroll.student_id.id,
                               status=status, **late)

    def _build_exams(self):
        if 'edicai.exam.schedule' not in self.env:
            return
        self.exams = []
        for i, offering in enumerate(self.offerings):
            for exam_type, edate, marks in (
                    ('midterm', '%d-09-15' % self.y0, 40.0),
                    ('final', '%d-11-20' % self.y0, 60.0)):
                self.exams.append(self._make(
                    'edicai.exam.schedule', 'exam.schedule',
                    name='Demo %s - %s' % (exam_type.title(), offering.course_id.code),
                    course_offering_id=offering.id, company_id=self.company.id,
                    exam_type=exam_type, exam_date=edate,
                    exam_start_time=9.0, exam_end_time=12.0,
                    venue_ids=[(6, 0, [self.rooms[i % len(self.rooms)].id])],
                    chief_invigilator_id=offering.faculty_member_id.id
                    if offering.faculty_member_id else self.faculty_members[0].id,
                    exam_max_marks=marks, exam_state='published'))
        finals = [e for e in self.exams if e.exam_type == 'final']
        for i, final in enumerate(finals):
            enrolls = [e for e in self.enrollments
                       if e.course_offering_id.id == final.course_offering_id.id]
            for j, enroll in enumerate(enrolls[:6]):
                ticket = self._make(
                    'edicai.exam.hall.ticket', 'hall.ticket',
                    exam_schedule_id=final.id, student_id=enroll.student_id.id,
                    ticket_state='approved')
                if j < 3:
                    self._make('edicai.exam.seating', 'seating',
                               exam_schedule_id=final.id, hall_ticket_id=ticket.id,
                               room_id=self.rooms[0].id, seat_number=j + 1)

    def _build_grading(self):
        if 'edicai.grade.entry' not in self.env or not getattr(
                self, 'enrollments', None):
            return
        scale = self._make('edicai.grade.scale', 'grade.scale',
                           name='Demo 10-Point Scale', company_id=self.company.id,
                           max_gpa=10.0)
        for letter, lmin, lmax, point, passing in [
                ('O', 90.0, 100.0, 10.0, True), ('A+', 80.0, 90.0, 9.0, True),
                ('A', 70.0, 80.0, 8.0, True), ('B+', 60.0, 70.0, 7.0, True),
                ('B', 50.0, 60.0, 6.0, True), ('C', 40.0, 50.0, 5.0, True),
                ('F', 0.0, 40.0, 0.0, False)]:
            self._make('edicai.grade.scale.line', 'grade.scale.line',
                       scale_id=scale.id, letter_grade=letter, min_percentage=lmin,
                       max_percentage=lmax, grade_point=point, is_passing=passing)
        for i, enroll in enumerate(self.enrollments):
            if i % 5 > 1:  # grade ~40% of enrollments; rest stay in-progress
                continue
            internal = 25.0 + (i * 7) % 14
            external = 30.0 + (i * 11) % 29
            self._make('edicai.grade.entry', 'grade.entry',
                       enrollment_id=enroll.id, internal_marks=internal,
                       external_marks=external, entry_state='verified')

    def _build_fees(self):
        if 'edicai.fee.structure' not in self.env:
            return
        structures = {}
        for _code, program in self.programs.items():
            struct = self._make(
                'edicai.fee.structure', 'fee.structure',
                name='Demo Fee %s %d-%d' % (program.code, self.y0, self.y1), program_id=program.id,
                academic_year_id=self.year.id, company_id=self.company.id,
                currency_id=self.currency.id, structure_state='active')
            structures[program.id] = struct
            for j, (lname, ftype, amount) in enumerate(self.ds.get('fee_lines', [])):
                self._make('edicai.fee.structure.line', 'fee.structure.line',
                           structure_id=struct.id, name=lname, fee_type=ftype,
                           amount=amount, sequence=10 * (j + 1))
        states = ['paid', 'sent', 'partial', 'overdue']
        methods = ['online', 'cash', 'bank_transfer']
        for i, student in enumerate(self.students):
            struct = structures[student.program_id.id]
            lines = self.env['edicai.fee.structure.line'].search(
                [('structure_id', '=', struct.id)])
            total = sum(lines.mapped('amount'))
            state = states[i % len(states)]
            invoice = self._make(
                'edicai.fee.invoice', 'fee.invoice', student_id=student.id,
                semester_id=self.terms[0].id, academic_year_id=self.year.id,
                fee_structure_id=struct.id, company_id=self.company.id,
                currency_id=self.currency.id,
                invoice_date='%d-07-01' % self.y0,
                due_date='%d-08-15' % self.y0, invoice_state=state)
            for line in lines:
                self._make('edicai.fee.invoice.line', 'fee.invoice.line',
                           invoice_id=invoice.id, name=line.name,
                           amount=line.amount, fee_type=line.fee_type)
            if state == 'paid':
                self._make('edicai.fee.payment', 'fee.payment',
                           invoice_id=invoice.id, amount=total,
                           currency_id=self.currency.id,
                           payment_date='%d-07-15' % self.y0,
                           payment_method=methods[i % len(methods)],
                           payment_state='confirmed')
            elif state == 'partial':
                self._make('edicai.fee.payment', 'fee.payment',
                           invoice_id=invoice.id, amount=round(total / 2, 2),
                           currency_id=self.currency.id,
                           payment_date='%d-07-20' % self.y0,
                           payment_method='bank_transfer', payment_state='confirmed')

    def _build_support(self):
        if self._has_feature('SCHOLARSHIP') and 'edicai.scholarship.program' in self.env:
            program = self._make(
                'edicai.scholarship.program', 'scholarship.program',
                name='Demo Merit Scholarship', code='DEMO-MERIT',
                company_id=self.company.id, academic_year_id=self.year.id,
                scholarship_type='merit', funding_source='institutional',
                award_type='cash_grant', award_amount=10000.0,
                total_quota=5, min_cgpa=8.0, program_state='open')
            for i, student in enumerate(self.students[:3]):
                app = self._make(
                    'edicai.scholarship.application', 'scholarship.application',
                    student_id=student.id, scholarship_program_id=program.id,
                    company_id=self.company.id,
                    application_state='approved' if i < 2 else 'submitted')
                if i < 2:
                    self._make('edicai.scholarship.award', 'scholarship.award',
                               application_id=app.id, student_id=student.id,
                               semester_id=self.terms[0].id, award_amount=10000.0,
                               company_id=self.company.id, award_state='disbursed')
        self._make('edicai.document.category', 'document.category',
                   name='Demo Academic Documents', company_id=self.company.id,
                   category_type='institutional', sequence=10)
        self._make('edicai.notification.template', 'notification.template',
                   name='Demo Attendance Shortage Alert', company_id=self.company.id,
                   trigger_event='attendance_shortage', channel='email',
                   email_subject='Demo: Attendance Shortage Warning',
                   email_body_html='<p>Dear {student_name}, your attendance in '
                                   '{course_name} is below the threshold.</p>',
                   is_active_trigger=True)
        self._make('edicai.notification.template', 'notification.template',
                   name='Demo Fee Payment Reminder', company_id=self.company.id,
                   trigger_event='fee_due', channel='email',
                   email_subject='Demo: Fee Payment Due Reminder',
                   email_body_html='<p>Dear {student_name}, your fee payment of '
                                   '{amount} is due.</p>',
                   is_active_trigger=True)
        if self._has_feature('LIBRARY') and 'edicai.library.book' in self.env:
            publisher = self._make('edicai.library.publisher', 'library.publisher',
                                   name='Demo Press')
            author = self._make('edicai.library.author', 'library.author',
                                name='Demo Author')
            book = self._make('edicai.library.book', 'library.book',
                              title='Demo Textbook', isbn='978-0000000001',
                              publisher_id=publisher.id,
                              author_ids=[(6, 0, [author.id])],
                              book_type='book', total_copies=3, available_copies=3)
            for i in range(3):
                self._make('edicai.library.book.copy', 'library.book.copy',
                           book_id=book.id, accession_number='DEMO-%03d' % (i + 1),
                           condition='good', copy_state='available')
            for student in self.students[:3]:
                self._make('edicai.library.member', 'library.member',
                           student_id=student.id, company_id=self.company.id,
                           member_state='active')
        if self._has_feature('HOSTEL') and 'edicai.hostel.block' in self.env:
            blocks = []
            for bname, bcode, gender, warden in (
                    ('Demo Boys Hostel', 'DEMO-HB', 'male', 'Demo Warden'),
                    ('Demo Girls Hostel', 'DEMO-HG', 'female', 'Demo Warden F')):
                blocks.append(self._make(
                    'edicai.hostel.block', 'hostel.block', name=bname, code=bcode,
                    company_id=self.company.id, campus_id=self.campus.id,
                    gender_type=gender, warden_name=warden,
                    warden_mobile=self._phone(700),
                    total_rooms=10, block_state='active'))
            rooms = []
            for i, block in enumerate(blocks):
                rooms.append(self._make(
                    'edicai.hostel.room', 'hostel.room',
                    room_number='D%d01' % (i + 1), block_id=block.id,
                    company_id=self.company.id, room_type='double',
                    capacity=3, current_occupancy=2,
                    monthly_rent=8000.0, room_state='occupied'))
            boys = [s for s in self.students if s.gender == 'male'][:2]
            girls = [s for s in self.students if s.gender == 'female'][:2]
            for student, room in list(zip(boys, [rooms[0]] * 2)) + \
                    list(zip(girls, [rooms[1]] * 2)):
                self._make('edicai.hostel.allocation', 'hostel.allocation',
                           student_id=student.id, room_id=room.id,
                           academic_year_id=self.year.id, company_id=self.company.id,
                           allocation_date='%d-07-15' % self.y0,
                           expected_checkin='%d-07-15' % self.y0,
                           allocation_state='allocated')
        if self._has_feature('TRANSPORT') and 'edicai.transport.vehicle' in self.env:
            vehicle = self._make(
                'edicai.transport.vehicle', 'transport.vehicle', name='Demo Bus 01',
                registration_number='DEMO-01-0001', vehicle_type='bus',
                seating_capacity=40, driver_name='Demo Driver',
                driver_mobile=self._phone(701), vehicle_state='active',
                company_id=self.company.id)
            route = self._make(
                'edicai.transport.route', 'transport.route', name='Demo Route 01',
                code='DEMO-RT-01', vehicle_id=vehicle.id, total_distance_km=10.0,
                route_state='active', company_id=self.company.id,
                campus_id=self.campus.id, direction='both')
            self._make('edicai.transport.stop', 'transport.stop',
                       route_id=route.id, name='Demo Stop Central',
                       sequence=10, distance_from_campus_km=3.0)
            for student in self.students[:2]:
                self._make('edicai.transport.pass', 'transport.pass',
                           student_id=student.id, route_id=route.id,
                           semester_id=self.terms[0].id, transport_fee=3000.0,
                           pass_state='active', company_id=self.company.id,
                           academic_year_id=self.year.id,
                           valid_from='%d-07-01' % self.y0,
                           valid_until='%d-12-31' % self.y0)
