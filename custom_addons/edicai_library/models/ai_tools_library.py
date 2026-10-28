"""
Library Buddy Copilot — AI tool layer for edicai_library.

Read-only catalogue/loan helpers plus guarded write path
(reservations only, via validated ``create``).  Record rules are
never bypassed: every ORM call runs as the current user so students
only ever see their own loans (see
security/edicai_library_record_rules.xml).

Guards mirrored from models/edicai_library_issue.py
(``action_renew``) and models/edicai_library_reservation.py
(``_check_availability``):

* renewal is blocked when the issue is not ``issued``, max renewals
  are used, the book is overdue, or another member is waiting
  (active reservation queue);
* a reservation cannot be created while copies are available —
  the librarian must issue directly instead;
* this module NEVER calls ``action_renew`` itself: ``renew_eligibility``
  only returns a draft action for librarian/user confirmation.

Wiring (manual step — existing files are intentionally untouched):

* import this module from ``models/__init__.py``;
* add ``data/ai_copilot_prompts.xml`` to the manifest ``data`` list.
"""

import logging
from datetime import date, timedelta

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# System-prompt storage key (seeded by data/ai_copilot_prompts.xml).
LIBRARIAN_PROMPT_PARAM = 'edicai_library.ai_librarian_prompt'

DEFAULT_SYSTEM_PROMPT = (
    'You are Library Buddy, a librarian assistant for the Edicai '
    'Library. Help users find books, check their loans, explain '
    'renewal eligibility, and request reservations. Always cite the '
    'catalogue (title, accession/ISBN, availability). Never override '
    'the reservation queue, never renew an overdue or reserved book, '
    'and never issue a book that is already issued. Reservation and '
    'renewal actions need librarian/user confirmation.'
)

# Tool registry — maps tool name to spec for the AI orchestrator.
# Follows the edicai_studio ``TOOL_SPECS`` convention.
TOOL_SPECS = {
    'catalogue_search': {
        'desc': (
            'Search the library catalogue (physical books and digital '
            'materials) by title, author and/or subject. Company-scoped, '
            'read-only.'
        ),
        'args': ['title', 'author', 'subject', 'limit'],
        'params': {
            'title': 'Free text matched against the book/material title.',
            'author': 'Free text matched against author names.',
            'subject': 'Free text matched against subject/classification names.',
            'limit': 'Max results per collection (default 10, max 20).',
        },
    },
    'my_loans': {
        'desc': (
            'List the current user\'s library membership(s) and active '
            'loans. Students only see their own records via existing '
            'record rules. Read-only.'
        ),
        'args': ['member_id', 'include_history'],
        'params': {
            'member_id': (
                'Optional member id. Defaults to the current user\'s own '
                'membership(s); librarians may pass another member\'s id.'
            ),
            'include_history': 'Also include returned/lost/cancelled issues.',
        },
    },
    'renew_eligibility': {
        'desc': (
            'Check whether a loan can be renewed (reservation queue, '
            'overdue status, renewal limits, membership standing). '
            'Never renews by itself — returns a draft action for '
            'librarian/user confirmation.'
        ),
        'args': ['issue_id'],
        'params': {
            'issue_id': 'Database id of the edicai.library.issue record.',
        },
    },
    'reserve_request': {
        'desc': (
            'Request a reservation for a book with no available copies. '
            'Creates the reservation via validated create (model '
            'constraints still apply: no reservation while copies are '
            'available, one active reservation per member/book).'
        ),
        'args': ['book_id', 'member_id', 'notes'],
        'params': {
            'book_id': 'Database id of the edicai.library.book record.',
            'member_id': (
                'Optional member id. Defaults to the current user\'s own '
                'membership; librarians may book on behalf of a member.'
            ),
            'notes': 'Optional note stored on the reservation.',
        },
    },
}


