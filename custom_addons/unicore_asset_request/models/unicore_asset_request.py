"""
UniCore Asset Request Model
Equipment/facility request and approval workflow.
Faculty and staff submit requests for assets; administrators
review and approve/reject; once approved, the request is
fulfilled (equipment delivered or booked).
"""
import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UniCoreAssetRequest(models.Model):
    _name = 'unicore.asset.request'
    _description = 'Asset Request'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _check_company_auto = True

    name = fields.Char(
        string='Request Number',
        readonly=True,
        copy=False,
        default='/',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )

    requested_by = fields.Many2one(
        comodel_name='res.users',
        string='Requested By',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        ondelete='restrict',
        tracking=True,
    )

    faculty_member_id = fields.Many2one(
        comodel_name='unicore.faculty.member',
        string='Faculty / Staff Member',
        ondelete='restrict',
        tracking=True,
        help='Link to the faculty or staff member making the request (if applicable)',
    )

    asset_id = fields.Many2one(
        comodel_name='unicore.asset',
        string='Asset',
        ondelete='restrict',
        tracking=True,
        domain="[('company_id', '=', company_id), ('asset_state', 'in', ['available', 'in_use'])]",
    )

    asset_description = fields.Char(
        string='Asset Description',
        tracking=True,
        help='Free-text description when selecting a specific asset is not required',
    )

    asset_type = fields.Selection(
        selection=[
            ('projector', 'Projector'),
            ('lab_equipment', 'Lab Equipment'),
            ('computer', 'Computer / Laptop'),
            ('furniture', 'Furniture'),
            ('audio_video', 'Audio / Video'),
            ('vehicle', 'Vehicle'),
            ('other', 'Other'),
        ],
        string='Asset Type',
        tracking=True,
    )

    requested_quantity = fields.Integer(
        string='Quantity',
        default=1,
        required=True,
        tracking=True,
    )

    reason = fields.Text(
        string='Reason / Justification',
        required=True,
        tracking=True,
    )

    needed_by_date = fields.Date(
        string='Needed By',
        required=True,
        tracking=True,
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('fulfilled', 'Fulfilled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    approver_id = fields.Many2one(
        comodel_name='res.users',
        string='Approver',
        ondelete='restrict',
        tracking=True,
        domain="[('share', '=', False)]",
    )

    approved_date = fields.Date(
        string='Approval Date',
        readonly=True,
        tracking=True,
    )

    fulfilled_date = fields.Date(
        string='Fulfilled Date',
        readonly=True,
        tracking=True,
    )

    rejection_reason = fields.Text(
        string='Rejection Reason',
        tracking=True,
    )

    # ------------------------------------------------------------
    # Onchange
    # ------------------------------------------------------------

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        """Auto-fill asset type when a specific asset is selected."""
        if self.asset_id:
            self.asset_type = self.asset_id.asset_type

    # ------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'unicore.asset.request',
                ) or '/'
        return super().create(vals_list)

    # ------------------------------------------------------------
    # Workflow Actions
    # ------------------------------------------------------------

    def action_submit(self):
        """Submit the request for approval."""
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft requests can be submitted.'))
            if not record.asset_id and not record.asset_description:
                raise UserError(_('Please select an asset or provide an asset description.'))
            record.write({
                'state': 'submitted',
            })
            record._post_state_message('draft', 'submitted')
            record._assign_approver()

    def action_approve(self):
        """Approve the request."""
        for record in self:
            if record.state != 'submitted':
                raise UserError(_('Only submitted requests can be approved.'))
            record.write({
                'state': 'approved',
                'approved_date': date.today(),
            })
            record._post_state_message('submitted', 'approved')

    def action_reject(self):
        """Reject the request."""
        for record in self:
            if record.state != 'submitted':
                raise UserError(_('Only submitted requests can be rejected.'))
            record.write({
                'state': 'rejected',
            })
            record._post_state_message('submitted', 'rejected')

    def action_fulfill(self):
        """Mark the request as fulfilled."""
        for record in self:
            if record.state != 'approved':
                raise UserError(_('Only approved requests can be fulfilled.'))
            record.write({
                'state': 'fulfilled',
                'fulfilled_date': date.today(),
            })
            record._post_state_message('approved', 'fulfilled')

    def action_reset_to_draft(self):
        """Reset the request back to draft."""
        for record in self:
            if record.state not in ('submitted', 'rejected'):
                raise UserError(_('Only submitted or rejected requests can be reset to draft.'))
            old_state = record.state
            record.write({
                'state': 'draft',
                'rejection_reason': False,
                'approved_date': False,
            })
            record._post_state_message(old_state, 'draft')

    # ------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------

    def _post_state_message(self, old_state, new_state):
        """Post a chatter message on state transition."""
        self.ensure_one()
        selection_labels = dict(self._fields['state'].selection)
        self.message_post(
            body=_(
                'Status changed from <b>%(old)s</b> to <b>%(new)s</b>.',
                old=selection_labels.get(old_state, old_state),
                new=selection_labels.get(new_state, new_state),
            ),
            subtype_id=self.env.ref('mail.mt_note', raise_if_not_found=False).id,
        )

    def _assign_approver(self):
        """Assign the default approver (admin or manager)."""
        self.ensure_one()
        if self.approver_id:
            return
        Admin = self.env['res.users']
        admin = Admin.search([
            ('groups_id', 'in', [
                self.env.ref('unicore_base.group_unicore_admin').id,
            ]),
            ('share', '=', False),
        ], limit=1)
        if admin:
            self.approver_id = admin
