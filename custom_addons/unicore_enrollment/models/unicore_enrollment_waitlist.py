"""
UniCore Enrollment Waitlist Model
Queue entry created automatically when a student
attempts to enroll in a full course offering.
Registrar staff manually promote waitlisted students
to confirmed enrollments when seats become available
— promotion is never fully automatic, to preserve
student consent and registrar oversight.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class UniCoreEnrollmentWaitlist(models.Model):
    _name = 'unicore.enrollment.waitlist'
    _description = 'Enrollment Waitlist Entry'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'course_offering_id, position'
    _check_company_auto = True

    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )

    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='course_offering_id.company_id',
        store=True,
        readonly=True,
    )

    position = fields.Integer(
        string='Queue Position',
        required=True,
        default=1,
        tracking=True,
    )

    waitlist_date = fields.Datetime(
        string='Waitlisted On',
        default=fields.Datetime.now,
        readonly=True,
    )

    waitlist_state = fields.Selection(
        string='Status',
        required=True,
        default='waiting',
        tracking=True,
        selection=[
            ('waiting', 'Waiting'),
            ('promoted', 'Promoted to Enrollment'),
            ('expired', 'Offer Expired'),
            ('declined', 'Declined by Student'),
        ],
    )

    promoted_enrollment_id = fields.Many2one(
        comodel_name='unicore.enrollment',
        string='Resulting Enrollment',
        readonly=True,
        copy=False,
    )

    _sql_constraints = [
        (
            'unique_student_offering_waitlist',
            'UNIQUE(student_id, course_offering_id)',
            'This student is already on the waitlist '
            'for this course offering.',
        ),
    ]

    def action_promote_to_enrollment(self):
        """
        Registrar-initiated promotion: creates an actual
        unicore.enrollment record using the standard create()
        validation chain (so prerequisites and conflicts are
        STILL checked at promotion time).
        """
        self.ensure_one()
        if self.waitlist_state != 'waiting':
            raise UserError(
                _('Only entries with status "Waiting" can be promoted.')
            )

        Enrollment = self.env['unicore.enrollment']
        new_enrollment = Enrollment.with_context(
            auto_waitlist=False
        ).create({
            'student_id': self.student_id.id,
            'course_offering_id': self.course_offering_id.id,
            'registration_type': 'waitlist_promotion',
        })

        self.write({
            'waitlist_state': 'promoted',
            'promoted_enrollment_id': new_enrollment.id,
        })
        self.message_post(
            body=_('Promoted to enrollment by %s.') % self.env.user.name
        )
        self._renumber_queue()

    def action_decline(self):
        self.ensure_one()
        self.waitlist_state = 'declined'
        self.message_post(
            body=_('Student declined the waitlist offer.')
        )
        self._renumber_queue()

    def action_expire(self):
        self.ensure_one()
        self.waitlist_state = 'expired'
        self.message_post(
            body=_('Waitlist offer expired without response.')
        )
        self._renumber_queue()

    def _renumber_queue(self):
        """
        After a waitlist entry leaves 'waiting' status, renumber
        remaining waiting entries so positions stay sequential
        (1, 2, 3...) without gaps.
        """
        self.ensure_one()
        remaining = self.search([
            ('course_offering_id', '=', self.course_offering_id.id),
            ('waitlist_state', '=', 'waiting'),
        ], order='position asc')
        for index, entry in enumerate(remaining, start=1):
            if entry.position != index:
                entry.position = index
