from odoo import _, api, fields, models
from odoo.exceptions import UserError


class OfferLetter(models.Model):
    _name = 'unicore.admission.offer.letter'
    _description = 'Offer Letter'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'offer_date desc, id desc'
    _rec_name = 'letter_number'

    letter_number = fields.Char(
        string='Letter No.', readonly=True, copy=False,
        default=lambda self: _('New'), tracking=True,
    )
    applicant_id = fields.Many2one(
        comodel_name='unicore.admission.applicant', string='Applicant',
        required=True, ondelete='cascade', tracking=True,
    )
    applicant_name = fields.Char(
        string='Applicant Name', related='applicant_id.name', store=False,
    )
    program_name = fields.Char(
        string='Program', related='applicant_id.program_id.name', store=False,
    )
    offer_date = fields.Date(
        string='Offer Date', required=True, default=fields.Date.today, tracking=True,
    )
    valid_until = fields.Date(string='Valid Until', tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('expired', 'Expired'),
        ],
        string='Status', default='draft', required=True, tracking=True,
    )
    terms = fields.Text(
        string='Terms & Conditions',
        default='''1. This offer is valid only for the program mentioned above.
2. Admission is subject to verification of all original documents.
3. Fees must be paid by the due date mentioned in the fee schedule.
4. The institution reserves the right to cancel admission for
   any misrepresentation of information.''',
    )
    response_date = fields.Date(string='Response Date', readonly=True, tracking=True)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        required=True, default=lambda self: self.env.company,
        ondelete='restrict', tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('letter_number', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('unicore.admission.offer.letter') or '/'
                vals['letter_number'] = seq
            if not vals.get('valid_until') and vals.get('offer_date'):
                vals['valid_until'] = fields.Date.add(vals['offer_date'], days=30)
        return super().create(vals_list)

    def action_send(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft offer letters can be sent.'))
            record.write({'state': 'sent'})

    def action_accept(self):
        for record in self:
            if record.state != 'sent':
                raise UserError(_('Only sent offer letters can be accepted.'))
            record.write({
                'state': 'accepted',
                'response_date': fields.Date.today(),
            })
            record.applicant_id.action_mark_fee_pending()

    def action_reject(self):
        for record in self:
            if record.state not in ('sent', 'accepted'):
                raise UserError(_('Only sent or accepted offers can be rejected.'))
            record.write({
                'state': 'rejected',
                'response_date': fields.Date.today(),
            })

    def action_mark_expired(self):
        for record in self:
            if record.state not in ('sent', 'draft'):
                raise UserError(_('Only sent or draft offers can be marked as expired.'))
            record.write({'state': 'expired'})
