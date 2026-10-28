from odoo import fields, models


class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    # Extend slide_category if needed, or just use boolean/relational fields
    is_edicai_assignment = fields.Boolean(
        string="Is Edicai Assignment",
        help="Check this if this slide represents a Edicai Assignment.",
    )

    edicai_assignment_id = fields.Many2one(
        'edicai.assignment',
        string="Edicai Assignment",
        help="Link to the specific Edicai Assignment.",
    )

    is_edicai_quiz = fields.Boolean(
        string="Is Edicai Quiz",
        help="Check this if this slide represents a Edicai Quiz.",
    )

    edicai_quiz_id = fields.Many2one(
        'edicai.quiz',
        string="Edicai Quiz",
        help="Link to the specific Edicai Quiz.",
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
