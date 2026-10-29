# -*- coding: utf-8 -*-
"""Edicai Home — automated tests (post-install, module-scoped)."""
from odoo import fields
from odoo.tests import common, TransactionCase

ROLE2GROUP = {
    'admin': 'group_edicai_admin',
    'manager': 'group_edicai_manager',
    'registrar': 'group_edicai_registrar',
    'finance': 'group_edicai_finance',
    'faculty': 'group_edicai_faculty',
    'staff': 'group_edicai_staff',
    'student': 'group_edicai_student',
}


def make_user(env, role, tag, group_extra=None):
    """Create an isolated user for a role (each test user is unique).

    NOTE: role student implies base.group_portal, which is exclusive with
    base.group_user — so no base user group is added for students."""
    ref = env.ref
    gids = [ref('edicai_base.%s' % ROLE2GROUP[role]).id]
    if group_extra:
        gids.append(ref(group_extra).id)
    elif role != 'student':
        gids.append(ref('base.group_user').id)
    return env['res.users'].sudo().with_context(
        no_reset_password=True).create({
        'name': 'Home Test %s' % tag,
        'login': 'home_%s_%s' % (role, tag),
        'email': 'home%s@home.test' % tag,
        'group_ids': [(6, 0, gids)],
    })


@common.tagged('post_install', '-at_install')
class TestRoleProfiles(TransactionCase):

    def test_student_profile_excludes_finance_widgets(self):
        user = make_user(self.env, 'student', 'srp1')
        data = self.env['edicai.home.data'].with_user(user).get_home_data()
        keys = [w['key'] for w in data['widgets']]
        self.assertNotIn('fee_collection', keys)
        self.assertNotIn('overdue_alerts', keys)
        self.assertNotIn('admissions_pipeline', keys)
        self.assertNotIn('enrollment_overview', keys)
        self.assertIn('my_attendance', keys)
        self.assertIn('today_classes_student', keys)
        self.assertIn('institution_notices', keys)
        self.assertEqual(data['roles'], ['student'])

    def test_finance_profile_has_finance_not_student_widgets(self):
        user = make_user(self.env, 'finance', 'srp2')
        data = self.env['edicai.home.data'].with_user(user).get_home_data()
        keys = [w['key'] for w in data['widgets']]
        self.assertIn('fee_collection', keys)
        self.assertIn('recent_payments', keys)
        self.assertNotIn('my_attendance', keys)
        self.assertNotIn('today_classes_faculty', keys)

    def test_multi_group_union_deterministic_no_duplicates(self):
        # faculty + finance (both internal; portal/user exclusivity avoided)
        user = make_user(self.env, 'finance', 'srp3')
        faculty_g = self.env.ref('edicai_base.group_edicai_faculty').id
        user.sudo().write({'group_ids': [(4, faculty_g)]})
        data = self.env['edicai.home.data'].with_user(user).get_home_data()
        keys = [w['key'] for w in data['widgets']]
        self.assertEqual(len(keys), len(set(keys)))
        # union of both profiles, without duplicates
        self.assertIn('fee_collection', keys)       # finance widget
        self.assertIn('today_classes_faculty', keys)  # faculty widget
        self.assertNotIn('my_attendance', keys)     # student-only widget
        self.assertIn('institution_notices', keys)  # shared widget

    def test_admin_widgets_include_institution_overview(self):
        user = make_user(self.env, 'admin', 'srp4')
        data = self.env['edicai.home.data'].with_user(user).get_home_data()
        keys = [w['key'] for w in data['widgets']]
        for expected in ['enrollment_overview', 'admissions_pipeline',
                         'fee_collection', 'attendance_overview',
                         'pending_approvals']:
            self.assertIn(expected, keys)


