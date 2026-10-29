# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

UPDATE_TYPES = [
    ('new_feature', 'New feature'),
    ('improvement', 'Improvement'),
    ('bugfix', 'Fix'),
    ('service', 'Service announcement'),
]


class EdicaiProductUpdate(models.Model):
    """Edicai product release notes (category A of Recent Updates).

    Published rows are visible to internal Edicai roles within their chosen
    audience groups; drafts stay admin-only (record rules in
    security/edicai_home_rules.xml enforce this; the feed re-filters
    explicitly so the UI stays honest even if a rule changes).
    """
    _name = 'edicai.product.update'
    _description = 'Edicai Home — product update (release note)'
    _order = 'publish_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Title', required=True, translate=True,
                       tracking=True)
    summary = fields.Char(string='Short summary', translate=True)
    body = fields.Html(string='Details', sanitize=True, translate=True)
    update_type = fields.Selection(UPDATE_TYPES, string='Category',
                                   required=True, default='improvement')
    state = fields.Selection(
        [('draft', 'Draft'), ('published', 'Published')],
        string='Status', required=True, default='draft', tracking=True,
        copy=False)
    publish_date = fields.Date(string='Published on', readonly=True,
                               copy=False)
    audience_groups = fields.Many2many(
        'res.groups', string='Visible to groups',
        help='Empty = all internal Edicai users.')
    company_id = fields.Many2one(
        'res.company', string='Institution',
        default=lambda self: self.env.company)

    def action_publish(self):
        self.write({'state': 'published',
                    'publish_date': fields.Date.context_today(self)})

    def action_unpublish(self):
        self.write({'state': 'draft'})

    @api.model
    def _visible_ids(self):
        """Published + audience-filtered ids for the current user."""
        today = fields.Date.context_today(self)
        domain = [('state', '=', 'published'),
                  ('publish_date', '<=', today)]
        recs = self.sudo().search(domain)
        user_gids = set(self.env.user.group_ids.ids)
        out = []
        for r in recs:
            if not r.audience_groups:
                out.append(r.id)
                continue
            # res.groups rows are unreadable for portal-bound roles, so this
            # join runs elevated: it only decides WHICH published ids match —
            # content is still read back under the user env (get_recent_...)
            # and remains protected by the record rule + explicit filters.
            aud_ids = set(r.audience_groups.ids)
            if user_gids & aud_ids:
                out.append(r.id)
        return out

    @api.model
    def get_recent_updates(self, limit=20):
        out = []
        try:
            recs = self.browse(self._visible_ids())
        except Exception:
            _logger.warning('product update feed failed', exc_info=True)
            return []
        for r in recs[:limit]:
            out.append({
                'id': r.id, 'res_model': self._name,
                'title': r.name or '', 'summary': r.summary or '',
                'update_type': r.update_type,
                'date': r.publish_date and str(r.publish_date) or '',
                'kind': 'product',
            })
        out.sort(key=lambda u: u['date'], reverse=True)
        return out


class EdicaiNoticeHomeFeed(models.Model):
    """Extend the standard notice board with an audience-filtered feed for
    the Home (institution announcements — category B)."""
    _inherit = 'edicai.notice'

    AUDIENCE_ROLES = {
        'students': 'edicai_base.group_edicai_student',
        'faculty': 'edicai_base.group_edicai_faculty',
    }

    @api.model
    def _home_feed(self, user, limit=5):
        try:
            return self._feed_impl(user, limit)
        except Exception:
            _logger.warning('notice home feed failed', exc_info=True)
            return []

    def _feed_impl(self, user, limit):
        today = fields.Date.context_today(self)
        audiences = ['all']
        for key, group_xmlid in self.AUDIENCE_ROLES.items():
            if user.has_group(group_xmlid):
                audiences.append(key)
        domain = [
            ('active', '=', True),
            ('audience', 'in', audiences),
            ('publish_date', '<=', today),
        ]
        if 'company_id' in self._fields:
            domain.insert(
                1, ('company_id', 'in',
                    (user.company_ids | user.company_id).ids))
        domain += ['|', ('expiry_date', '=', False),
                   ('expiry_date', '>=', today)]
        rows = []
        for r in self.search(domain, limit=limit * 3):
            rows.append({
                'id': r.id, 'res_model': self._name,
                'title': r.title or '',
                'notice_type': r.notice_type or 'general',
                'pinned': bool(r.pinned),
                'date': r.publish_date and str(r.publish_date) or '',
                'summary': r.plain_body(chars=110),
                'kind': 'notice',
            })
        rows.sort(key=lambda n: (not n['pinned'], n['date']),
                  reverse=True)
        return rows[:limit]

    def plain_body(self, chars=110):
        self.ensure_one()
        text = ' '.join(re.sub(r'<[^>]+>', ' ', self.body or '').split())
        return text[:chars] + ('…' if len(text) > chars else '')
