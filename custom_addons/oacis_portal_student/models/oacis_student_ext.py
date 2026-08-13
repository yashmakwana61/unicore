"""
Oacis Student Extension for Portal
"""
from odoo import _, fields, models
from odoo.exceptions import UserError


class OacisStudent(models.Model):
    _inherit = 'oacis.student'

    has_portal_user = fields.Boolean(
        compute='_compute_has_portal_user',
        string="Has Portal User",
        help="Technical field to determine if a portal user exists for this student.",
    )

    def _compute_has_portal_user(self):
        for student in self:
            # Check if any user is linked to the student's partner
            student.has_portal_user = bool(student.partner_id.user_ids)

    def action_grant_portal_access(self):
        """
        Opens the standard Odoo Portal Access Management wizard
        for this student's related partner.
        Auto-creates a res.partner if one doesn't exist yet.
        """
        self.ensure_one()

        # Auto-create partner from student data if missing
        if not self.partner_id:
            if not self.email:
                raise UserError(
                    _("Please set an email address on this "
                      "student record before granting portal access."),
                )
            partner_vals = {
                'name': self.display_name or self.name,
                'email': self.email,
                'phone': self.mobile,
                'image_1920': self.image_1920,
                'type': 'contact',
                'company_id': self.company_id.id,
                'company_type': 'person',
            }
            partner = self.env['res.partner'].sudo().create(partner_vals)
            self.partner_id = partner.id

        return self.env['portal.wizard'].with_context(
            active_ids=self.partner_id.ids,
            active_model='res.partner',
        ).action_open_wizard()