@common.tagged('post_install', '-at_install')
class TestOnboarding(TransactionCase):

    def test_items_seeded_per_role(self):
        admin_user = self.env.ref('base.user_admin')
        payload = self.env['edicai.onboarding.item'].get_role_onboarding(
            admin_user, ['admin'])
        self.assertGreater(len(payload['items']), 0)
        self.assertTrue(all('name' in it for it in payload['items']))

    def test_state_roundtrip_and_ownership(self):
        user = make_user(self.env, 'staff', 'sob1')
        item = self.env['edicai.onboarding.item'].sudo().search(
            [('role', '=', 'staff')], limit=1)
        self.assertTrue(item)
        State = self.env['edicai.onboarding.state'].with_user(user)
        State.set_state(item.id, 'done')
        my = State.search([('item_id', '=', item.id)])
        self.assertEqual(len(my), 1)
        self.assertEqual(my.state, 'done')
        self.assertTrue(my.completed_on)
        State.set_state(item.id, 'skipped')
        self.assertEqual(
            State.search([('item_id', '=', item.id)]).state, 'skipped')
        # other user cannot read foreign rows (record rule scopes their search)
        other = make_user(self.env, 'staff', 'sob2')
        other_state = self.env['edicai.onboarding.state'].with_user(
            other).search([('item_id', '=', item.id)])
        self.assertEqual(other_state, State.browse([]))

    def test_foreign_progress_write_blocked(self):
        user = make_user(self.env, 'staff', 'sob3')
        other = make_user(self.env, 'staff', 'sob4')
        item = self.env['edicai.onboarding.item'].sudo().search(
            [('role', '=', 'staff')], limit=1)
        self.env['edicai.onboarding.state'].with_user(user).set_state(
            item.id, 'done')
        row = self.env['edicai.onboarding.state'].sudo().search(
            [('item_id', '=', item.id)], limit=1)
        with self.assertRaises(Exception):
            row.with_user(other).write({'state': 'todo'})


@common.tagged('post_install', '-at_install')
class TestUpdates(TransactionCase):

    def test_draft_hidden_published_visible(self):
        upd = self.env['edicai.product.update'].sudo().create({
            'name': 'Home Engineer Update',
            'update_type': 'new_feature',
            'summary': 'Testing feed visibility.',
        })
        student = make_user(self.env, 'student', 'sup1')
        feed = self.env['edicai.product.update'].with_user(student)\
            .get_recent_updates()
        self.assertNotIn(upd.id, [u['id'] for u in feed])
        upd.action_publish()
        upd.publish_date = fields.Date.context_today(upd)
        feed = self.env['edicai.product.update'].with_user(student)\
            .get_recent_updates()
        self.assertIn(upd.id, [u['id'] for u in feed])

    def test_audience_restriction(self):
        finance_group = self.env.ref('edicai_base.group_edicai_finance')
        upd = self.env['edicai.product.update'].sudo().create({
            'name': 'Finance-only update',
            'update_type': 'improvement',
        })
        upd.action_publish()
        upd.publish_date = fields.Date.context_today(upd)
        upd.audience_groups = [(6, 0, [finance_group.id])]
        student_feed = self.env['edicai.product.update'].with_user(
            make_user(self.env, 'student', 'sup2')).get_recent_updates()
        self.assertNotIn(upd.id, [u['id'] for u in student_feed])
        finance_feed = self.env['edicai.product.update'].with_user(
            make_user(self.env, 'finance', 'sup3')).get_recent_updates()
        self.assertIn(upd.id, [u['id'] for u in finance_feed])

    def test_notice_audience_feed(self):
        Notice = self.env['edicai.notice'].sudo()
        student_user = make_user(self.env, 'student', 'sup4')
        n_all = Notice.create({
            'title': 'All-hands Town update',
            'body': '<p>Everyone.</p>', 'audience': 'all',
        })
        n_only_stu = Notice.create({
            'title': 'Exam schedule info',
            'body': '<p>Only students.</p>', 'audience': 'students',
        })
        n_only_fac = Notice.create({
            'title': 'Faculty meeting',
            'body': '<p>Only faculty people.</p>', 'audience': 'faculty',
        })
        for n in (n_all, n_only_stu, n_only_fac):
            n.publish_date = fields.Date.context_today(n)
        feed = Notice.with_user(student_user)._home_feed(
            student_user, limit=20)
        titles = [f['title'] for f in feed]
        self.assertIn('All-hands Town update', titles)
        self.assertIn('Exam schedule info', titles)
        self.assertNotIn('Faculty meeting', titles)


@common.tagged('post_install', '-at_install')
class TestLandingWire(TransactionCase):

    def test_action_and_wire_roundtrip(self):
        action = self.env.ref('edicai_home.action_edicai_home')
        self.assertEqual(action.tag, 'edicai_home.home')
        admin = self.env.ref('base.user_admin')
        # post_install hook ran at install in this DB
        self.assertEqual(admin.action_id.id, action.id,
                         'post_init must wire admin landing')
        res = self.env['edicai.home.data'].sudo().restore_home_action()
        self.assertTrue(res['ok'])
        admin.invalidate_recordset(['action_id'])
        self.assertFalse(admin.action_id)
        res2 = self.env['edicai.home.data'].sudo().wire_home_action(
            logins=[admin.login])
        self.assertTrue(res2['ok'])
        admin.invalidate_recordset(['action_id'])
        self.assertEqual(admin.action_id.id, action.id)
