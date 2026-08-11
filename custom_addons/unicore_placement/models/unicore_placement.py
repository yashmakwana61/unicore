from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PlacementCompany(models.Model):
    _name = 'unicore.placement.company'
    _description = 'Placement Company'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Company Name', required=True, tracking=True)
    industry = fields.Char(string='Industry', tracking=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.company)


class PlacementDrive(models.Model):
    _name = 'unicore.placement.drive'
    _description = 'Placement Drive'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    _check_company_auto = True
    _rec_name = 'name'

    company_id = fields.Many2one(
        'unicore.placement.company',
        string='Company',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    institution_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='company_id.company_id',
        store=True,
    )
    date = fields.Date(string='Drive Date', required=True, tracking=True)
    eligible_program_ids = fields.Many2many(
        'unicore.program',
        'unicore_placement_drive_program_rel',
        'drive_id', 'program_id',
        string='Eligible Programs',
        domain="[('company_id', 'in', [institution_id, False])]",
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)

    name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('company_id', 'date')
    def _compute_name(self):
        for rec in self:
            company_name = rec.company_id.name if rec.company_id else 'Unknown'
            date_str = str(rec.date) if rec.date else 'Unknown'
            rec.name = f"{company_name} Placement Drive ({date_str})"

    def action_activate(self):
        self.write({'state': 'active'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class PlacementApplication(models.Model):
    _name = 'unicore.placement.application'
    _description = 'Placement Application'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'create_date desc'
    _check_company_auto = True
    _rec_name = 'name'

    student_id = fields.Many2one(
        'unicore.student',
        string='Student',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='student_id.company_id',
        store=True,
    )
    drive_id = fields.Many2one(
        'unicore.placement.drive',
        string='Placement Drive',
        required=True,
        domain="[('institution_id', 'in', [company_id, False])]",
        tracking=True,
    )
    status = fields.Selection([
        ('applied', 'Applied'),
        ('shortlisted', 'Shortlisted'),
        ('offered', 'Offered'),
        ('rejected', 'Rejected')
    ], string='Status', default='applied', required=True, tracking=True)

    name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('student_id', 'drive_id')
    def _compute_name(self):
        for rec in self:
            student_name = rec.student_id.display_name if rec.student_id else 'Unknown'
            drive_name = rec.drive_id.display_name if rec.drive_id else 'Unknown'
            rec.name = f"{student_name} - {drive_name}"

    @api.constrains('student_id', 'drive_id')
    def _check_eligibility_and_duplicates(self):
        for rec in self:
            # Check duplicate application
            existing = self.search([
                ('student_id', '=', rec.student_id.id),
                ('drive_id', '=', rec.drive_id.id),
                ('id', '!=', rec.id)
            ])
            if existing:
                raise ValidationError(_('Student has already applied to this drive.'))
                
            # Check eligibility
            if rec.drive_id.eligible_program_ids and rec.student_id.program_id:
                if rec.student_id.program_id not in rec.drive_id.eligible_program_ids:
                    raise ValidationError(_('Student is not in an eligible program for this drive.'))

    def action_shortlist(self):
        self.write({'status': 'shortlisted'})

    def action_offer(self):
        self.write({'status': 'offered'})

    def action_reject(self):
        self.write({'status': 'rejected'})
