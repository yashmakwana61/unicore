from odoo import api, models


class UniCoreTranscriptReport(models.AbstractModel):
    _name = 'report.unicore_grading.unicore_transcript_template'
    _description = 'Academic Transcript Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        students = self.env['unicore.student'].browse(docids)
        data = data or {}

        transcript_data = []
        for student in students:
            semester_results = self.env['unicore.semester.result'].search([
                ('student_id', '=', student.id),
                ('is_published', '=', True),
            ], order='semester_id asc')

            semester_data = []
            for result in semester_results:
                grade_entries = self.env['unicore.grade.entry'].search([
                    ('student_id', '=', student.id),
                    ('semester_id', '=', result.semester_id.id),
                    ('entry_state', 'in', ['published', 'locked']),
                ], order='course_id')

                course_rows = []
                for entry in grade_entries:
                    course_rows.append({
                        'code': entry.course_id.code or '',
                        'course_name': entry.course_id.name,
                        'credit_hours': entry.credit_hours,
                        'internal_marks': entry.internal_marks,
                        'external_marks': entry.external_marks,
                        'total_marks': entry.total_marks_obtained,
                        'total_max': entry.total_marks_max,
                        'letter_grade': entry.letter_grade,
                        'grade_point': entry.grade_point,
                        'grade_points_earned': entry.grade_points_earned,
                        'is_pass': entry.is_pass,
                    })

                semester_data.append({
                    'semester': result.semester_id,
                    'credits_attempted': result.credits_attempted,
                    'credits_earned': result.credits_earned,
                    'semester_gpa': result.semester_gpa,
                    'courses_passed': result.courses_passed,
                    'courses_failed': result.courses_failed,
                    'result_status': result.result_status,
                    'course_rows': course_rows,
                })

            transcript_data.append({
                'student': student,
                'semester_data': semester_data,
                'cgpa': student.cgpa,
                'total_credits_earned': student.total_credits_earned,
                'total_credits_required': student.program_id.total_credits or 0,
                'company_name': (
                    student.company_id.name
                    or self.env.company.name
                ),
            })

        return {
            'doc_ids': docids,
            'doc_model': 'unicore.student',
            'docs': students,
            'transcript_data': transcript_data,
            'data': data or {},
        }
