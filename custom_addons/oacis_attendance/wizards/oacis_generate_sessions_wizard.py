"""
UniCore Generate Sessions Wizard
Generates unicore.attendance.session records for
a selected course offering (or all offerings in a
semester) by expanding the weekly timetable entries
across all teaching dates in the semester date range,
automatically excluding holiday dates.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UniCoreGenerateSessionsWizard(models.TransientModel):
    _name = 'unicore.generate.sessions.wizard'
    _description = 'Generate Attendance Sessions Wizard'

    generation_mode = fields.Selection(
        string='Generate For',
        required=True,
        default='offering',
        selection=[
            ('offering', 'Specific Course Offering'),
            ('semester', 'All Offerings in Semester'),
        ],
    )

    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        domain="[('offering_state', 'in', ['open', 'ongoing'])]",
        help='Required when mode is Specific Offering',
    )

    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        help='Required when mode is All Offerings',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        default=lambda self: self.env.company,
        required=True,
    )

    skip_existing = fields.Boolean(
        string='Skip Existing Sessions',
        default=True,
        help='If True skip dates where a session already exists (safe for re-running). If False raise error on duplicate.',
    )

    preview_count = fields.Integer(
        string='Sessions to Generate (Preview)',
        compute='_compute_preview_count',
        store=False,
    )

    def _get_holiday_dates(self, semester_id, campus_id=None):
        """
        Returns a set of dates that are holidays for
        the given semester, optionally filtered by campus.
        Only includes holidays where affects_attendance=True.
        """
        Holiday = self.env['unicore.holiday']
        domain = [
            ('academic_year_id', '=', semester_id.academic_year_id.id),
            ('affects_attendance', '=', True),
        ]
        holidays = Holiday.search(domain)
        holiday_dates = set()
        for holiday in holidays:
            if holiday.date_start and holiday.date_end:
                if campus_id and holiday.campus_ids and campus_id not in holiday.campus_ids:
                    continue
                current = holiday.date_start
                while current <= holiday.date_end:
                    holiday_dates.add(current)
                    current += timedelta(days=1)
        return holiday_dates

    def _get_teaching_dates_for_entry(self, entry, holiday_dates):
        """
        Returns a list of dates on which a specific
        timetable entry should have a session.
        Expands the entry's effective_date_start to
        effective_date_end, keeping only dates matching
        the entry's day_of_week, excluding holidays.
        """
        if not entry.effective_date_start or not entry.effective_date_end:
            return []
        target_weekday = int(entry.day_of_week)
        dates = []
        current = entry.effective_date_start
        while current <= entry.effective_date_end:
            if current.weekday() == target_weekday and current not in holiday_dates:
                dates.append(current)
            current += timedelta(days=1)
        return dates

    def _generate_for_offering(self, offering, skip_existing=True):
        """
        Generates sessions for all confirmed timetable
        entries of a given course offering.
        Returns the count of newly created sessions.
        """
        Session = self.env['unicore.attendance.session']
        TimetableEntry = self.env['unicore.timetable.entry']

        entries = TimetableEntry.search([
            ('course_offering_id', '=', offering.id),
            ('entry_state', '=', 'confirmed'),
        ])
        if not entries:
            _logger.warning(
                'No confirmed timetable entries found for offering %s.',
                offering.offering_code,
            )
            return 0

        holiday_dates = self._get_holiday_dates(
            offering.semester_id,
            offering.campus_id.id,
        )

        created_count = 0
        for entry in entries:
            teaching_dates = self._get_teaching_dates_for_entry(entry, holiday_dates)
            for teaching_date in teaching_dates:
                existing = Session.search([
                    ('timetable_entry_id', '=', entry.id),
                    ('session_date', '=', teaching_date),
                ], limit=1)
                if existing:
                    if skip_existing:
                        continue
                    raise UserError(
                        _('Session already exists for entry "%s" on %s. Enable Skip Existing to ignore duplicates.')
                        % (entry.display_name, teaching_date),
                    )
                Session.create({
                    'timetable_entry_id': entry.id,
                    'session_date': teaching_date,
                    'session_state': 'scheduled',
                })
                created_count += 1
        return created_count

    def _compute_preview_count(self):
        for rec in self:
            try:
                if rec.generation_mode == 'offering' and rec.course_offering_id:
                    Session = self.env['unicore.attendance.session']
                    TimetableEntry = self.env['unicore.timetable.entry']
                    entries = TimetableEntry.search([
                        ('course_offering_id', '=', rec.course_offering_id.id),
                        ('entry_state', '=', 'confirmed'),
                    ])
                    holiday_dates = rec._get_holiday_dates(
                        rec.course_offering_id.semester_id,
                    )
                    count = 0
                    for entry in entries:
                        dates = rec._get_teaching_dates_for_entry(entry, holiday_dates)
                        count += len(dates)
                    rec.preview_count = count
                else:
                    rec.preview_count = 0
            except Exception:
                rec.preview_count = 0

    def action_generate(self):
        self.ensure_one()
        total_created = 0

        if self.generation_mode == 'offering':
            if not self.course_offering_id:
                raise UserError(
                    _('Please select a course offering.'),
                )
            total_created = self._generate_for_offering(
                self.course_offering_id,
                self.skip_existing,
            )
        elif self.generation_mode == 'semester':
            if not self.semester_id:
                raise UserError(
                    _('Please select a semester.'),
                )
            Offering = self.env['unicore.course.offering']
            offerings = Offering.search([
                ('semester_id', '=', self.semester_id.id),
                ('company_id', '=', self.company_id.id),
                ('offering_state', 'in', ['open', 'ongoing']),
            ])
            if not offerings:
                raise UserError(
                    _('No open or ongoing course offerings found for the selected semester.'),
                )
            for offering in offerings:
                total_created += self._generate_for_offering(offering, self.skip_existing)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sessions Generated'),
                'message': _('%d attendance sessions successfully generated.') % total_created,
                'type': 'success',
                'sticky': False,
            },
        }

    @api.onchange('generation_mode')
    def _onchange_generation_mode(self):
        if self.generation_mode == 'semester':
            self.course_offering_id = False
        else:
            self.semester_id = False
