from datetime import date

from odoo import api, models


class OacisBonafideReport(models.AbstractModel):
    _name = 'report.oacis_student.bonafide_template'
    _description = 'Bonafide Certificate Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        students = self.env['oacis.student'].browse(docids)
        data = data or {}

        def get_salutation(gender):
            return {
                'male': 'Mr.',
                'female': 'Ms.',
            }.get(gender, 'Mx.')

        def get_ordinal(n):
            if not n:
                return ''
            suffixes = {1: 'st', 2: 'nd', 3: 'rd'}
            return str(n) + suffixes.get(n, 'th')

        return {
            'doc_ids': docids,
            'doc_model': 'oacis.student',
            'docs': students,
            'data': data,
            'get_salutation': get_salutation,
            'get_ordinal': get_ordinal,
            'today': date.today(),
        }
