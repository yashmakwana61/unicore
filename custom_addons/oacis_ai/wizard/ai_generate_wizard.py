from odoo import _, fields, models
from odoo.exceptions import UserError


class AIGenerateWizard(models.TransientModel):
    """Popup wizard for AI text generation, rewriting, and summarisation.

    Can be opened from any form view via a server action or button.
    """
    _name = 'unicore.ai.generate.wizard'
    _description = 'AI Text Generator'

    action = fields.Selection(
        selection=[
            ('generate', 'Generate New Text'),
            ('rewrite', 'Rewrite / Improve'),
            ('summarize', 'Summarise'),
            ('expand', 'Expand / Elaborate'),
            ('formal', 'Make Formal'),
            ('casual', 'Make Casual'),
            ('translate', 'Translate'),
        ],
        string='Action',
        default='generate',
        required=True,
    )
    prompt = fields.Text(
        string='Prompt / Instructions',
        help='Describe what you want the AI to generate or how you want the text changed.',
    )
    source_text = fields.Text(
        string='Source Text',
        help='Paste the text you want to rewrite, summarise, or translate.',
    )
    target_language = fields.Char(
        string='Target Language',
        default='English',
        help='Language to translate to (only used for Translate action).',
    )
    result_text = fields.Text(
        string='Result',
        readonly=True,
    )

    def action_generate(self):
        """Call the AI provider and populate the result field."""
        self.ensure_one()
        provider = self.env['unicore.ai.provider']

        if self.action == 'generate':
            if not self.prompt:
                raise UserError(_('Please enter a prompt for text generation.'))
            result = provider.generate_text(
                self.prompt,
                system_prompt=(
                    'You are a professional content writer for an '
                    'education management system. Generate clear, '
                    'well-structured text based on the user prompt.'
                ),
            )
        elif self.action == 'rewrite':
            if not self.source_text:
                raise UserError(_('Please paste the source text to rewrite.'))
            instruction = self.prompt or 'Improve the clarity and professionalism of this text'
            result = provider.rewrite_text(self.source_text, instruction)
        elif self.action == 'summarize':
            if not self.source_text:
                raise UserError(_('Please paste the source text to summarise.'))
            result = provider.summarize_text(self.source_text)
        elif self.action == 'expand':
            if not self.source_text:
                raise UserError(_('Please paste the source text to expand.'))
            result = provider.rewrite_text(
                self.source_text,
                'Expand and elaborate on this text with more detail and examples',
            )
        elif self.action == 'formal':
            if not self.source_text:
                raise UserError(_('Please paste the source text.'))
            result = provider.rewrite_text(
                self.source_text,
                'Rewrite this text in a formal, professional tone',
            )
        elif self.action == 'casual':
            if not self.source_text:
                raise UserError(_('Please paste the source text.'))
            result = provider.rewrite_text(
                self.source_text,
                'Rewrite this text in a casual, friendly tone',
            )
        elif self.action == 'translate':
            if not self.source_text:
                raise UserError(_('Please paste the source text to translate.'))
            lang = self.target_language or 'English'
            result = provider.rewrite_text(
                self.source_text,
                f'Translate this text accurately into {lang}',
            )
        else:
            raise UserError(_('Unknown action.'))

        self.result_text = result
        # Return the same wizard so the user sees the result
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
