from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('oacis', 'security', 'post_install', '-at_install')
class PortalRuleCoverageTest(TransactionCase):
    """Defense-in-depth regression: every model surfaced through the
    student portal must keep an ir.rule restricting group_oacis_student
    to the student's own records.

    The original rules were consolidated into each owning module using
    the ``student_id.partner_id.user_ids`` pattern. This test fails if a
    refactor or new module drops that coverage, so DB-level isolation
    never regresses even though portal controllers use sudo().
    """

    # (model_name, owning_module) — models exposed via student portal.
    PORTAL_MODELS = [
        ('oacis.student', 'oacis_student'),
        ('oacis.enrollment', 'oacis_admission'),
        ('oacis.grade.entry', 'oacis_grading'),
        ('oacis.semester.result', 'oacis_grading'),
        ('oacis.fee.invoice', 'oacis_fees'),
        ('oacis.attendance.record', 'oacis_attendance'),
        ('oacis.library.issue', 'oacis_library'),
        ('oacis.hostel.allocation', 'oacis_hostel'),
        ('oacis.transport.pass', 'oacis_transport'),
        ('oacis.exam.hall.ticket', 'oacis_exam'),
    ]

    def setUpClass(self):
        super().setUpClass()
        self.student_group = self.env.ref(
            'oacis_base.group_oacis_student')

    def _model_installed(self, model_name):
        return model_name in self.env

    def test_01_student_self_view_rules_exist(self):
        Rule = self.env['ir.rule'].sudo()
        missing = []
        for model_name, module in self.PORTAL_MODELS:
            if not self._model_installed(model_name):
                continue
            Model = self.env[model_name]
            rules = Rule.search([
                ('model_id', '=', Model.id),
                ('groups', 'in', self.student_group.ids),
                ('perm_read', '=', True),
            ])
            if not rules:
                missing.append('%s (owned by %s)' % (model_name, module))
        self.assertFalse(
            missing,
            'Portal-facing models lost their student self-view record '
            'rules; restore defense-in-depth for: %s' % ', '.join(missing),
        )

    def test_02_rules_use_partner_user_link(self):
        """Rules must bind records to the logged-in user (directly or via
        partner user_ids), not just company/campus scoping."""
        Rule = self.env['ir.rule'].sudo()
        weak = []
        for model_name, module in self.PORTAL_MODELS:
            if not self._model_installed(model_name):
                continue
            Model = self.env[model_name]
            rules = Rule.search([
                ('model_id', '=', Model.id),
                ('groups', 'in', self.student_group.ids),
                ('perm_read', '=', True),
            ])
            has_owner_clause = any(
                'user.id' in (rule.domain_force or '')
                and 'partner_id' in (rule.domain_force or '')
                for rule in rules
            )
            if not has_owner_clause:
                weak.append('%s (owned by %s)' % (model_name, module))
        self.assertFalse(
            weak,
            'Student record rules lack an owner-binding clause '
            '(partner_id/user_ids): %s' % ', '.join(weak),
        )
