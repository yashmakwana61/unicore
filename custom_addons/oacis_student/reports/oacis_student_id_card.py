from odoo import api, models


class OacisStudentIdCardReport(models.AbstractModel):
    _name = 'report.oacis_student.student_id_card'
    _description = 'Student ID Card Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        students = self.env['oacis.student'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'oacis.student',
            'docs': students,
            'data': data or {},
        }
