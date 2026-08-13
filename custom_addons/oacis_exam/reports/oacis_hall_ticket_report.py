from odoo import api, models


def _format_time(float_hour):
    if float_hour is None:
        return '--:--'
    hour = int(float_hour)
    minute = int(round((float_hour - hour) * 60))
    period = 'AM' if hour < 12 else 'PM'
    if hour == 0:
        hour12 = 12
    elif hour > 12:
        hour12 = hour - 12
    else:
        hour12 = hour
    return '%02d:%02d %s' % (hour12, minute, period)


class OacisHallTicketReport(models.AbstractModel):
    _name = 'report.oacis_exam.hall_ticket_template'
    _description = 'Exam Hall Ticket Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        hall_tickets = self.env['oacis.exam.hall.ticket'].browse(docids)

        ticket_data = []
        for ticket in hall_tickets:
            student = ticket.student_id
            schedule = ticket.exam_schedule_id
            semester = schedule.semester_id

            courses_exam_map = {}
            if semester:
                semester_schedules = self.env['oacis.exam.schedule'].search([
                    ('semester_id', '=', semester.id),
                    ('exam_state', 'not in', ('draft', 'cancelled')),
                ])
                for sch in semester_schedules:
                    if sch.course_id:
                        courses_exam_map[sch.course_id.id] = sch

            enrollments = self.env['oacis.enrollment'].search([
                ('student_id', '=', student.id),
                ('semester_id', '=', semester.id if semester else False),
                ('enrollment_state', '!=', 'dropped'),
            ])

            exam_rows = []
            for enr in enrollments:
                course = enr.course_id
                es = courses_exam_map.get(course.id)
                exam_rows.append({
                    'course': course,
                    'exam_schedule': es,
                    'exam_date': es.exam_date if es else None,
                    'exam_start': _format_time(es.exam_start_time) if es else '--:--',
                    'exam_end': _format_time(es.exam_end_time) if es else '--:--',
                    'has_exam': es is not None,
                })

            exam_rows.sort(key=lambda r: (
                r['exam_date'] or '',
                r['exam_start'] or '',
            ))

            seating = ticket.seating_id
            room_name = seating.room_id.name if seating and seating.room_id else ''
            seat_number = seating.seat_number if seating else None
            room_code = seating.room_id.code if seating and seating.room_id else ''
            venue_list = schedule.venue_ids

            ticket_data.append({
                'ticket': ticket,
                'student': student,
                'schedule': schedule,
                'semester': semester,
                'exam_rows': exam_rows,
                'room_name': room_name,
                'seat_number': seat_number,
                'room_code': room_code,
                'venue_list': venue_list,
                'instructions': schedule.instructions,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'oacis.exam.hall.ticket',
            'docs': hall_tickets,
            'ticket_data': ticket_data,
            'format_time': _format_time,
            'data': data or {},
        }
