from odoo import api, models


class OacisGradeBookReport(models.AbstractModel):
    _name = 'report.oacis_gradebook.oacis_gradebook_template'
    _description = 'Grade Book Mark Sheet Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        configs = self.env['oacis.gradebook.config'].browse(docids)
        data = data or {}

        report_data = []
        for config in configs:
            assignments = []
            seen = set()
            for assignment in config.assignment_ids:
                if assignment.id in seen:
                    continue
                seen.add(assignment.id)
                assignments.append({
                    'id': assignment.id,
                    'title': assignment.title,
                    'max_marks': assignment.max_marks,
                    'type': assignment.assignment_type,
                })

            rows = []
            for line in config.student_line_ids:
                scores = {
                    al.assignment_id.id: al.marks_obtained
                    for al in line.assignment_line_ids
                }
                rows.append({
                    'student': line.student_id,
                    'scores': scores,
                    'graded_count': line.graded_assignment_count,
                    'total_possible': line.total_possible_marks,
                    'total_obtained': line.total_obtained_marks,
                    'percentage': line.assignment_percentage,
                    'ca_component': line.computed_ca_component,
                    'current_ca': line.current_ca_marks,
                    'entry_state': line.grade_entry_state,
                    'is_synced': line.is_synced,
                })

            report_data.append({
                'config': config,
                'course': config.course_id,
                'offering': config.course_offering_id,
                'semester': config.semester_id,
                'faculty': config.faculty_member_id,
                'campus': config.campus_id,
                'weight': config.assignment_weight_pct,
                'max_ca': config.max_ca_marks,
                'assignment_count': config.assignment_count,
                'graded_assignment_count': config.graded_assignment_count,
                'student_count': config.student_count,
                'class_avg': config.class_avg_assignment_pct,
                'assignments': assignments,
                'rows': rows,
                'company_name': (
                    config.company_id.name
                    or self.env.company.name
                ),
            })

        return {
            'doc_ids': docids,
            'doc_model': 'oacis.gradebook.config',
            'docs': configs,
            'report_data': report_data,
            'data': data or {},
        }
