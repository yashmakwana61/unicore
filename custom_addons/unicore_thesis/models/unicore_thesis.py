from odoo import api, fields, models


class Thesis(models.Model):
    _name = 'unicore.thesis'
    _description = 'Thesis'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _check_company_auto = True

    title = fields.Char(string='Thesis Title', required=True, tracking=True)
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
    supervisor_id = fields.Many2one(
        'unicore.faculty.member',
        string='Supervisor',
        required=True,
        domain="[('company_id', 'in', [company_id, False])]",
        tracking=True,
    )
    abstract = fields.Text(string='Abstract')
    status = fields.Selection([
        ('proposal', 'Proposal Submitted'),
        ('research', 'In Research'),
        ('draft', 'Draft Submitted'),
        ('submitted', 'Final Submission'),
        ('defended', 'Defended'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='proposal', required=True, tracking=True)
    review_ids = fields.One2many(
        'unicore.thesis.review',
        'thesis_id',
        string='Reviews',
    )
    document = fields.Binary(string='Thesis Document', attachment=True)
    document_filename = fields.Char(string='Document Filename')

    def action_approve(self):
        self.write({'status': 'approved'})

    def action_reject(self):
        self.write({'status': 'rejected'})


class ThesisReview(models.Model):
    _name = 'unicore.thesis.review'
    _description = 'Thesis Review'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'create_date desc'
    _check_company_auto = True
    _rec_name = 'name'

    thesis_id = fields.Many2one(
        'unicore.thesis',
        string='Thesis',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='thesis_id.company_id',
        store=True,
    )
    reviewer_id = fields.Many2one(
        'unicore.faculty.member',
        string='Reviewer',
        required=True,
        domain="[('company_id', 'in', [company_id, False])]",
    )
    comments = fields.Text(string='Review Comments', required=True)
    decision = fields.Selection([
        ('approve', 'Recommend Approval'),
        ('revise', 'Needs Revision'),
        ('reject', 'Recommend Rejection'),
    ], string='Decision', required=True)

    name = fields.Char(
        string='Display Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('thesis_id', 'reviewer_id')
    def _compute_name(self):
        for rec in self:
            reviewer_name = rec.reviewer_id.display_name if rec.reviewer_id else 'Unknown'
            rec.name = f"Review by {reviewer_name}"
