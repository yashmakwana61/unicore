from odoo import _, api, models
from odoo.exceptions import UserError


class UnicoreSequenceMixin(models.AbstractModel):
    """Per-company sequence numbering helper (multi-institution compliance, C1).

    Gives every institution an *independent* counter for a given sequence code.
    On first use it materialises a per-company ``ir.sequence`` from the global
    template record (``company_id = False``), so numbering never leaks between
    institutions even when the same Odoo database serves several companies.
    """

    _name = 'unicore.sequence.mixin'
    _description = 'Per-company sequence numbering mixin'

    @api.model
    def _get_sequence(self, code, company_id=None):
        """Return the ``ir.sequence`` scoped to ``company_id`` (creating a
        per-company copy from the global template on first use)."""
        company = self.env['res.company'].browse(
            company_id or self.env.company.id
        )
        seq_model = self.env['ir.sequence'].sudo()
        sequence = seq_model.search([
            ('code', '=', code),
            ('company_id', '=', company.id),
        ], limit=1)
        if sequence:
            return sequence

        template = seq_model.search([
            ('code', '=', code),
            ('company_id', '=', False),
        ], limit=1)
        if not template:
            raise UserError(_(
                'Sequence "%s" is not configured. Please add a global '
                'sequence template for it.' % code
            ))

        return seq_model.create({
            'name': '%s - %s' % (template.name, company.name),
            'code': code,
            'prefix': template.prefix,
            'padding': template.padding,
            'number_next': 1,
            'number_increment': 1,
            'implementation': template.implementation or 'standard',
            'company_id': company.id,
        })

    @api.model
    def _next_sequence(self, code, company_id=None):
        """Next number of the per-company sequence ``code``."""
        return self._get_sequence(code, company_id).next_by_id()
