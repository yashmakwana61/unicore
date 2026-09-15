import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Default policy: documents and images only. Blocklists are
# dangerous (mime spoofing), so we use an explicit allowlist of
# extensions plus a size ceiling.
DEFAULT_ALLOWED_EXTENSIONS = frozenset({
    'pdf', 'doc', 'docx', 'odt', 'rtf', 'txt',
    'xls', 'xlsx', 'ods', 'csv',
    'ppt', 'pptx', 'odp',
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'heic',
    'zip',
})

DEFAULT_MAX_FILE_MB = 25


class OacisUploadValidator(models.AbstractModel):
    """Shared validation for user-uploaded files arriving through
    portal controllers or RPC writes."""

    _name = 'oacis.upload.validator'
    _description = 'Oacis Upload Validator'

    @api.model
    def validate_upload(
        self,
        filename,
        content,
        allowed_extensions=None,
        max_mb=None,
        field_label=None,
    ):
        """Raise UserError when the upload violates policy.

        :param filename: original client filename
        :param content: raw bytes already read from the stream
        :param allowed_extensions: override the default allowlist
        :param max_mb: override the default size ceiling
        :param field_label: human label used in error messages
        """
        field_label = field_label or _('file')
        if not filename and not content:
            return
        if content is None:
            raise UserError(
                _('Uploaded %s is empty.') % field_label)
        max_bytes = (max_mb or DEFAULT_MAX_FILE_MB) * 1024 * 1024
        if len(content) > max_bytes:
            raise UserError(_(
                '%(label)s is too large. Maximum size is %(limit)s MB.',
            ) % {'label': field_label, 'limit': max_mb})
        extension = ''
        if filename and '.' in filename:
            extension = filename.rsplit('.', 1)[-1].lower().strip()
        allowed = frozenset(
            allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS)
        if not extension or extension not in allowed:
            raise UserError(_(
                '%(label)s has an unsupported type "%(ext)s". '
                'Allowed types: %(allowed)s.',
            ) % {
                'label': field_label,
                'ext': extension or _('unknown'),
                'allowed': ', '.join(sorted(allowed)),
            })
        # Neutralize path traversal / control characters in filenames.
        if any(c in filename for c in ('..', '/', '\\', '\x00')):
            raise UserError(
                _('%s contains an invalid filename.') % field_label)
