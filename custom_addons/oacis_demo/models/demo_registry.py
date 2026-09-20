"""Oacis Demo — run registry.

Tracks every record created by the institution-aware demo generator so that
demo data can be listed, regenerated and, most importantly, safely reset
without touching real (non-demo) institution data.

Design notes
------------
* Registry-based tracking is used instead of an ``is_demo`` flag on every
  ``oacis.*`` model.  This keeps the change surface inside ``oacis_demo``
  (no core-module schema changes) while still answering "which records did
  the demo create?".
* Every entry stores ``company_id`` so resets are always scoped to one
  institution — required for multi-institution databases.
* ``sequence`` records creation order; resets delete in reverse order so
  dependent records (payments, grades, …) go before their parents.
"""

from odoo import api, fields, models


class OacisDemoRecord(models.Model):
    _name = 'oacis.demo.record'
    _description = 'Demo Data Registry Entry'
    _order = 'sequence desc, id desc'

    name = fields.Char(
        string='Description',
        required=True,
        help='Human-readable label, e.g. "student:Aarav Patel".',
    )
    run_key = fields.Char(
        string='Run Key',
        required=True,
        index=True,
        help='Identifier of the generator run that created the record.',
    )
    institution_type = fields.Char(
        string='Institution Type',
        help='Institution type dataset this record belongs to.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        index=True,
        ondelete='cascade',
    )
    model_name = fields.Char(
        string='Model',
        required=True,
        index=True,
    )
    res_id = fields.Integer(
        string='Record ID',
        required=True,
    )
    sequence = fields.Integer(
        string='Creation Order',
        required=True,
        default=10,
        help='Creation order within the run; reset deletes highest first.',
    )

    _sql_constraints = [
        ('unique_demo_record',
         'UNIQUE(run_key, model_name, res_id)',
         'This demo record is already registered.'),
    ]

    @api.model
    def log(self, run_key, record, company, institution_type, sequence):
        """Register a newly created demo record."""
        self.create({
            'name': '%s:%s' % (record._name, record.display_name),
            'run_key': run_key,
            'institution_type': institution_type,
            'company_id': company.id,
            'model_name': record._name,
            'res_id': record.id,
            'sequence': sequence,
        })

    def _target(self):
        """Return the referenced recordset (may be empty if already gone)."""
        self.ensure_one()
        if self.model_name not in self.env:
            return self.env['oacis.demo.record'].browse()
        return self.env[self.model_name].browse(self.res_id).exists()
