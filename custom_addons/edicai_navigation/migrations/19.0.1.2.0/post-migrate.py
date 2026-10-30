# -*- coding: utf-8 -*-
"""19.0.1.2.0 — durable post-migration self-heal.

Module upgrades re-import data/menu_workspaces.xml, which resets the
workspace roots to their XML defaults (active=False). When the preview
state is ON, re-apply the enable step so the demo layout survives every
-u cycle without manual wizard interaction.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = None  # placeholder for tooling readability
    # Odoo wraps migrate() with an env attribute in modern versions:
    # (cr, version) signature keeps compatibility with the runner.
    # We re-open through the registry cursor's environments entrypoint.
    from odoo.api import Environment
    from odoo.modules.registry import Registry

    registry = Registry(cr.dbname)
    with registry.cursor() as cur:
        env = Environment(cur, 1, {})
        util = env['navigation.preview.util'].sudo()
        state = util._state()
        if state == 'on':
            res = util.enable_preview()
            _logger.info('edicai_navigation post-migrate re-enable: %s', res)
        cur.commit()
