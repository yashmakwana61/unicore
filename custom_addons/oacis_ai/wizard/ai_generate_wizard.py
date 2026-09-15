from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AIGenerateWizard(models.TransientModel):
    """Popup wizard for AI text generation, rewriting, and summarisation.

    Can be opened from any form view via a server action or button.
    Pass ``default_source_text`` or context ``active_model/active_id`` to
    pre-fill. Use ``Insert into Record`` to write the result back.
    """
    _name = 'oacis.ai.generate.wizard'
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
            ('quiz', 'Create Quiz'),
            ('notice', 'Draft Notice'),
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
    prompt_id = fields.Many2one(
        'oacis.ai.prompt', string='Template',
        help='Pick a reusable prompt template to pre-fill the instructions.',
    )
    target_language = fields.Selection(
        selection=[
            ('English', 'English'),
            ('Hindi', 'Hindi'),
            ('Gujarati', 'Gujarati'),
            ('Marathi', 'Marathi'),
            ('Tamil', 'Tamil'),
            ('Telugu', 'Telugu'),
            ('French', 'French'),
            ('Spanish', 'Spanish'),
            ('German', 'German'),
        ],
        string='Target Language',
        default='English',
        help='Language to translate to (only used for Translate action).',
    )
    target_language_custom = fields.Char(
        string='Other Language',
        help='Fill in when the language is not in the list above.',
    )
    result_text = fields.Text(
        string='Result',
    )
    # Insert-back bookkeeping (set from context when launched from a record)
    res_model = fields.Char(string='Target Model', readonly=True)
    res_id = fields.Integer(string='Target Record', readonly=True)
    target_field = fields.Char(string='Target Field', readonly=True)

    @api.onchange('prompt_id')
    def _onchange_prompt_id(self):
        if self.prompt_id and not self.prompt:
            self.prompt = self.prompt_id.prompt_text

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        if 'active_model' in ctx and 'res_model' in fields_list:
            res.setdefault('res_model', ctx.get('active_model'))
        if 'active_id' in ctx and 'res_id' in fields_list:
            try:
                res.setdefault('res_id', int(ctx.get('active_id') or 0) or False)
            except (ValueError, TypeError):
                pass
        if ctx.get('default_source_text') and 'source_text' in fields_list:
            res.setdefault('source_text', ctx.get('default_source_text'))
        if ctx.get('default_target_field') and 'target_field' in fields_list:
            res.setdefault('target_field', ctx.get('default_target_field'))
        return res

    def _effective_language(self):
        self.ensure_one()
        return self.target_language_custom or self.target_language or 'English'

    def action_generate(self):
        """Call the AI provider and populate the result field."""
        self.ensure_one()
        provider = self.env['oacis.ai.provider']
        if self.prompt_id and not self.prompt:
            self.prompt = self.prompt_id.prompt_text

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
                feature='wizard:generate',
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
            lang = self._effective_language()
            result = provider.rewrite_text(
                self.source_text,
                f'Translate this text accurately into {lang}',
            )
        elif self.action == 'quiz':
            topic = self.prompt or self.source_text
            if not topic:
                raise UserError(_('Please enter the quiz topic in Prompt.'))
            result = provider.generate_quiz(topic)
        elif self.action == 'notice':
            topic = self.prompt or self.source_text
            if not topic:
                raise UserError(_('Please enter the notice topic in Prompt.'))
            result = provider.draft_notice(topic)
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

    def action_insert_into_record(self):
        """Write result_text back to the originating record field."""
        self.ensure_one()
        if not self.result_text:
            raise UserError(_('Generate a result first.'))
        if not (self.res_model and self.res_id and self.target_field):
            raise UserError(_(
                'This wizard was not opened from a record field. '
                'Copy the result manually.',
            ))
        Model = self.env.get(self.res_model)
        if Model is None:
            raise UserError(_('Unsupported target model: %s') % self.res_model)
        Model.check_access_rights('write', raise_exception=True)
        record = Model.browse(self.res_id)
        if not record.exists():
            raise UserError(_('Target record no longer exists.'))
        record.check_access_rule('write')
        if self.target_field not in record._fields:
            raise UserError(_('Field %s does not exist.') % self.target_field)
        Model.check_field_access_rights('write', [self.target_field])
        record.write({self.target_field: self.result_text})
        return {'type': 'ir.actions.act_window_close'}
