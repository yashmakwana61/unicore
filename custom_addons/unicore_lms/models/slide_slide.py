# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    # Extend slide_category if needed, or just use boolean/relational fields
    is_unicore_assignment = fields.Boolean(
        string="Is Unicore Assignment",
        help="Check this if this slide represents a Unicore Assignment."
    )
    
    unicore_assignment_id = fields.Many2one(
        'unicore.assignment',
        string="Unicore Assignment",
        help="Link to the specific Unicore Assignment."
    )
    
    is_unicore_quiz = fields.Boolean(
        string="Is Unicore Quiz",
        help="Check this if this slide represents a Unicore Quiz."
    )
    
    unicore_quiz_id = fields.Many2one(
        'unicore.quiz',
        string="Unicore Quiz",
        help="Link to the specific Unicore Quiz."
    )
    
    # Live Class Integration
    is_live_class = fields.Boolean(
        string="Is Live Class",
        help="Check this if this slide is a scheduled live class (e.g. Zoom/Meet)."
    )
    
    meeting_url = fields.Char(
        string="Meeting URL",
        help="The link to join the live class (Zoom, Teams, Meet, etc.)."
    )
    
    meeting_datetime = fields.Datetime(
        string="Meeting Date & Time",
        help="When the live class is scheduled to happen."
    )
