from odoo import api, models


class UniCoreStudentIdCardReport(models.AbstractModel):
    _name = 'report.unicore_student.student_id_card'
    _description = 'Student ID Card Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        students = self.env['unicore.student'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'unicore.student',
            'docs': students,
            'data': data or {},
        }
