from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UnicoreNotice(models.Model):
    _name = 'unicore.notice'
    _description = 'UniCore Notice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'pinned desc, publish_date desc, id desc'
    _rec_name = 'title'

    title = fields.Char(string='Title', required=True, tracking=True)
    body = fields.Html(string='Body', required=True, sanitize=True, tracking=True)
    notice_type = fields.Selection(
        selection=[
            ('general', 'General'),
            ('academic', 'Academic'),
            ('exam', 'Exam'),
            ('fee', 'Fee'),
            ('event', 'Event'),
        ],
        string='Notice Type',
        default='general',
        required=True,
        tracking=True,
    )
    audience = fields.Selection(
        selection=[
            ('all', 'All'),
            ('students', 'Students'),
            ('faculty', 'Faculty'),
            ('guardians', 'Guardians'),
            ('specific', 'Specific Campus / Program'),
        ],
        string='Audience',
        default='all',
        required=True,
        tracking=True,
    )
    publish_date = fields.Date(
        string='Publish Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    expiry_date = fields.Date(string='Expiry Date', tracking=True)
    attachment = fields.Binary(string='Attachment')
    attachment_name = fields.Char(string='Attachment Name')
    pinned = fields.Boolean(string='Pinned', default=False, tracking=True)
    active = fields.Boolean(string='Active', default=True, tracking=True)
    publisher_id = fields.Many2one(
        comodel_name='res.users',
        string='Published By',
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        default=lambda self: self.env.company,
        required=True,
        tracking=True,
    )
    campus_ids = fields.Many2many(
        comodel_name='unicore.campus',
        relation='unicore_notice_campus_rel',
        column1='notice_id',
        column2='campus_id',
        string='Campuses',
    )
    program_ids = fields.Many2many(
        comodel_name='unicore.program',
        relation='unicore_notice_program_rel',
        column1='notice_id',
        column2='program_id',
        string='Programs',
    )

    _sql_constraints = [
        ('title_company_unique', 'UNIQUE(title, company_id)', 'A notice title must be unique per institution.'),
    ]

    @api.constrains('publish_date', 'expiry_date')
    def _check_dates(self):
        for record in self:
            if record.publish_date and record.expiry_date and record.expiry_date < record.publish_date:
                raise ValidationError(_('Expiry date cannot be earlier than publish date.'))
