import logging
from datetime import timedelta

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class OacisGenerateWeeksWizard(models.TransientModel):
    """Wizard to generate academic weeks for a semester."""

    _name = 'oacis.generate.weeks.wizard'
    _description = 'Generate Academic Weeks for Semester'

    semester_id = fields.Many2one(
        comodel_name='oacis.semester',
        string='Semester',
        required=True,
        ondelete='cascade',
    )
    week_start_day = fields.Selection(
        selection=[
            ('0', 'Monday'),
            ('6', 'Sunday'),
            ('5', 'Saturday'),
        ],
        string='Week Starts On',
        default='0',
        required=True,
    )
    default_week_type = fields.Selection(
        selection=[
            ('teaching', 'Teaching Week'),
            ('revision', 'Revision Week'),
            ('exam', 'Examination Week'),
            ('holiday', 'Holiday Week'),
            ('orientation', 'Orientation Week'),
            ('break', 'Semester Break'),
        ],
        string='Default Week Type',
        default='teaching',
        required=True,
    )
    preview_line_ids = fields.One2many(
        comodel_name='oacis.generate.weeks.line',
        inverse_name='wizard_id',
        string='Preview',
    )

    def action_preview(self):
        self.ensure_one()
        self.preview_line_ids.unlink()
        sem = self.semester_id
        lines = []
        start = sem.date_start
        end = sem.date_end
        week_start_day_int = int(self.week_start_day)

        current = start
        week_num = 1
        while current <= end:
            week_start = current
            if week_start.weekday() != week_start_day_int:
                days_ahead = (week_start_day_int - week_start.weekday()) % 7
                week_start = week_start + timedelta(days=days_ahead)
                if week_start > end:
                    break

            week_end = week_start + timedelta(days=6)
            if week_end > end:
                week_end = end

            week_name = _('Week %s') % week_num
            lines.append({
                'week_number': week_num,
                'name': week_name,
                'date_start': week_start,
                'date_end': week_end,
                'week_type': self.default_week_type,
            })
            current = week_end + timedelta(days=1)
            week_num += 1

        Line = self.env['oacis.generate.weeks.line']
        for line_vals in lines:
            Line.create({
                'wizard_id': self.id,
                'week_number': line_vals['week_number'],
                'name': line_vals['name'],
                'date_start': line_vals['date_start'],
                'date_end': line_vals['date_end'],
                'week_type': line_vals['week_type'],
            })

        return {'type': 'ir.actions.do_nothing'}

    def action_generate(self):
        self.ensure_one()
        sem = self.semester_id
        existing = self.env['oacis.academic.week'].search([
            ('semester_id', '=', sem.id),
        ])
        existing.unlink()

        Week = self.env['oacis.academic.week']
        for line in self.preview_line_ids:
            Week.create({
                'semester_id': sem.id,
                'week_number': line.week_number,
                'name': line.name,
                'date_start': line.date_start,
                'date_end': line.date_end,
                'week_type': line.week_type,
            })

        _logger.info(
            'Generated %d academic weeks for semester %s (%s).',
            len(self.preview_line_ids), sem.name, sem.code,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Academic Weeks'),
            'res_model': 'oacis.academic.week',
            'view_mode': 'list,form',
            'domain': [('semester_id', '=', sem.id)],
        }


class OacisGenerateWeeksLine(models.TransientModel):
    """Preview line for week generation wizard."""

    _name = 'oacis.generate.weeks.line'
    _description = 'Week Generation Preview Line'

    wizard_id = fields.Many2one(
        comodel_name='oacis.generate.weeks.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    week_number = fields.Integer(
        string='Week Number',
        required=True,
    )
    name = fields.Char(
        string='Week Name',
        required=True,
    )
    date_start = fields.Date(
        string='Start Date',
        required=True,
    )
    date_end = fields.Date(
        string='End Date',
        required=True,
    )
    week_type = fields.Selection(
        selection=[
            ('teaching', 'Teaching Week'),
            ('revision', 'Revision Week'),
            ('exam', 'Examination Week'),
            ('holiday', 'Holiday Week'),
            ('orientation', 'Orientation Week'),
            ('break', 'Semester Break'),
        ],
        string='Week Type',
        required=True,
    )
