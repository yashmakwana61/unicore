"""
UniCore Student — Partner Extension
Links unicore.student to res.partner for accounting/invoicing.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class UnicoreStudentPartnerExt(models.Model):
    _inherit = 'unicore.student'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Billing Partner',
        ondelete='restrict',
        readonly=True,
        help='Auto-linked res.partner for invoicing and payment tracking',
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create student and auto-create/link res.partner if configured."""
        records = super().create(vals_list)

        # Get accounting config to check if auto-create is enabled
        try:
            config = self.env['unicore.fee.accounting.config']._get_active_config(
                company_id=records[0].company_id.id
            )
        except UserError:
            config = None

        for record in records:
            # Skip if partner already linked or auto-create disabled
            if record.partner_id or not config or not config.auto_create_partner:
                continue

            # Create res.partner for the student
            partner = self._create_student_partner(record)
            record.write({'partner_id': partner.id})

        return records

    def write(self, vals):
        """Update partner when student contact details change."""
        result = super().write(vals)

        # Check if sync is enabled
        try:
            config = self.env['unicore.fee.accounting.config']._get_active_config(
                company_id=self.company_id.id
            )
        except UserError:
            config = None

        if config and config.sync_partner_on_update:
            for record in self:
                if record.partner_id:
                    self._sync_partner_from_student(record)

        return result

    def _create_student_partner(self, student):
        """
        Create a res.partner record from student data.

        Returns:
            res.partner record
        """
        partner_data = {
            'name': student.name,
            'email': student.email,
            'phone': student.mobile or student.phone,
            'street': student.address_street,
            'street2': student.address_street2,
            'city': student.address_city,
            'zip': student.address_zip,
            'country_id': student.address_country_id.id or None,
            'state_id': student.address_state_id.id or None,
            'company_id': student.company_id.id,
            'customer_rank': 1,
            'is_company': False,
            'type': 'invoice',
        }

        # Create partner
        partner = self.env['res.partner'].create(partner_data)

        # Add student reference in partner notes
        partner.comment = _('Student ID: %s\nEnrolled in: %s') % (
            student.student_id_number,
            student.program_id.name
        )

        return partner

    def _sync_partner_from_student(self, student):
        """
        Sync student contact details to linked res.partner.

        Called when sync_partner_on_update is enabled.
        """
        if not student.partner_id:
            return

        partner = student.partner_id
        update_vals = {}

        # Sync contact fields
        if student.name != partner.name:
            update_vals['name'] = student.name
        if student.email and student.email != partner.email:
            update_vals['email'] = student.email
        if (student.mobile or student.phone) and (student.mobile or student.phone) != partner.phone:
            update_vals['phone'] = student.mobile or student.phone

        # Sync address fields
        if student.address_street != partner.street:
            update_vals['street'] = student.address_street
        if student.address_street2 != partner.street2:
            update_vals['street2'] = student.address_street2
        if student.address_city != partner.city:
            update_vals['city'] = student.address_city
        if student.address_zip != partner.zip:
            update_vals['zip'] = student.address_zip
        if student.address_country_id and student.address_country_id != partner.country_id:
            update_vals['country_id'] = student.address_country_id.id
        if student.address_state_id and student.address_state_id != partner.state_id:
            update_vals['state_id'] = student.address_state_id.id

        if update_vals:
            partner.write(update_vals)

    def unlink(self):
        """Archive linked partners instead of deleting."""
        for record in self:
            if record.partner_id:
                record.partner_id.write({'active': False})

        return super().unlink()
