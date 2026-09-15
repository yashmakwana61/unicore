from datetime import date, timedelta

from odoo import tests
from odoo.exceptions import UserError, ValidationError


@tests.tagged('oacis', 'phase_auto')
class OacisAdmissionAutomationTest(tests.common.TransactionCase):
    """Phases A/B/C: automation engine, entrance-test precision, offer PDF."""

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
            'end_date': '2026-08-31',
            'state': 'active',
            'company_id': cls.company.id,
        })
        cls.seat = cls.env['oacis.admission.cycle.seat'].create({
            'cycle_id': cls.cycle.id,
            'program_id': cls.program.id,
            'total_seats': 10,
            'reserved_seats': 0,
            'company_id': cls.company.id,
        })

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def _create_applicant(self, name, state='shortlisted'):
        return self.env['oacis.admission.applicant'].create({
            'name': name,
            'email': '%s@test.oacis.edu' % name.lower().replace(' ', '.'),
            'mobile': '9000000000',
            'gender': 'male',
            'date_of_birth': '2003-06-15',
            'cycle_id': self.cycle.id,
            'campus_id': self.campus.id,
            'program_id': self.program.id,
            'company_id': self.company.id,
            'state': state,
        })

    def _create_rule(self, name, **kw):
        vals = {'name': name, 'company_id': self.company.id}
        vals.update(kw)
        return self.env['oacis.admission.automation.rule'].create(vals)

    def _rule_notes(self, record, rule):
        return record.message_ids.filtered(
            lambda m: (m.body or '') and rule.name in m.body,
        )

    # ==============================================================
    # PHASE A — RULE CONFIGURATION VALIDATION
    # ==============================================================

    def test_01_state_rule_requires_trigger_state(self):
        with self.assertRaises(ValidationError):
            self._create_rule(
                'Broken State Rule', trigger_type='on_state_change',
            )

    def test_02_active_email_rule_requires_template(self):
        with self.assertRaises(ValidationError):
            self._create_rule(
                'Active Email Rule', trigger_type='on_state_change',
                trigger_state='merit_listed', channel='email',
            )
        # Inactive placeholder rules may be saved without a template.
        rule = self._create_rule(
            'Inactive Placeholder', trigger_type='on_state_change',
            trigger_state='merit_listed', channel='email', active=False,
        )
        self.assertFalse(rule.active)

    # ==============================================================
    # PHASE A — TRIGGER FIRING
    # ==============================================================

    def test_03_state_change_fires_rule_once(self):
        rule = self._create_rule(
            'State Rule', trigger_type='on_state_change',
            trigger_state='merit_listed', channel='in_app',
        )
        applicant = self._create_applicant('Anna')
        applicant.write({'state': 'merit_listed'})
        self.assertEqual(len(self._rule_notes(applicant, rule)), 1,
                         'The rule must fire exactly once per state entry.')

    def test_04_rewriting_same_state_does_not_fire(self):
        rule = self._create_rule(
            'State Rule', trigger_type='on_state_change',
            trigger_state='shortlisted', channel='in_app',
        )
        applicant = self._create_applicant('Bella', state='inquiry')
        applicant.write({'state': 'shortlisted'})
        self.assertEqual(len(self._rule_notes(applicant, rule)), 1)
        applicant.write({'state': 'shortlisted'})
        self.assertEqual(len(self._rule_notes(applicant, rule)), 1,
                         'Writing the same state must not re-fire the rule.')

    def test_05_stage_drag_fires_stage_rule_once(self):
        stage_a = self.env['oacis.admission.stage'].create({
            'name': 'Automation Stage A',
            'state': 'shortlisted',
            'sequence': 10,
            'company_id': self.company.id,
        })
        stage_b = self.env['oacis.admission.stage'].create({
            'name': 'Automation Stage B',
            'state': 'merit_listed',
            'sequence': 20,
            'company_id': self.company.id,
        })
        rule = self._create_rule(
            'Stage Rule', trigger_type='on_stage_change',
            trigger_stage_id=stage_b.id, channel='in_app',
        )
        applicant = self._create_applicant('Cara')
        applicant.write({'stage_id': stage_b.id})
        self.assertEqual(applicant.state, 'merit_listed')
        self.assertEqual(len(self._rule_notes(applicant, rule)), 1,
                         'A kanban stage drag must fire the stage rule once.')

    def test_06_date_based_rule_fires_via_cron(self):
        rule = self._create_rule(
            'Reminder Rule', trigger_type='date_based',
            date_field='entrance_test_date', date_offset_days=0,
            channel='in_app',
        )
        today = date.today()
        applicant = self._create_applicant('Dara')
        test = self.env['oacis.admission.entrance.test'].create({
            'name': 'Physics Entrance',
            'code': 'ENT-PHY',
            'cycle_id': self.cycle.id,
            'test_date': today,
            'start_time': 9.0,
            'end_time': 11.0,
            'venue': 'Hall A',
            'company_id': self.company.id,
        })
        self.env['oacis.admission.entrance.test.line'].create({
            'test_id': test.id,
            'applicant_id': applicant.id,
        })
        self.assertEqual(applicant.entrance_test_date, today)

        fired = self.env['oacis.admission.automation.engine'].\
            _run_date_based_rules()
        self.assertGreaterEqual(fired, 1)
        self.assertEqual(len(self._rule_notes(applicant, rule)), 1)

    # ==============================================================
    # PHASE B — ENTRANCE TEST PRECISION
    # ==============================================================

    def _create_test(self, name, test_date, venue='Hall B',
                     start=9.0, end=11.0):
        return self.env['oacis.admission.entrance.test'].create({
            'name': name,
            'code': 'ENT-%s' % name.replace(' ', '').upper()[:8],
            'cycle_id': self.cycle.id,
            'test_date': test_date,
            'start_time': start,
            'end_time': end,
            'venue': venue,
            'company_id': self.company.id,
        })

    def test_07_publish_blocks_when_marks_missing(self):
        test = self._create_test('Marks Test', self.cycle.start_date)
        applicant = self._create_applicant('Eara', state='entrance_scheduled')
        self.env['oacis.admission.entrance.test.line'].create({
            'test_id': test.id,
            'applicant_id': applicant.id,
            'attended': True,
        })
        test.action_schedule()
        test.action_start()
        test.action_complete()
        with self.assertRaises(UserError):
            test.action_publish_results()

    def test_08_publish_with_marks_moves_to_merit(self):
        test = self._create_test('Marks Test 2', self.cycle.start_date)
        applicant = self._create_applicant('Fara', state='entrance_scheduled')
        line = self.env['oacis.admission.entrance.test.line'].create({
            'test_id': test.id,
            'applicant_id': applicant.id,
            'attended': True,
        })
        line.write({'marks_obtained': 72.5})
        self.assertTrue(line.marks_entered)
        test.action_schedule()
        test.action_start()
        test.action_complete()
        test.action_publish_results()
        self.assertEqual(test.state, 'result_published')
        self.assertEqual(applicant.entrance_score, 72.5)
        self.assertEqual(applicant.state, 'merit_listed')

    def test_09_publish_rejects_absent_applicant(self):
        test = self._create_test('Marks Test 3', self.cycle.start_date)
        applicant = self._create_applicant('Gara', state='entrance_scheduled')
        self.env['oacis.admission.entrance.test.line'].create({
            'test_id': test.id,
            'applicant_id': applicant.id,
            'attended': False,
        })
        test.action_schedule()
        test.action_start()
        test.action_complete()
        test.action_publish_results()
        self.assertEqual(applicant.state, 'rejected')
        self.assertTrue(applicant.rejection_reason)

    def test_10_venue_overlap_constraint(self):
        self._create_test('Overlap A', self.cycle.start_date,
                          venue='Hall C', start=9.0, end=11.0)
        with self.assertRaises(ValidationError):
            self._create_test('Overlap B', self.cycle.start_date,
                              venue='Hall C', start=10.0, end=12.0)
        # Back-to-back sessions do not overlap.
        self._create_test('Overlap C', self.cycle.start_date,
                          venue='Hall C', start=11.0, end=13.0)

    def test_11_bulk_write_sets_marks_entered(self):
        test = self._create_test('Bulk Marks', self.cycle.start_date)
        applicant = self._create_applicant('Hara', state='entrance_scheduled')
        line = self.env['oacis.admission.entrance.test.line'].create({
            'test_id': test.id,
            'applicant_id': applicant.id,
            'attended': True,
        })
        self.assertFalse(line.marks_entered)
        line.write({'marks_obtained': 60.0})
        self.assertTrue(line.marks_entered)

    # ==============================================================
    # PHASE C — OFFER LETTER PDF SEND
    # ==============================================================

    def test_12_send_offer_letter_creates_pdf_attachment(self):
        applicant = self._create_applicant('Iara', state='merit_listed')
        applicant.action_send_offer()
        self.assertEqual(applicant.state, 'offer_sent')
        offer = applicant.offer_letter_ids[0]
        self.assertEqual(offer.state, 'draft')

        offer.action_send()
        self.assertEqual(offer.state, 'sent')
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'oacis.admission.offer.letter'),
            ('res_id', '=', offer.id),
            ('mimetype', '=', 'application/pdf'),
        ])
        self.assertEqual(len(attachment), 1,
                         'Sending an offer letter must attach its rendered PDF.')
        self.assertTrue(attachment.datas,
                        'The PDF attachment must hold binary content.')

    def test_13_only_draft_letters_can_be_sent(self):
        applicant = self._create_applicant('Jara', state='merit_listed')
        applicant.action_send_offer()
        offer = applicant.offer_letter_ids[0]
        offer.action_send()
        with self.assertRaises(UserError):
            offer.action_send()