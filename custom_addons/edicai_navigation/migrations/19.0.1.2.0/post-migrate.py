# -*- coding: utf-8 -*-
"""19.0.1.2.0 — durable post-migration self-heal.

Module upgrades re-import data/menu_workspaces.xml, which resets the
workspace roots to their XML defaults (active=False). When the preview
state is ON, re-apply the enable step so the demo layout survives every
-u cycle without manual wizard interaction.

IMPORTANT: uses the migration runner's OWN cursor (env on `cr`) — opening
a second cursor deadlocks against the rows the re-import transaction holds.
No explicit commit: the runner manages the transaction.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    util = env['navigation.preview.util'].sudo()
    state = util._state()
    if state == 'on':
        res = util.enable_preview()
        _logger.info('edicai_navigation post-migrate re-enable: %s', res)