class LibraryAICopilot(models.AbstractModel):
    """Library Buddy Copilot — tool-constrained AI helpers."""

    _name = 'library.ai.copilot'
    _description = 'Library Buddy Copilot — AI tool layer'

    # ------------------------------------------------------------------
    # Registry / chat entry
    # ------------------------------------------------------------------

    @api.model
    def get_tool_specs(self):
        """Return the TOOL_SPECS registry for the AI orchestrator."""
        return TOOL_SPECS

    @api.model
    def _get_system_prompt(self):
        prompt = self.env['ir.config_parameter'].sudo().get_param(
            LIBRARIAN_PROMPT_PARAM, default='',
        )
        return prompt or DEFAULT_SYSTEM_PROMPT

    @api.model
    def chat(self, prompt):
        """One-shot question answering with the librarian system prompt.

        Tool execution itself is driven by the caller using
        ``get_tool_specs``; this helper only grounds plain questions.
        """
        if not prompt:
            raise UserError(_('Please provide a question for Library Buddy.'))
        provider = self.env['edicai.ai.provider']
        return provider.generate_text(
            prompt, system_prompt=self._get_system_prompt(),
        )

    # ------------------------------------------------------------------
    # Membership resolution: user -> partner -> member(s)
    # ------------------------------------------------------------------

    @api.model
    def _resolve_my_members(self):
        """Return the current user's library membership(s).

        Chain: ``res.users.partner_id`` -> ``edicai.student`` /
        ``edicai.faculty.member`` (both have ``partner_id``) ->
        ``edicai.library.member`` (``student_id`` / ``faculty_member_id``).
        Runs as the current user, so record rules apply throughout.
        """
        partner = self.env.user.partner_id
        if not partner:
            return self.env['edicai.library.member'].browse()
        students = self.env['edicai.student'].search([
            ('partner_id', '=', partner.id),
        ])
        faculty = self.env['edicai.faculty.member'].search([
            ('partner_id', '=', partner.id),
        ])
        if not students and not faculty:
            return self.env['edicai.library.member'].browse()
        return self.env['edicai.library.member'].search([
            ('company_id', '=', self.env.company.id),
            '|',
            ('student_id', 'in', students.ids),
            ('faculty_member_id', 'in', faculty.ids),
        ])

    @api.model
    def _resolve_member(self, member_id=None):
        """Resolve the target member: explicit id or the user's own.

        An explicit ``member_id`` is browsed as the current user, so a
        student cannot reach another member's record through here.
        """
        if member_id:
            member = self.env['edicai.library.member'].browse(member_id)
            if not member.exists():
                raise UserError(_('Library member #%s not found.') % member_id)
            # Field access enforces read rights under record rules.
            member.display_name  # noqa: B018 - access check
            return member
        members = self._resolve_my_members()
        if not members:
            raise UserError(_(
                'No library membership found for the current user. '
                'Please contact the librarian to register.',
            ))
        if len(members) > 1:
            raise UserError(_(
                'Multiple memberships found (%s). '
                'Please specify member_id explicitly.'
            ) % ', '.join(members.mapped('member_id')))
        return members

    # ------------------------------------------------------------------
    # Tool: catalogue_search
    # ------------------------------------------------------------------

    @api.model
    def catalogue_search(self, title=None, author=None, subject=None,
                         limit=10):
        """Search physical books + digital materials (company-scoped)."""
        try:
            limit = int(limit or 10)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 20))
        company = self.env.company

        book_domain = [
            ('company_id', '=', company.id),
            ('book_state', '=', 'active'),
        ]
        if title:
            book_domain.append(('title', 'ilike', title.strip()))
        if author:
            book_domain.append(
                ('author_ids.name', 'ilike', author.strip()))
        if subject:
            book_domain.append(
                ('subject_ids.name', 'ilike', subject.strip()))

        books = self.env['edicai.library.book'].search(
            book_domain, limit=limit, order='title',
        )
        book_results = [{
            'id': book.id,
            'title': book.title,
            'authors': book.author_display or '',
            'isbn': book.isbn or '',
            'subjects': book.subject_ids.mapped('name'),
            'available_copies': book.available_copies,
            'total_copies': book.total_copies,
            'shelf_location': book.location or '',
            'call_number': book.call_number or '',
        } for book in books]

        material_domain = [('company_id', '=', company.id)]
        if title:
            material_domain.append(('title', 'ilike', title.strip()))
        if author:
            material_domain.append(('author', 'ilike', author.strip()))
        if subject:
            material_domain.append(
                ('subject_id.name', 'ilike', subject.strip()))

        materials = self.env['edicai.digital.material'].search(
            material_domain, limit=limit, order='title',
        )
        material_results = [{
            'id': mat.id,
            'title': mat.title,
            'author': mat.author or '',
            'subject': mat.subject_id.name if mat.subject_id else '',
            'file_type': mat.file_type,
            'access_level': mat.access_level,
        } for mat in materials]

        return {
            'company': company.display_name,
            'books': book_results,
            'digital_materials': material_results,
        }

    # ------------------------------------------------------------------
    # Tool: my_loans
    # ------------------------------------------------------------------

    @api.model
    def _serialize_issue(self, issue):
        return {
            'id': issue.id,
            'issue_number': issue.issue_number,
            'book': issue.book_id.title if issue.book_id else '',
            'accession_number': (
                issue.book_copy_id.accession_number
                if issue.book_copy_id else ''
            ),
            'issue_date': str(issue.issue_date) if issue.issue_date else '',
            'due_date': str(issue.due_date) if issue.due_date else '',
            'days_overdue': issue.days_overdue,
            'is_overdue': issue.is_overdue,
            'fine_amount': issue.fine_amount,
            'renewal_count': issue.renewal_count,
            'max_renewals': issue.max_renewals,
            'issue_state': issue.issue_state,
        }

    @api.model
    def my_loans(self, member_id=None, include_history=False):
        """List membership(s) + loans for the current user (or one member)."""
        member = self._resolve_member(member_id=member_id)
        domain = [('member_id', '=', member.id)]
        if not include_history:
            domain.append(('issue_state', '=', 'issued'))
        # Record rules apply: students only ever see their own issues.
        issues = self.env['edicai.library.issue'].search(
            domain, order='due_date asc',
        )
        return {
            'member': {
                'id': member.id,
                'member_id': member.member_id,
                'display_name': member.display_name,
                'member_state': member.member_state,
                'current_issue_count': member.current_issue_count,
                'outstanding_fines': member.outstanding_fines,
            },
            'issues': [self._serialize_issue(i) for i in issues],
        }

    # ------------------------------------------------------------------
    # Tool: renew_eligibility (check only — never renews)
    # ------------------------------------------------------------------

    @api.model
    def renew_eligibility(self, issue_id):
        """Evaluate renewal guards; return a draft action, never renew.

        Mirrors the guards in ``edicai.library.issue.action_renew`` plus
        membership standing.  The caller (librarian/user) must confirm
        before invoking ``action_renew`` through the normal UI/action.
        """
        try:
            issue_id = int(issue_id)
        except (TypeError, ValueError):
            raise UserError(_('Invalid issue id: %r.') % (issue_id,))
        issue = self.env['edicai.library.issue'].browse(issue_id)
        if not issue.exists():
            raise UserError(_('Loan #%s not found.') % issue_id)
        # Touch a stored field so record rules / access rights raise
        # AccessError here for records the user may not see.
        issue.display_name  # noqa: B018 - access check

        Reservation = self.env['edicai.library.reservation']
        active_queue = Reservation.search([
            ('book_id', '=', issue.book_id.id),
            ('reservation_state', '=', 'active'),
        ], order='queue_number asc') if issue.book_id else Reservation
        ready_count = Reservation.search_count([
            ('book_id', '=', issue.book_id.id),
            ('reservation_state', '=', 'ready'),
        ]) if issue.book_id else 0

        reasons = []
        if issue.issue_state != 'issued':
            reasons.append(
                _('Only issued books can be renewed (state: %s).')
                % issue.issue_state,
            )
        if issue.renewal_count >= issue.max_renewals:
            reasons.append(
                _('Maximum renewals (%d) already reached.')
                % issue.max_renewals,
            )
        if issue.is_overdue:
            reasons.append(
                _('Book is overdue by %d day(s). Return and settle the '
                  'fine of %s first.') % (
                    issue.days_overdue, issue.fine_amount),
            )
        if active_queue:
            reasons.append(
                _('%d member(s) waiting in the reservation queue; '
                  'renewal would skip the queue.') % len(active_queue),
            )
        member = issue.member_id
        if member and (
                member.member_state != 'active' or member.is_expired):
            reasons.append(
                _('Membership is not in good standing (state: %s).')
                % member.member_state,
            )

        eligible = not reasons
        proposed_action = None
        if eligible:
            preview_due = date.today() + timedelta(
                days=member.loan_period_days if member else 14,
            )
            proposed_action = {
                'action': 'confirm_renewal',
                'model': 'edicai.library.issue',
                'method': 'action_renew',
                'ids': [issue.id],
                'preview_new_due_date': str(preview_due),
                'note': _(
                    'Draft only — requires librarian/user confirmation. '
                    'Confirm via the Renew button on the loan form.'),
            }

        return {
            'eligible': eligible,
            'reasons': reasons,
            'issue': self._serialize_issue(issue),
            'reservation_queue': {
                'active_count': len(active_queue),
                'ready_count': ready_count,
                'waiting_members': [
                    {
                        'queue_number': res.queue_number,
                        'member': res.member_id.display_name,
                    } for res in active_queue[:5]
                ],
            },
            'proposed_action': proposed_action,
        }

    # ------------------------------------------------------------------
    # Tool: reserve_request (validated create only)
    # ------------------------------------------------------------------

    @api.model
    def reserve_request(self, book_id, member_id=None, notes=None):
        """Create a reservation through the model's validated create.

        All model constraints still apply (no available copies, one
        active reservation per member/book, queue numbering).  Raises
        UserError with a clear message for the common guard cases.
        """
        try:
            book_id = int(book_id)
        except (TypeError, ValueError):
            raise UserError(_('Invalid book id: %r.') % (book_id,))
        book = self.env['edicai.library.book'].browse(book_id)
        if not book.exists():
            raise UserError(_('Book #%s not found.') % book_id)
        book.title  # noqa: B018 - access check under record rules
        if book.company_id != self.env.company:
            raise UserError(_(
                'Book "%s" belongs to another institution.') % book.title)
        if book.book_state != 'active':
            raise UserError(_(
                'Book "%s" is not available for reservation (state: %s).')
                % (book.title, book.book_state))

        member = self._resolve_member(member_id=member_id)
        if member.company_id != book.company_id:
            raise UserError(_(
                'Member %s does not belong to the book\'s institution.')
                % member.display_name)
        if member.member_state != 'active' or member.is_expired:
            raise UserError(_(
                'Member %s is not in good standing (state: %s); '
                'reservation not allowed.')
                % (member.display_name, member.member_state))

        Reservation = self.env['edicai.library.reservation']
        if book.available_copies > 0:
            raise UserError(_(
                'Book "%s" has %d available copie(s). Please issue '
                'directly instead of reserving.')
                % (book.title, book.available_copies))
        duplicate = Reservation.search([
            ('book_id', '=', book.id),
            ('member_id', '=', member.id),
            ('reservation_state', 'in', ['active', 'ready']),
        ], limit=1)
        if duplicate:
            raise UserError(_(
                'Member %s already has %s waiting for "%s".')
                % (member.display_name,
                   duplicate.reservation_number or _('a reservation'),
                   book.title))

        # Validated create: sequence, expiry, queue numbering and the
        # no-available-copies constraint all run inside the model.
        reservation = Reservation.create({
            'member_id': member.id,
            'book_id': book.id,
            'company_id': book.company_id.id,
            'notes': notes or _('Created by Library Buddy Copilot.'),
        })
        _logger.info(
            'Library Buddy: reservation %s created for book %s / member %s',
            reservation.reservation_number, book.title,
            member.display_name,
        )
        return {
            'reservation_id': reservation.id,
            'reservation_number': reservation.reservation_number,
            'queue_number': reservation.queue_number,
            'reservation_state': reservation.reservation_state,
            'expiry_date': str(reservation.expiry_date)
            if reservation.expiry_date else '',
            'book': book.title,
            'member': member.display_name,
        }

    @api.model
    def check_tool_access(self, tool_name):
        """Gate copilot write tools behind the library portal/staff groups.

        Read tools (catalogue_search, my_loans, renew_eligibility) rely
        on record rules alone; reserve_request additionally requires the
        caller to have create rights on reservations, which students
        lack by default — librarians act on their behalf.
        """
        if tool_name not in TOOL_SPECS:
            raise UserError(_('Unknown copilot tool: %s.') % tool_name)
        if tool_name == 'reserve_request':
            if not self.env['edicai.library.reservation'].check_access(
                    'create', raise_exception=False):
                raise AccessError(_(
                    'You are not allowed to create reservations. '
                    'Please ask a librarian.'))
        return True
