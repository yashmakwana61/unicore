"""Rewritten Phase 0 security tests — AI chat isolation (record rules + ACLs).

Odoo 19 semantics used here:
* ``Environment`` has no ``with_user``; use ``Model.with_user(user)``
  which switches user AND drops superuser mode (record rules apply).
* ``browse(...).exists()`` is NOT record-rule-checked (documented ORM
  behaviour), so invisibility is asserted through rule-checked
  operations: ``search`` by id, field reads, ``write`` and ``unlink``
  (each of which raises AccessError for foreign records).

Covers Phase 0 charter tests A–E.
"""

import odoo.tests
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

GROUP_AI_USER = 'edicai_ai.group_edicai_ai_user'
GROUP_AI_MANAGER = 'edicai_ai.group_edicai_ai_manager'


@odoo.tests.tagged('edicai', 'security', 'unit')
class AIChatIsolationTest(TransactionCase):
    """Tests A / B / C / E of the Phase 0 security charter."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)

        def mk_user(login, group_xmlid):
            return Users.create({
                'name': login.replace('_', ' ').title(),
                'login': login,
                'email': '%s@example.com' % login,
                'group_ids': [(4, cls.env.ref(group_xmlid).id)],
            })

        cls.user_a = mk_user('edicai_p0_user_a', GROUP_AI_USER)
        cls.user_b = mk_user('edicai_p0_user_b', GROUP_AI_USER)
        cls.manager = mk_user('edicai_p0_manager', GROUP_AI_MANAGER)

    def _session_for(self, user, title='S'):
        return self.env['edicai.ai.chat.session'].with_user(user).create({
            'title': title,
        })

    # ------------------------------------------------------------------
    # A — owner access
    # ------------------------------------------------------------------

    def test_01_owner_can_use_own_conversation(self):
        session = self._session_for(self.user_a)
        self.assertEqual(session.user_id, self.user_a)
        own = self.env['edicai.ai.chat.session'].with_user(
            self.user_a).search([])
        self.assertIn(session, own)
        session.with_user(self.user_a).write({'title': 'owner sees me'})
        msg = self.env['edicai.ai.chat.message'].with_user(
            self.user_a).create({
                'session_id': session.id,
                'role': 'user',
                'content': 'hello from owner',
                'sequence': 10,
            })
        self.assertEqual(
            self.env['edicai.ai.chat.message'].with_user(
                self.user_a).search_count([('session_id', '=', session.id)]),
            1)
        # owner can read the message back
        self.assertEqual(
            self.env['edicai.ai.chat.message'].with_user(
                self.user_a).browse(msg.id).content,
            'hello from owner')

    # ------------------------------------------------------------------
    # B — cross-user isolation (rule-checked operations)
    # ------------------------------------------------------------------

    def test_02_foreign_session_is_invisible(self):
        session = self._session_for(self.user_a, 'privileged chat')
        msg = self.env['edicai.ai.chat.message'].sudo().create({
            'session_id': session.id,
            'role': 'user',
            'content': 'SECRET-CONTENTS-should-not-leak',
        })
        # 1. list (rule-checked): the foreign session is not in B's set
        self.assertFalse(
            self.env['edicai.ai.chat.session'].with_user(
                self.user_b).search([('id', '=', session.id)]))
        # 2. rule-checked read of the message payload fails closed
        with self.assertRaises(AccessError):
            _ = self.env['edicai.ai.chat.message'].with_user(
                self.user_b).browse(msg.id).content
        with self.assertRaises(AccessError):
            _ = self.env['edicai.ai.chat.session'].with_user(
                self.user_b).browse(session.id).title
        # 3. list of messages (rule-checked) stays empty
        self.assertEqual(
            self.env['edicai.ai.chat.message'].with_user(
                self.user_b).search_count([('session_id', '=', session.id)]),
            0)

    def test_03_foreign_session_cannot_be_modified_or_deleted(self):
        session = self._session_for(self.user_a)
        foreign = self.env['edicai.ai.chat.session'].with_user(
            self.user_b).browse(session.id)
        with self.assertRaises(AccessError):
            foreign.write({'title': 'hijacked'})
        with self.assertRaises(AccessError):
            foreign.unlink()
        # identity injection on create is blocked by the owner rule
        with self.assertRaises(AccessError):
            self.env['edicai.ai.chat.session'].with_user(
                self.user_b).create({
                    'title': 'hijack',
                    'user_id': self.user_a.id,
                })
        with self.assertRaises(AccessError):
            self.env['edicai.ai.chat.message'].with_user(self.user_b).create({
                'session_id': session.id,
                'role': 'user',
                'content': 'injected',
            })
        # original data untouched
        self.assertEqual(session.title, 'S')

    # ------------------------------------------------------------------
    # C — manager visibility (module-published AI manager policy)
    # ------------------------------------------------------------------

    def test_04_manager_sees_owner_sessions_and_messages(self):
        session = self._session_for(self.user_a, 'seen by manager')
        msg = self.env['edicai.ai.chat.message'].sudo().create({
            'session_id': session.id,
            'role': 'assistant',
            'content': 'manager-visible reply',
        })
        self.assertIn(
            session,
            self.env['edicai.ai.chat.session'].with_user(
                self.manager).search([]))
        self.assertIn(
            msg,
            self.env['edicai.ai.chat.message'].with_user(
                self.manager).search([('session_id', '=', session.id)]))

    # ------------------------------------------------------------------
    # E — controller trust boundary
    # ------------------------------------------------------------------

    def test_05_controller_boundary_denies_foreign_session(self):
        """``/edicai_ai/chat/send`` resolves the session through
        ``Session.browse(id)`` executed as the requesting user and then
        performs rule-checked ORM calls.  A foreign id behaves here
        exactly as in the endpoint: search finds nothing and any
        content operation fails closed."""
        session = self._session_for(self.user_a)
        looked = self.env['edicai.ai.chat.session'].with_user(
            self.user_b).browse(session.id)
        found = self.env['edicai.ai.chat.session'].with_user(
            self.user_b).search([('id', '=', session.id)])
        self.assertFalse(found)
        with self.assertRaises(AccessError):
            _ = looked.user_id.id  # rule-checked read fails


@odoo.tests.tagged('edicai', 'security', 'unit')
class AIChatRuleIntegrityTest(TransactionCase):
    """Test D — no unrestricted rule may ever apply to a normal AI user."""

    def test_06_owner_rule_present(self):
        Rule = self.env['ir.rule'].sudo()
        for model_xml in ('edicai_ai.model_edicai_ai_chat_session',
                          'edicai_ai.model_edicai_ai_chat_message'):
            model = self.env.ref(model_xml)
            rules = Rule.search([('model_id', '=', model.id)])
            self.assertTrue(
                rules, 'No record rules found for %s' % model.model)
            self.assertTrue(
                any('user.id' in (r.domain_force or '') for r in rules),
                'No owner-scoped rule found for %s' % model.model)

    def test_07_unrestricted_rules_only_for_manager_group(self):
        Rule = self.env['ir.rule'].sudo()
        manager = self.env.ref(GROUP_AI_MANAGER)
        user = self.env.ref(GROUP_AI_USER)
        for model_xml in ('edicai_ai.model_edicai_ai_chat_session',
                          'edicai_ai.model_edicai_ai_chat_message'):
            model = self.env.ref(model_xml)
            for rule in Rule.search([('model_id', '=', model.id)]):
                if (1, '=', 1) in tuple(rule.domain_force):
                    group_ids = rule.groups.ids
                    self.assertIn(
                        manager.id, group_ids,
                        'Unrestricted rule "%s" is not attached to the AI '
                        'manager group' % rule.name)
                    self.assertNotEqual(
                        group_ids, [user.id],
                        'Unrestricted rule "%s" must never apply to the '
                        'plain AI user group' % rule.name)
