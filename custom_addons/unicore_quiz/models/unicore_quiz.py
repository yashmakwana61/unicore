import json
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class QuestionBank(models.Model):
    _name = 'unicore.question.bank'
    _description = 'Question Bank'
    _inherit = ['unicore.mixin']
    _check_company_auto = True

    question_text = fields.Text(string='Question', required=True)
    option_a = fields.Char(string='Option A', required=True)
    option_b = fields.Char(string='Option B', required=True)
    option_c = fields.Char(string='Option C')
    option_d = fields.Char(string='Option D')
    correct_answer = fields.Selection([
        ('a', 'A'),
        ('b', 'B'),
        ('c', 'C'),
        ('d', 'D')
    ], string='Correct Answer', required=True)
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.company)


class Quiz(models.Model):
    _name = 'unicore.quiz'
    _description = 'Quiz'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    title = fields.Char(string='Quiz Title', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.company)
    question_ids = fields.Many2many(
        'unicore.question.bank',
        'unicore_quiz_question_rel',
        'quiz_id', 'question_id',
        string='Questions',
        domain="[('company_id', 'in', [company_id, False])]"
    )
    time_limit = fields.Integer(string='Time Limit (Minutes)', required=True, default=15)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], string='Status', default='draft', required=True, tracking=True)
    
    def action_activate(self):
        if not self.question_ids:
            raise ValidationError(_('Please add at least one question to activate the quiz.'))
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})


class QuizAttempt(models.Model):
    _name = 'unicore.quiz.attempt'
    _description = 'Quiz Attempt'
    _inherit = ['unicore.mixin']
    _order = 'create_date desc'
    _check_company_auto = True

    student_id = fields.Many2one(
        'unicore.student',
        string='Student',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='student_id.company_id',
        store=True,
    )
    quiz_id = fields.Many2one(
        'unicore.quiz',
        string='Quiz',
        required=True,
        domain="[('company_id', 'in', [company_id, False])]",
    )
    score = fields.Float(string='Score')
    tab_switches = fields.Integer(string='Tab Switches (Anti-Cheating)', default=0)
    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted')
    ], string='Status', default='in_progress', required=True)

    @api.constrains('student_id', 'quiz_id')
    def _check_single_attempt(self):
        for rec in self:
            existing = self.search([
                ('student_id', '=', rec.student_id.id),
                ('quiz_id', '=', rec.quiz_id.id),
                ('id', '!=', rec.id)
            ])
            if existing:
                raise ValidationError(_('A student can only attempt a quiz once.'))

    @api.model
    def submit_quiz_attempt(self, attempt_id, answers, tab_switches):
        attempt = self.browse(attempt_id)
        if not attempt or attempt.state == 'submitted':
            return False
            
        score = 0
        total = len(attempt.quiz_id.question_ids)
        for question in attempt.quiz_id.question_ids:
            # answers dictionary contains question_id as key and answer selection (a/b/c/d) as value
            if answers.get(str(question.id)) == question.correct_answer:
                score += 1
                
        attempt.write({
            'score': (score / total) * 100 if total > 0 else 0,
            'tab_switches': tab_switches,
            'state': 'submitted'
        })
        return True
