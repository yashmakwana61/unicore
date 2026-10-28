"""Centralised, safe error taxonomy for the conversational AI layer.

Phase 0 — Security Foundation.

The chat surface must never return Python tracebacks, SQL, ORM internals,
filesystem paths, API keys, provider credentials, raw request payloads or
internal security details to a user.  Every conversational failure is
mapped to a deterministic category with a FIXED safe user message; no
exception payload is ever interpolated into the user-facing text.

Full diagnostics stay server-side: callers log the original exception
(``_logger.exception``) and persist a sanitised audit event through
``edicai.ai.audit.event``.
"""

import requests

from odoo.exceptions import AccessError, MissingError, UserError, ValidationError

# NOTE: messages are plain (non-``_()``) strings on purpose — they are
# fixed security texts; import-time ``_()`` would only produce
# translation warnings.  Localisation can wrap these later.

# ---------------------------------------------------------------------
# Deterministic error categories
# ---------------------------------------------------------------------

AUTHORIZATION_DENIED = 'AUTHORIZATION_DENIED'
RECORD_NOT_FOUND = 'RECORD_NOT_FOUND'
VALIDATION_FAILED = 'VALIDATION_FAILED'
TOOL_UNAVAILABLE = 'TOOL_UNAVAILABLE'
LLM_UNAVAILABLE = 'LLM_UNAVAILABLE'
TIMEOUT = 'TIMEOUT'
RATE_LIMITED = 'RATE_LIMITED'
CONFLICT = 'CONFLICT'
INTERNAL_ERROR = 'INTERNAL_ERROR'

#: Fixed, safe user-facing texts.  Nothing dynamic is interpolated here,
#: so no exception payload can ever leak through these strings.
SAFE_MESSAGES = {
    AUTHORIZATION_DENIED: (
        'You do not have access to this information.'),
    RECORD_NOT_FOUND: (
        'That record could not be found.'),
    VALIDATION_FAILED: (
        'Some of the provided details are missing or invalid. '
        'Please check them and try again.'),
    TOOL_UNAVAILABLE: (
        'That capability is not available right now. Please try again later.'),
    LLM_UNAVAILABLE: (
        'AI is temporarily unavailable. Please try again.'),
    TIMEOUT: (
        'The request took too long to complete. Please try again.'),
    RATE_LIMITED: (
        'You are doing that too often. Please wait a moment and try again.'),
    CONFLICT: (
        'That changed since you last viewed it. Please refresh and try again.'),
    INTERNAL_ERROR: (
        'Something went wrong on our side. Please try again. '
        'If it keeps happening, contact your administrator.'),
}

ERROR_CATEGORIES = tuple(sorted(SAFE_MESSAGES))

# Phrases inside provider-raised ``UserError`` strings that identify a
# configuration problem (safe to classify as "service not configured"
# rather than a raw internal failure).
_PROVIDER_CONFIG_PHRASES = (
    'api key', 'not configured', 'configuration', 'configur ', 'endpoint url',
)

# Phrases that identify a transient provider condition.  They map onto the
# existing fixed safe texts — no exception payload is ever interpolated.
_PROVIDER_TIMEOUT_PHRASES = (
    'did not respond in time', 'timed out', 'timeout',
)
_PROVIDER_RATE_LIMIT_PHRASES = (
    'rate limit', 'too many requests',
)
_PROVIDER_UNAVAILABLE_PHRASES = (
    'temporarily unavailable', 'service is down', 'provider is down',
)


def classify_exception(exc):
    """Map an exception to ``(error_code, safe_user_message)``.

    The returned message is ALWAYS one of the fixed ``SAFE_MESSAGES``
    texts (or the fixed "not configured" text).  Callers must still log
    the original exception server-side.
    """
    if isinstance(exc, (requests.exceptions.Timeout, TimeoutError)):
        return TIMEOUT, SAFE_MESSAGES[TIMEOUT]
    if isinstance(exc, requests.exceptions.ConnectionError):
        return LLM_UNAVAILABLE, SAFE_MESSAGES[LLM_UNAVAILABLE]
    if isinstance(exc, requests.exceptions.HTTPError):
        return LLM_UNAVAILABLE, SAFE_MESSAGES[LLM_UNAVAILABLE]
    if isinstance(exc, MissingError):
        return RECORD_NOT_FOUND, SAFE_MESSAGES[RECORD_NOT_FOUND]
    if isinstance(exc, AccessError):
        return AUTHORIZATION_DENIED, SAFE_MESSAGES[AUTHORIZATION_DENIED]
    if isinstance(exc, ValidationError):
        return VALIDATION_FAILED, SAFE_MESSAGES[VALIDATION_FAILED]
    if isinstance(exc, UserError):
        text = str(exc).lower()
        if any(phrase in text for phrase in _PROVIDER_CONFIG_PHRASES):
            return LLM_UNAVAILABLE, (
                'The AI service is not configured. '
                'Please contact your administrator.')
        if any(phrase in text for phrase in _PROVIDER_TIMEOUT_PHRASES):
            return TIMEOUT, SAFE_MESSAGES[TIMEOUT]
        if any(phrase in text for phrase in _PROVIDER_RATE_LIMIT_PHRASES):
            return RATE_LIMITED, SAFE_MESSAGES[RATE_LIMITED]
        if any(phrase in text for phrase in _PROVIDER_UNAVAILABLE_PHRASES):
            return LLM_UNAVAILABLE, SAFE_MESSAGES[LLM_UNAVAILABLE]
        return INTERNAL_ERROR, SAFE_MESSAGES[INTERNAL_ERROR]
    return INTERNAL_ERROR, SAFE_MESSAGES[INTERNAL_ERROR]


def safe_error_payload(error_code):
    """Return a JSON-ready error payload for chat endpoints.

    Always ``{'error': <safe text>, 'error_code': <category>}``.
    Unknown codes degrade to ``INTERNAL_ERROR``.
    """
    if error_code not in SAFE_MESSAGES:
        error_code = INTERNAL_ERROR
    return {
        'error_code': error_code,
        'error': SAFE_MESSAGES[error_code],
    }
