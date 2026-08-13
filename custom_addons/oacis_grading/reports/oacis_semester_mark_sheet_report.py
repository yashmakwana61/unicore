from odoo import api, models


class OacisSemesterMarkSheetReport(models.AbstractModel):
    _name = 'report.oacis_grading.oacis_semester_mark_sheet_template'
    _description = 'Semester Mark Sheet Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        semesters = self.env['oacis.semester'].browse(docids)
        data = data or {}

        report_data = []
        for semester in semesters:
            entries = self.env['oacis.grade.entry'].search([
                ('semester_id', '=', semester.id),
                ('entry_state', 'in', ['published', 'locked']),
            ], order='course_offering_id, student_id')

            by_offering = {}
            for entry in entries:
                by_offering.setdefault(
                    entry.course_offering_id, [],
                ).append(entry)

            offerings = []
            for offering in sorted(
                by_offering,
                key=lambda o: (o.course_id.code or '', o.name or ''),
            ):
                rows = []
                for entry in by_offering[offering]:
                    rows.append({
                        'student': entry.student_id,
                        'internal': entry.internal_marks,
                        'external': entry.external_marks,
                        'total': entry.total_marks_obtained,
                        'total_max': entry.total_marks_max,
                        'percentage': entry.percentage,
                        'letter_grade': entry.letter_grade,
                        'grade_point': entry.grade_point,
                        'is_pass': entry.is_pass,
                    })
                offerings.append({
                    'offering': offering,
                    'course': offering.course_id,
                    'faculty': offering.faculty_member_id,
                    'rows': rows,
                })

            report_data.append({
                'semester': semester,
                'offerings': offerings,
                'company_name': (
                    semester.company_id.name
                    or self.env.company.name
                ),
            })

        return {
            'doc_ids': docids,
            'doc_model': 'oacis.semester',
            'docs': semesters,
            'report_data': report_data,
            'data': data or {},
        }
