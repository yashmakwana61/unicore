"""
OACIS Notification & Automation Jobs.

Daily/weekly housekeeping that used to be missing entirely:

* Fee dunning ladder: flips past-due invoices to ``overdue``
  and dispatches fee_due / fee_overdue notifications.
* Attendance shortage alerts (activates the previously
  dead ``send_attendance_shortage_alerts``).
* Exam reminders N days before published exams.
* Library reservation expiry.
* Admission offer expiry.
* Pre-computation of semester results once a semester has
  ended (drafts only; publishing stays a human decision).

All methods are safe to run multiple times per day and are
wired to ir.cron records in data/oacis_notify_automation_cron.xml.
"""

import logging
from datetime import date, timedelta

from odoo import api, models

_logger = logging.getLogger(__name__)


class OacisNotificationAutomation(models.AbstractModel):
    _name = 'oacis.notification.automation'
    _description = 'Notification Automation Jobs'

    def _companies(self):
        return self.env['res.company'].search([])

    def _engine(self):
        return self.env['oacis.notification.engine']

    # ===================================================
    # FEES: DUNNING LADDER
    # ===================================================

    @api.model
    def cron_fee_dunning(self):
        """
        1. Flip sent/partial invoices past their due date to
           overdue (previously only happened as a side effect
           of payment writes).
        2. Send fee_overdue alerts for everything currently
           overdue.
        3. Send fee_due reminders for invoices due soon
           (activates send_batch_fee_reminders()).
        """
        today = date.today()
        Invoice = self.env['oacis.fee.invoice']

        stale = Invoice.search([
            ('invoice_state', 'in', ['sent', 'partial']),
            ('due_date', '<', today),
            ('amount_outstanding', '>', 0),
        ])
        if stale:
            stale.write({'invoice_state': 'overdue'})
            _logger.info(
                'Fee dunning: flipped %d invoices to overdue.',
                len(stale),
            )

        engine = self._engine()
        overdue = Invoice.search([
            ('invoice_state', '=', 'overdue'),
            ('amount_outstanding', '>', 0),
        ])
        notified = 0
        for inv in overdue:
            ok = engine._safe_emit(
                inv.student_id,
                'fee_overdue',
                {
                    'amount': str(inv.amount_outstanding),
                    'invoice_number': inv.invoice_number,
                    'due_date': str(inv.due_date),
                },
                include_guardians=True,
            )
            notified += 1 if ok else 0

        reminded = 0
        for company in self._companies():
            try:
                engine.send_batch_fee_reminders(company.id)
                reminded += 1
            except Exception as e:
                _logger.warning(
                    'Fee due reminders failed for company '
                    '%s: %s', company.id, str(e),
                )
        _logger.info(
            'Fee dunning done: %d overdue alerts, %d reminder '
            'runs.', notified, reminded,
        )

    # ===================================================
    # ATTENDANCE SHORTAGE
    # ===================================================

    @api.model
    def cron_attendance_shortage(self):
        """Dispatch attendance shortage alerts per company."""
        engine = self._engine()
        for company in self._companies():
            try:
                engine.send_attendance_shortage_alerts(
                    company.id,
                )
            except Exception as e:
                _logger.warning(
                    'Attendance shortage alerts failed for '
                    'company %s: %s', company.id, str(e),
                )

    # ===================================================
    # EXAM REMINDERS
    # ===================================================

    @api.model
    def cron_exam_reminders(self, days_before=7):
        """
        Remind enrolled students about exams happening in
        exactly ``days_before`` days (default one week).
        """
        engine = self._engine()
        target = date.today() + timedelta(days=days_before)
        Exam = self.env['oacis.exam.schedule']
        exams = Exam.search([
            ('exam_date', '=', target),
            ('exam_state', 'in', [
                'published',
                'hall_tickets_generated',
                'seating_generated',
            ]),
        ])
        Enrollment = self.env['oacis.enrollment']
        exam_type_labels = dict(Exam._fields[
            'exam_type'
        ]._description_selection(self.env))
        count = 0
        for exam in exams:
            students = Enrollment.search([
                ('course_offering_id', '=',
                 exam.course_offering_id.id),
                ('enrollment_state', 'in',
                 ['registered', 'completed']),
            ]).mapped('student_id')
            variables_base = {
                'exam_name': exam_type_labels.get(
                    exam.exam_type, exam.exam_type,
                ),
                'course_name': (
                    exam.course_id.display_name
                    if exam.course_id else ''
                ),
                'exam_date': str(exam.exam_date),
            }
            for student in students:
                if engine._safe_emit(
                    student, 'exam_reminder',
                    dict(variables_base),
                ):
                    count += 1
        _logger.info(
            'Exam reminders sent to %d students for %d '
            'exams on %s.', count, len(exams), target,
        )

    # ===================================================
    # LIBRARY HOUSEKEEPING
    # ===================================================

    @api.model
    def cron_library_housekeeping(self):
        """Expire stale library reservations."""
        today = date.today()
        Reservation = self.env[
            'oacis.library.reservation'
        ].sudo()
        stale = Reservation.search([
            ('reservation_state', 'in', ['active', 'ready']),
            ('expiry_date', '<', today),
        ])
        if stale:
            stale.write({'reservation_state': 'expired'})
            _logger.info(
                'Library: expired %d reservations.', len(stale),
            )

    # ===================================================
    # ADMISSION OFFER EXPIRY
    # ===================================================

    @api.model
    def cron_admission_offer_expiry(self):
        """Expire unanswered admission offers past validity."""
        today = date.today()
        OfferLetter = self.env[
            'oacis.admission.offer.letter'
        ].sudo()
        stale = OfferLetter.search([
            ('state', '=', 'sent'),
            ('response_date', '=', False),
            '|',
            ('valid_until', '<', today),
            ('valid_until', '=', False),
        ])
        # Offers without any validity window are left alone;
        # only strictly-expired ones flip automatically.
        stale = stale.filtered(
            lambda o: o.valid_until and o.valid_until < today
        )
        if stale:
            stale.write({'state': 'expired'})
            for offer in stale:
                offer.message_post(
                    body='Offer expired automatically '
                         '(validity elapsed without response).',
                )
            _logger.info(
                'Admissions: expired %d offers.', len(stale),
            )

    # ===================================================
    # SEMESTER RESULT PRE-COMPUTATION
    # ===================================================

    @api.model
    def cron_generate_semester_results(self, grace_days=2):
        """
        Pre-compute semester result drafts for semesters that
        ended more than ``grace_days`` days ago and already
        have published/locked grade entries. Publishing
        remains manual (action_publish_result).
        """
        today = date.today()
        cutoff = today - timedelta(days=grace_days)
        Semester = self.env['oacis.semester']
        GradeEntry = self.env['oacis.grade.entry']
        Result = self.env['oacis.semester.result']

        semesters = Semester.search([
            ('date_end', '<', cutoff),
        ])
        processed = 0
        for semester in semesters:
            company_id = semester.company_id.id
            entry_count = GradeEntry.search_count([
                ('semester_id', '=', semester.id),
                ('company_id', '=', company_id),
                ('entry_state', 'in', ['published', 'locked']),
            ])
            if not entry_count:
                continue
            try:
                Result.generate_results_for_semester(
                    semester.id, company_id,
                )
                processed += 1
            except Exception as e:
                _logger.warning(
                    'Result generation failed for semester '
                    '%s: %s', semester.id, str(e),
                )
        if processed:
            _logger.info(
                'Semester results generated for %d semesters.',
                processed,
            )
