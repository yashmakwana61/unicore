
import logging

from odoo import tests
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


@tests.tagged('oacis', 'phase1')
class OacisAdmissionMeritScoringTest(tests.common.TransactionCase):
    """Phase 1: smart scoring (configurable weights), merit ranks, bulk merit
    list generation, seat enforcement and per-company sequences."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        faculty = cls.env['oacis.faculty'].create({
            'name': 'Faculty of Science',
            'code': 'FS',
            'company_id': cls.company.id,
        })
        department = cls.env['oacis.department'].create({
            'name': 'Physics',
            'code': 'PHY',
            'faculty_id': faculty.id,
        })
        cls.program = cls.env['oacis.program'].create({
            'name': 'B.Sc Physics',
            'code': 'BSC-PHY',
            'degree_title': 'Bachelor of Science',
            'program_type': 'undergraduate',
            'credit_system': 'credit_hours',
            'total_credits': 120,
            'duration_years': 3,
            'department_id': department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Science Campus',
            'code': 'SC',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': '2025-2026',
            'code': '2025',
            'date_start': '2025-06-01',
            'date_end': '2026-05-31',
        })
        cls.cycle = cls.env['oacis.admission.cycle'].create({
            'name': 'Main Intake 2025-26',
            'code': 'MAIN-2526',
            'campus_id': cls.campus.id,
            'academic_year_id': cls.academic_year.id,
            'start_date': '2025-03-01',
            'end_date': '2025-08-31',
            'state': 'active',
            'company_id': cls.company.id,
        })
        cls.seat = cls.env['oacis.admission.cycle.seat'].create({
            'cycle_id': cls.cycle.id,
            'program_id': cls.program.id,
            'total_seats': 2,
            'reserved_seats': 0,
            'company_id': cls.company.id,
        })

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def _create_applicant(self, name, aggregate, entrance, interview, state='shortlisted'):
        return self.env['oacis.admission.applicant'].create({
            'name': name,
            'email': '%s@test.oacis.edu' % name.lower().replace(' ', '.'),
            'mobile': '9000000000',
            'gender': 'male',
            'date_of_birth': '2003-06-15',
            'cycle_id': self.cycle.id,
            'campus_id': self.campus.id,
            'program_id': self.program.id,
            'aggregate_percentage': aggregate,
            'entrance_score': entrance,
            'interview_score': interview,
            'company_id': self.company.id,
            'state': state,
        })

    # ==============================================================
    # TEST 01: COMPOSITE SCORE USES CYCLE WEIGHTS
    # ==============================================================

    def test_01_composite_score_uses_cycle_weights(self):
        self.cycle.write({
            'weight_aggregate': 60.0,
            'weight_entrance': 30.0,
            'weight_interview': 10.0,
        })
        applicant = self._create_applicant('Anna', 80.0, 70.0, 60.0)
        expected = (80.0 * 0.6) + (70.0 * 0.3) + (60.0 * 0.1)
        self.assertAlmostEqual(
            applicant.composite_score, expected, places=2,
            msg='Composite score must honour the cycle weights (60/30/10).',
        )

    # ==============================================================
    # TEST 02: DEFAULT WEIGHTS ARE BACKWARD COMPATIBLE (40/40/20)
    # ==============================================================

    def test_02_default_weights_backward_compatible(self):
        applicant = self._create_applicant('Bella', 80.0, 70.0, 60.0)
        expected = (80.0 * 0.4) + (70.0 * 0.4) + (60.0 * 0.2)
        self.assertAlmostEqual(
            applicant.composite_score, expected, places=2,
            msg='Default weights (40/40/20) must preserve the original formula.',
        )

    # ==============================================================
    # TEST 03: WEIGHTS MUST SUM TO 100
    # ==============================================================

    def test_03_weights_must_sum_to_100(self):
        with self.assertRaises(ValidationError):
            self.env['oacis.admission.cycle'].create({
                'name': 'Broken Weights',
                'code': 'BW-2526',
                'campus_id': self.campus.id,
                'academic_year_id': self.academic_year.id,
                'start_date': '2025-03-01',
                'end_date': '2025-08-31',
                'state': 'draft',
                'company_id': self.company.id,
                'weight_aggregate': 50.0,
                'weight_entrance': 30.0,
                'weight_interview': 10.0,  # sum = 90
            })

    # ==============================================================
    # TEST 04: MERIT RANK ORDERING
    # ==============================================================

    def test_04_merit_rank_ordering(self):
        low = self._create_applicant('Cara', 60.0, 60.0, 60.0)
        high = self._create_applicant('Dara', 90.0, 90.0, 90.0)
        mid = self._create_applicant('Eara', 75.0, 75.0, 75.0)

        self.assertEqual(high.rank, 1, 'Highest composite score must be rank 1.')
        self.assertEqual(mid.rank, 2, 'Second-highest score must be rank 2.')
        self.assertEqual(low.rank, 3, 'Lowest score must be rank 3.')

        # Recompute after scoring change -> rank must follow.
        low.write({
            'aggregate_percentage': 100.0,
            'entrance_score': 100.0,
            'interview_score': 100.0,
        })
        self.assertEqual(
            low.rank, 1,
            'Rank must update when the composite score changes.',
        )

    # ==============================================================
    # TEST 05: BULK MERIT LIST GENERATION (CAPS AT SEATS)
    # ==============================================================

    def test_05_generate_merit_list_caps_at_seats(self):
        self._create_applicant('Fara', 88.0, 88.0, 88.0)
        self._create_applicant('Gara', 72.0, 72.0, 72.0)
        self._create_applicant('Hara', 55.0, 55.0, 55.0)

        self.cycle.action_generate_merit_list()

        merit = self.env['oacis.admission.applicant'].search([
            ('cycle_id', '=', self.cycle.id),
            ('state', '=', 'merit_listed'),
        ])
        waitlisted = self.env['oacis.admission.applicant'].search([
            ('cycle_id', '=', self.cycle.id),
            ('state', '=', 'waitlisted'),
        ])
        self.assertEqual(
            len(merit), 2,
            'Only as many applicants as available seats must be merit-listed.',
        )
        self.assertEqual(
            len(waitlisted), 1,
            'The remaining eligible applicant must be waitlisted.',
        )
        self.assertEqual(
            max(merit.mapped('composite_score')),
            max(self.env['oacis.admission.applicant'].search([
                ('cycle_id', '=', self.cycle.id),
            ]).mapped('composite_score')),
            'Top-scoring applicant must be merit-listed.',
        )

    # ==============================================================
    # TEST 06: SEAT ENFORCEMENT ON OFFER
    # ==============================================================

    def test_06_seat_enforcement_on_offer(self):
        self.seat.write({'total_seats': 1, 'reserved_seats': 0})
        first = self._create_applicant('Iara', 90.0, 90.0, 90.0, state='merit_listed')
        second = self._create_applicant('Jara', 80.0, 80.0, 80.0, state='merit_listed')

        first.action_send_offer()  # consumes the only seat
        self.assertEqual(first.state, 'offer_sent')
        self.assertLessEqual(
            self.seat.available_seats, 0,
            'Available seats must reflect the committed applicant.',
        )

        with self.assertRaises(UserError):
            second.action_send_offer()

        # Releasing the seat (reject -> waitlist) must allow the offer again.
        first.offer_letter_ids[0].action_send()
        first.offer_letter_ids[0].action_reject()
        self.assertEqual(first.state, 'waitlisted')
        second.action_send_offer()
        self.assertEqual(second.state, 'offer_sent')

    # ==============================================================
    # TEST 07: PER-COMPANY SEQUENCES ARE INDEPENDENT
    # ==============================================================

    def test_07_per_company_sequences_are_independent(self):
        second_company = self.env['res.company'].create({
            'name': 'Second Institution',
            'currency_id': self.env.ref('base.USD').id,
        })

        Applicant = self.env['oacis.admission.applicant']

        def _create(company, name, mobile):
            return Applicant.with_company(company).create({
                'name': name,
                'email': '%s@test.oacis.edu' % name.lower(),
                'mobile': mobile,
                'gender': 'female',
                'date_of_birth': '2003-06-15',
                'cycle_id': self.cycle.id,
                'campus_id': self.campus.id,
                'program_id': self.program.id,
                'company_id': company.id,
            })

        def sequence_suffix(application_number):
            return int(application_number.rsplit('/', 1)[-1])

        # Burn several numbers in company A's series first.
        for i in range(3):
            _create(self.company, 'Burn%d' % i, '90000000%02d' % i)

        second_1 = _create(second_company, 'Beta', '9000000002')
        second_2 = _create(second_company, 'Gamma', '9000000003')

        # Company B is a fresh institution, so its series must start at 1
        # independently of company A having already consumed numbers.
        for app in (second_1, second_2):
            self.assertTrue(app.application_number.startswith('APP/'))
        self.assertEqual(sequence_suffix(second_1.application_number), 1,
                         'A fresh per-company sequence must restart at 1.')
        self.assertEqual(sequence_suffix(second_2.application_number), 2,
                         'Each company counts its own series (1, 2, 3...).')

    # ==============================================================
    # TEST 08: OFFER REJECT RELEASES THE SEAT
    # ==============================================================

    def test_08_offer_reject_moves_applicant_to_waitlist(self):
        self.seat.write({'total_seats': 2, 'reserved_seats': 0})
        applicant = self._create_applicant('Kara', 85.0, 85.0, 85.0, state='merit_listed')
        applicant.action_send_offer()
        self.assertEqual(applicant.state, 'offer_sent')

        offer = applicant.offer_letter_ids[0]
        offer.action_send()
        offer.action_reject()

        self.assertEqual(offer.state, 'rejected')
        self.assertEqual(
            applicant.state, 'waitlisted',
            'Declining the only open offer must return the applicant to the '
            'waitlist and free the seat.',
        )
        self.assertGreaterEqual(
            self.seat.available_seats, 1,
            'A declined offer must release the seat.',
        )
