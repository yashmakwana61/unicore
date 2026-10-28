"""Edicai Attendance — student-side summary fields and actions.

Lives in edicai_attendance (not edicai_student) so the dependency arrow
points the right way: attendance depends on student, never the reverse.
All aggregates are batched with read_group: one query per recordset no
matter how many kanban cards render.
"""
from odoo import _, api, fields, models


class EdicaiStudentAttendanceExt(models.Model):
    _inherit = 'edicai.student'

    attendance_record_ids = fields.One2many(
        comodel_name='edicai.attendance.record',
        inverse_name='student_id',
        string='Attendance Records',
        readonly=True,
    )
    attendance_records_count = fields.Integer(
        string='Sessions Marked',
        compute='_compute_attendance_summary',
        store=True,
    )
    attendance_percentage = fields.Float(
        string='Attendance %',
        compute='_compute_attendance_summary',
        store=True,
        digits=(5, 1),
        help='Present + late count as attended over all marked sessions.',
    )
    has_attendance_shortage = fields.Boolean(
        string='Attendance Shortage',
        compute='_compute_attendance_summary',
        store=True,
    )

    @api.depends('attendance_record_ids', 'attendance_record_ids.status')
    def _compute_attendance_summary(self):
        # Batched: two read_group queries for the whole recordset, so
        # kanban grids never issue per-card queries.
        Record = self.env['edicai.attendance.record']
        totals = {
            g['student_id'][0]: g.get('student_id_count', g.get('__count', 0))
            for g in Record.read_group(
                [('student_id', 'in', self.ids)],
                ['student_id'], ['student_id'])
        }
        attended = {
            g['student_id'][0]: g.get('student_id_count', g.get('__count', 0))
            for g in Record.read_group(
                [('student_id', 'in', self.ids),
                 ('status', 'in', ('present', 'late'))],
                ['student_id'], ['student_id'])
        }
        for record in self:
            total = totals.get(record.id, 0)
            hit = attended.get(record.id, 0)
            record.attendance_records_count = total
            record.attendance_percentage = (
                round(hit / total * 100.0, 1) if total else 0.0)
            record.has_attendance_shortage = bool(
                total) and record.attendance_percentage < 75.0

    def action_open_attendance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attendance Records'),
            'res_model': 'edicai.attendance.record',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
