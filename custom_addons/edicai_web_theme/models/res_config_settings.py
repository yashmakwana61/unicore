"""Res.Config.Settings hook that stores the color scheme.

The value is persisted through the standard ``config_parameter``
mechanism, so no extra tables / privileged fields are introduced.  The
scheme is a pure presentation preference and never gates permissions.
"""

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    edicai_color_scheme = fields.Selection(
        [('light', 'Light'), ('dark', 'Dark')],
        string='Color Scheme',
        default='light',
        help='Applies the Light or Dark UI across the whole back-end. '
             'Saved as the "edicai.web.color_scheme" system parameter; '
             'presentation only — it never affects permissions.',
        config_parameter='edicai.web.color_scheme',
    )
