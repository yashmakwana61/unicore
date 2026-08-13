from odoo import fields, models


class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    # Extend slide_category if needed, or just use boolean/relational fields
    is_oacis_assignment = fields.Boolean(
        string="Is Oacis Assignment",
        help="Check this if this slide represents a Oacis Assignment.",
    )

    oacis_assignment_id = fields.Many2one(
        'oacis.assignment',
        string="Oacis Assignment",
        help="Link to the specific Oacis Assignment.",
    )

    is_oacis_quiz = fields.Boolean(
        string="Is Oacis Quiz",
        help="Check this if this slide represents a Oacis Quiz.",
    )

    oacis_quiz_id = fields.Many2one(
        'oacis.quiz',
        string="Oacis Quiz",
        help="Link to the specific Oacis Quiz.",
    )

    # Live Class Integration
    is_live_class = fields.Boolean(
        string="Is Live Class",
        help="Check this if this slide is a scheduled live class (e.g. Zoom/Meet).",
    )

    meeting_url = fields.Char(
        string="Meeting URL",
        help="The link to join the live class (Zoom, Teams, Meet, etc.).",
    )

    meeting_datetime = fields.Datetime(
        string="Meeting Date & Time",
        help="When the live class is scheduled to happen.",
    )
