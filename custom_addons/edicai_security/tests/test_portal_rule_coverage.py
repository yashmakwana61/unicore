from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('edicai', 'security', 'post_install', '-at_install')
class PortalRuleCoverageTest(TransactionCase):
    """Defense-in-depth regression: every model surfaced through the
    student portal must keep an ir.rule restricting group_edicai_student
    to the student's own records.

    The original rules were consolidated into each owning module using
    the ``student_id.partner_id.user_ids`` pattern. This test fails if a
    refactor or new module drops that coverage, so DB-level isolation
    never regresses even though portal controllers use sudo().
    """

    # (model_name, owning_module) — models exposed via student portal.
    PORTAL_MODELS = [
        ('edicai.student', 'edicai_student'),
        ('edicai.enrollment', 'edicai_admission'),
        ('edicai.grade.entry', 'edicai_grading'),
        ('edicai.semester.result', 'edicai_grading'),
        ('edicai.fee.invoice', 'edicai_fees'),
        ('edicai.attendance.record', 'edicai_attendance'),
        ('edicai.library.issue', 'edicai_library'),
        ('edicai.hostel.allocation', 'edicai_hostel'),
        ('edicai.transport.pass', 'edicai_transport'),
        ('edicai.exam.hall.ticket', 'edicai_exam'),
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student_group = cls.env.ref(
            'edicai_base.group_edicai_student')

    def _model_installed(self, model_name):
        return model_name in self.env

    def _student_rules(self, model_name):
        model_id = self.env['ir.model']._get(model_name).id
        return self.env['ir.rule'].sudo().search([
            ('model_id', '=', model_id),
            ('groups', 'in', self.student_group.ids),
            ('perm_read', '=', True),
        ])

    def test_01_student_self_view_rules_exist(self):
        missing = []
        for model_name, module in self.PORTAL_MODELS:
            if not self._model_installed(model_name):
                continue
            rules = self._student_rules(model_name)
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
        weak = []
        for model_name, module in self.PORTAL_MODELS:
            if not self._model_installed(model_name):
                continue
            rules = self._student_rules(model_name)
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
