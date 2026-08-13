"""
Oacis Exam Seating Model
Assigns an eligible, approved hall ticket holder
to a specific room and seat number for an exam.
Generated automatically by the exam schedule's
action_generate_seating() method. Can also be
created or edited manually by registrar for
special accommodation requests.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OacisExamSeating(models.Model):
    _name = 'oacis.exam.seating'
    _description = 'Exam Seating Assignment'
    _rec_name = 'display_name'
    _inherit = ['oacis.mixin']

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['exam_schedule_id.display_name', 'student_id.display_name',
                 'seat_label'],
    )

    @api.depends('exam_schedule_id.display_name', 'student_id.display_name',
                 'seat_label')
    def _compute_display_name(self):
        for rec in self:
            schedule_name = (
                rec.exam_schedule_id.display_name
                if rec.exam_schedule_id else ''
            )
            student_name = (
                rec.student_id.display_name if rec.student_id else ''
            )
            rec.display_name = '%s - %s - Seat %s' % (
                schedule_name, student_name, rec.seat_label or '',
            )
    _order = 'exam_schedule_id, room_id, seat_number'
    _check_company_auto = True

    exam_schedule_id = fields.Many2one(
        comodel_name='oacis.exam.schedule',
        string='Exam',
        required=True,
        ondelete='cascade',
        index=True,
    )

    hall_ticket_id = fields.Many2one(
        comodel_name='oacis.exam.hall.ticket',
        string='Hall Ticket',
        required=True,
        ondelete='cascade',
        index=True,
    )

    student_id = fields.Many2one(
        comodel_name='oacis.student',
        string='Student',
        related='hall_ticket_id.student_id',
        store=True,
        readonly=True,
        index=True,
    )

    course_id = fields.Many2one(
        comodel_name='oacis.course',
        string='Course',
        related='exam_schedule_id.course_id',
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='exam_schedule_id.company_id',
        store=True,
        readonly=True,
    )

    exam_date = fields.Date(
        string='Exam Date',
        related='exam_schedule_id.exam_date',
        store=True,
        readonly=True,
    )

    room_id = fields.Many2one(
        comodel_name='oacis.room',
        string='Room',
        required=True,
        ondelete='restrict',
        domain="[('campus_id','=',exam_schedule_id.campus_id.id)]",
    )

    seat_number = fields.Integer(
        string='Seat Number',
        required=True,
    )

    seat_label = fields.Char(
        string='Seat Label',
        compute='_compute_seat_label',
        store=True,
        depends=['room_id', 'seat_number'],
    )

    special_requirements = fields.Text(
        string='Special Requirements',
        help='e.g. wheelchair access, extra time, separate room for special needs',
    )

    _unique_seat_room_exam = models.Constraint(
        'UNIQUE(exam_schedule_id, room_id, seat_number)',
        'Seat number is already assigned in this room for this exam.',
    )

    _unique_student_exam_seating = models.Constraint(
        'UNIQUE(exam_schedule_id, student_id)',
        'Student already has a seat assignment for this exam.',
    )

    @api.depends('room_id', 'seat_number')
    def _compute_seat_label(self):
        for rec in self:
            if rec.room_id and rec.seat_number:
                rec.seat_label = '%s-%d' % (rec.room_id.code, rec.seat_number)
            else:
                rec.seat_label = ''

    @api.constrains('seat_number')
    def _check_seat_number(self):
        for rec in self:
            if rec.seat_number < 1:
                raise ValidationError(_('Seat number must be at least 1.'))

    @api.constrains('room_id', 'seat_number', 'exam_schedule_id')
    def _check_seat_within_capacity(self):
        for rec in self:
            room_capacity = rec.room_id.exam_capacity or rec.room_id.capacity
            if rec.seat_number > room_capacity:
                raise ValidationError(
                    _('Seat number %d exceeds room "%s" exam capacity of %d.')
                    % (rec.seat_number, rec.room_id.display_name, room_capacity),
                )

    def write(self, vals):
        result = super().write(vals)
        for rec in self:
            if rec.hall_ticket_id:
                rec.hall_ticket_id.seating_id = rec.id
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.hall_ticket_id:
                rec.hall_ticket_id.seating_id = rec.id
        return records
