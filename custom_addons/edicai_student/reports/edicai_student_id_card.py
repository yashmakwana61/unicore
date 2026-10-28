from odoo import api, models


class EdicaiStudentIdCardReport(models.AbstractModel):
    _name = 'report.edicai_student.student_id_card'
    _description = 'Student ID Card Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        students = self.env['edicai.student'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'edicai.student',
            'docs': students,
            'data': data or {},
        }
