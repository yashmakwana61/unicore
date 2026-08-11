# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    is_academic_course = fields.Boolean(
        string="Is Academic Course",
        help="Check this if this course is part of the Unicore academic curriculum."
    )
    
    course_offering_id = fields.Many2one(
        'unicore.course.offering',
        string="Academic Course Offering",
        help="Link this LMS course to a specific academic offering to auto-enroll students."
    )
    
    program_id = fields.Many2one(
        'unicore.program',
        related='course_offering_id.program_id',
        store=True,
        readonly=True
    )
    
    semester_id = fields.Many2one(
        'unicore.semester',
        related='course_offering_id.semester_id',
        store=True,
        readonly=True
    )

    def action_sync_academic_enrollments(self):
        """
        Sync students from unicore_enrollment (via course_offering)
        to this slide.channel as partners.
        """
        for channel in self:
            if not channel.is_academic_course or not channel.course_offering_id:
                continue
            
            # Assuming offering has enrollment_ids which links to student_id which has partner_id
            enrollments = self.env['unicore.enrollment'].search([
                ('course_offering_id', '=', channel.course_offering_id.id),
                ('enrollment_state', 'in', ['registered', 'enrolled', 'ongoing'])
            ])
            
            for enrollment in enrollments:
                partner = enrollment.student_id.partner_id
                if partner:
                    channel._action_add_members(partner)
        return True

    def action_view_gradebook(self):
        """
        Open the gradebook config associated with this academic course offering.
        """
        self.ensure_one()
        if not self.is_academic_course or not self.course_offering_id:
            return
            
        gradebook = self.env['unicore.gradebook.config'].search([
            ('course_offering_id', '=', self.course_offering_id.id)
        ], limit=1)
        
        if gradebook:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Academic Gradebook',
                'res_model': 'unicore.gradebook.config',
                'view_mode': 'form',
                'res_id': gradebook.id,
            }
        else:
            # Optionally return an action to create it or show a warning
            return {
                'type': 'ir.actions.act_window',
                'name': 'Academic Gradebook',
                'res_model': 'unicore.gradebook.config',
                'view_mode': 'list,form',
                'domain': [('course_offering_id', '=', self.course_offering_id.id)],
                'context': {'default_course_offering_id': self.course_offering_id.id},
            }
