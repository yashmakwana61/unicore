from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EntranceTest(models.Model):
    _name = 'oacis.admission.entrance.test'
    _description = 'Entrance Test'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'test_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Test Name', required=True, tracking=True)
    code = fields.Char(string='Test Code', required=True, tracking=True)
    cycle_id = fields.Many2one(
        comodel_name='oacis.admission.cycle', string='Admission Cycle',
        required=True, tracking=True,
    )
    test_date = fields.Date(string='Test Date', required=True, tracking=True)
    start_time = fields.Float(string='Start Time', required=True, help='Hour in 24h format e.g. 9.0 for 09:00')
    end_time = fields.Float(string='End Time', required=True, help='Hour in 24h format e.g. 11.0 for 11:00')
    venue = fields.Char(string='Venue', required=True)
    max_marks = fields.Float(string='Maximum Marks', required=True, default=100.0)
    passing_marks = fields.Float(string='Passing Marks', required=True, default=40.0)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('result_published', 'Result Published'),
        ],
        string='Status', default='draft', required=True, tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        required=True, default=lambda self: self.env.company,
        ondelete='restrict', tracking=True,
    )
    applicant_line_ids = fields.One2many(
        comodel_name='oacis.admission.entrance.test.line',
        inverse_name='test_id', string='Applicants',
    )
    total_applicants = fields.Integer(
        string='Total Applicants', compute='_compute_counts', store=False,
    )
    attended_count = fields.Integer(
        string='Attended', compute='_compute_counts', store=False,
    )

    @api.depends('applicant_line_ids')
    def _compute_counts(self):
        for record in self:
            record.total_applicants = len(record.applicant_line_ids)
            record.attended_count = len(record.applicant_line_ids.filtered('attended'))

    def action_schedule(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft tests can be scheduled.'))
            record.write({'state': 'scheduled'})

    def action_start(self):
        for record in self:
            if record.state != 'scheduled':
                raise UserError(_('Only scheduled tests can be started.'))
            record.write({'state': 'in_progress'})

    def action_complete(self):
        for record in self:
            if record.state != 'in_progress':
                raise UserError(_('Only in-progress tests can be completed.'))
            record.write({'state': 'completed'})

    def action_publish_results(self):
        for record in self:
            if record.state != 'completed':
                raise UserError(_('Test must be completed before publishing results.'))
            for line in record.applicant_line_ids:
                if line.attended and line.marks_obtained < 0:
                    raise UserError(_(
                        'Please enter marks for all attended applicants before publishing.',
                    ))
                if line.applicant_id.state == 'entrance_scheduled':
                    if line.attended:
                        line.applicant_id.entrance_score = line.marks_obtained
                        line.applicant_id.action_add_to_merit()
                    else:
                        line.applicant_id.write({
                            'state': 'rejected',
                            'rejection_reason': _('Did not attend entrance test.'),
                        })
            record.write({'state': 'result_published'})

    @api.constrains('max_marks', 'passing_marks')
    def _check_marks(self):
        for record in self:
            if record.passing_marks > record.max_marks:
                raise ValidationError(_('Passing marks cannot exceed maximum marks.'))
            if record.passing_marks < 0 or record.max_marks <= 0:
                raise ValidationError(_('Marks must be positive values.'))

    @api.constrains('start_time', 'end_time')
    def _check_time(self):
        for record in self:
            if record.start_time >= record.end_time:
                raise ValidationError(_('Start time must be before end time.'))

    @api.constrains('test_date')
    def _check_test_date(self):
        for record in self:
            if record.test_date and record.cycle_id:
                if record.test_date < record.cycle_id.start_date:
                    raise ValidationError(_('Test date cannot be before cycle start date.'))
                if record.test_date > record.cycle_id.end_date:
                    raise ValidationError(_('Test date cannot be after cycle end date.'))


class EntranceTestLine(models.Model):
    _name = 'oacis.admission.entrance.test.line'
    _description = 'Entrance Test Applicant Line'
    _rec_name = 'applicant_id'

    test_id = fields.Many2one(
        comodel_name='oacis.admission.entrance.test', string='Entrance Test',
        required=True, ondelete='cascade',
    )
    applicant_id = fields.Many2one(
        comodel_name='oacis.admission.applicant', string='Applicant',
        required=True, ondelete='restrict',
    )
    marks_obtained = fields.Float(string='Marks Obtained', default=0.0)
    attended = fields.Boolean(string='Attended', default=False)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        related='test_id.company_id', store=True,
    )

    @api.constrains('marks_obtained', 'test_id')
    def _check_marks_obtained(self):
        for record in self:
            if record.marks_obtained < 0:
                raise ValidationError(_('Marks obtained cannot be negative.'))
            if record.test_id and record.marks_obtained > record.test_id.max_marks:
                raise ValidationError(_(
                    'Marks obtained cannot exceed maximum marks (%s).',
                ) % record.test_id.max_marks)

    _sql_constraints = [
        ('unique_test_applicant', 'UNIQUE(test_id, applicant_id)',
         'Each applicant can only appear once per entrance test.'),
    ]
