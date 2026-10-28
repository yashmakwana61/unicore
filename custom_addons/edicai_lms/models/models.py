# from odoo import models, fields, api


# class edicai_lms(models.Model):
#     _name = 'edicai_lms.edicai_lms'
#     _description = 'edicai_lms.edicai_lms'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
