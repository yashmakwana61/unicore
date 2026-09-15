from odoo import fields, models


class OacisAIPrompt(models.Model):
    """Reusable prompt template library (e.g. admission, academic, fees)."""
    _name = 'oacis.ai.prompt'
    _description = 'AI Prompt Template'
    _order = 'category, name'

    name = fields.Char(string='Title', required=True)
    category = fields.Selection(
        selection=[
            ('admission', 'Admission'),
            ('academic', 'Academic'),
            ('fees', 'Fees & Finance'),
            ('general', 'General'),
        ],
        default='general',
        required=True,
    )
    prompt_text = fields.Text(string='Prompt', required=True)
    is_shared = fields.Boolean(
        string='Shared with all AI users',
        default=True,
        help='If unchecked, only the creator (and managers) can see it.',
    )
    active = fields.Boolean(default=True)
