import json
import logging

from odoo.http import request
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)

MAX_REQUEST_BODY = 64 * 1024  # 64 KB


def _check_body_size():
    """Reject requests with oversized bodies before processing."""
    content_length = request.httprequest.content_length
    if content_length and content_length > MAX_REQUEST_BODY:
        return api_error(
            'Request body exceeds 64 KB limit.',
            'PAYLOAD_TOO_LARGE',
            413,
        )
    return None


def _validate_int_param(value, name, min_val=1, max_val=None):
    """
    Safely parse an integer query parameter.
    Returns (int_value, None) on success.
    Returns (None, error_response) on failure.
    """
    if value is None:
        return None, None
    try:
        int_val = int(str(value).strip())
    except (ValueError, TypeError):
        return None, api_error(
            '%s must be a valid integer.' % name,
            'INVALID_PARAM',
            400,
        )
    if int_val < min_val:
        return None, api_error(
            '%s must be >= %d.' % (name, min_val),
            'INVALID_PARAM',
            400,
        )
    if max_val and int_val > max_val:
        return None, api_error(
            '%s must be <= %d.' % (name, max_val),
            'INVALID_PARAM',
            400,
        )
    return int_val, None


def _validate_str_param(value, name, allowed_values=None, max_length=100):
    """
    Safely validate a string query parameter.
    Returns (str_value, None) on success.
    Returns (None, error_response) on failure.
    """
    if value is None:
        return None, None
    value = str(value).strip()
    if len(value) > max_length:
        return None, api_error(
            '%s exceeds maximum length.' % name,
            'INVALID_PARAM',
            400,
        )
    if allowed_values and value not in allowed_values:
        return None, api_error(
            '%s must be one of: %s' % (name, ', '.join(allowed_values)),
            'INVALID_PARAM',
            400,
        )
    return value, None


def api_response(data, meta=None, code=200):
    body = {'success': True, 'data': data}
    if meta:
        body['meta'] = meta
    return request.make_response(
        json.dumps(body, default=str),
        headers=[('Content-Type', 'application/json')],
        status=code,
    )


def api_error(message, error_code='ERROR', status_code=400):
    return request.make_response(
        json.dumps({
            'success': False,
            'error': message,
            'code': error_code,
        }),
        headers=[('Content-Type', 'application/json')],
        status=status_code,
    )


def validate_api_key(req):
    token = req.httprequest.headers.get('X-UniCore-Key', '')
    if not token:
        return None
    ip_address = req.httprequest.remote_addr or ''
    try:
        ApiKey = req.env['unicore.api.key']
        api_key = ApiKey.sudo().validate_key(token, ip_address)
        return api_key
    except AccessDenied:
        return None


def _require_scope(api_key, required):
    """
    Explicit scope checking with support for old and new scope names.

    Required values:
      'read'    — any key with read capability
      'notify'  — can send notifications
      'write'   — can write/modify data
      'full'    — admin-level access only

    Scope hierarchy (new names):
      read_only    → GET endpoints only
      notify_only  → can only POST /notifications/send
      read_write   → all GET + all POST
      full         → everything unconditionally

    Legacy alias mapping:
      'read'   → read_only
      'write'  → read_write
      'admin'  → full
    """
    scope_map = {
        'read_only': 'read_only',
        'notify_only': 'notify_only',
        'read_write': 'read_write',
        'full': 'full',
        'read': 'read_only',
        'write': 'read_write',
        'admin': 'full',
    }

    scope = scope_map.get(api_key.scope)
    if scope == 'full':
        return True
    if required == 'read':
        return scope in ('read_only', 'notify_only', 'read_write')
    if required == 'notify':
        return scope in ('notify_only', 'read_write')
    if required == 'write':
        return scope == 'read_write'
    if required == 'full':
        return False
    return False


def _safe_call(func, *args, **kwargs):
    """Wrap controller calls to prevent stack trace exposure."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        _logger.error('API error: %s', str(e), exc_info=True)
        return api_error(
            'An unexpected error occurred.',
            'INTERNAL_ERROR',
            500,
        )
