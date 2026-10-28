"""Admission FAQ Copilot — scoped AI tool belt (read-only + draft creation only).

Only NEW code lives here; no existing model, view, or core logic is touched.
Wiring contract:

* Read tools (``program_search``, ``seat_availability``, ``docs_checklist``,
  ``fee_structure_quote``) perform ONLY ``search`` / ``search_count`` /
  ``read`` / ``browse`` calls. They never call ``create`` / ``write`` /
  ``unlink`` and never invoke ``action_*`` state-machine methods.
* ``draft_inquiry`` is the SOLE write path. It may ONLY:
  (1) create a ``crm.lead`` inquiry, and
  (2) create an ``edicai.admission.applicant`` DRAFT via the model's existing
  validated ``create()`` (required fields supplied, ``state='inquiry'``).
  It never writes to, or transitions, any existing record.
* Every tool scopes all queries to ``request.env.company`` and returns cited
  ``sources`` (``model`` / ``id`` / ``display_name``) so the counsellor
  prompt can cite-or-say-unknown.
* ``run_tool`` dispatches ONLY names present in ``TOOL_SPECS``.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

TOOL_SPECS = [
    {
        'name': 'program_search',
        'description': (
            'Search active academic programs, optionally filtered by '
            'program level (program_type) and campus. Read-only.'
        ),
        'args': ['level', 'campus', 'query', 'limit'],
        'read_only': True,
    },
    {
        'name': 'seat_availability',
        'description': (
            'Read seat allocation for a cycle + program '
            '(total / reserved / committed / available). Locked read: '
            'no seat row is ever written or locked by this tool.'
        ),
        'args': ['cycle', 'program'],
        'read_only': True,
    },
    {
        'name': 'docs_checklist',
        'description': (
            'Read the applicant document checklist (document categories '
            'of applicant type) for a program. Read-only.'
        ),
        'args': ['program'],
        'read_only': True,
    },
    {
        'name': 'fee_structure_quote',
        'description': (
            'Read the active fee structure / tuition estimate for a '
            'program. Quotes are estimates only. Read-only.'
        ),
        'args': ['program', 'academic_year'],
        'read_only': True,
    },
    {
        'name': 'draft_inquiry',
        'description': (
            'Create a crm.lead inquiry and, when full applicant details '
            'are supplied, a DRAFT applicant (state=inquiry) via the '
            'existing validated create. Never modifies existing records.'
        ),
        'args': [
            'name', 'email', 'mobile', 'gender', 'date_of_birth',
            'cycle', 'program', 'campus', 'notes',
        ],
        'read_only': False,
    },
]

_TOOL_NAMES = {spec['name'] for spec in TOOL_SPECS}


class AdmissionAITools(models.AbstractModel):
    _name = 'edicai.admission.ai.tools'
    _description = 'Admission FAQ Copilot — scoped tools'

    # ------------------------------------------------------------------
    # Dispatcher + shared helpers
    # ------------------------------------------------------------------

    @api.model
    def _company_id(self):
        return self.env.company.id

    @api.model
    def _cite(self, records):
        """Build cite-or-say-unknown sources for a recordset."""
        sources = []
        for rec in records:
            try:
                label = rec.display_name
            except Exception:
                label = rec._name
            sources.append({
                'model': rec._name,
                'id': rec.id,
                'display_name': label,
            })
        return sources

    @api.model
    def run_tool(self, name, **kwargs):
        """Dispatch ONLY to tools declared in TOOL_SPECS."""
        if name not in _TOOL_NAMES:
            raise UserError(_('Unknown copilot tool: %s.') % name)
        handler = getattr(self, '_tool_%s' % name, None)
        if handler is None:
            raise UserError(_('Copilot tool not implemented: %s.') % name)
        return handler(**kwargs)

    # ------------------------------------------------------------------
    # READ tools — search/read/browse only, company-scoped
    # ------------------------------------------------------------------

    @api.model
    def _tool_program_search(self, level=None, campus=None, query=None,
                             limit=10):
        company_id = self._company_id()
        domain = [
            ('company_id', '=', company_id),
            ('program_state', '=', 'active'),
        ]
        if level:
            domain.append(('program_type', '=', level))
        if query:
            # Users commonly search by catalogue code (e.g. BCA), while
            # the display name may be expanded ("Bachelor of Computer
            # Applications"). Keep both alternatives inside the same
            # company/active domain; an unresolved query returns no rows.
            domain += ['|', ('name', 'ilike', query),
                       ('code', 'ilike', query)]
        if campus:
            campuses = self.env['edicai.campus'].search([
                ('company_id', '=', company_id),
                '|', ('name', 'ilike', campus),
                     ('code', '=ilike', campus),
            ], limit=6)
            if not campuses:
                return {'programs': [], 'total_count': 0,
                        'truncated': False, 'sources': []}
            if len(campuses) > 1:
                return {'programs': [], 'total_count': 0,
                        'truncated': False, 'sources': [],
                        'clarify': campuses.mapped('display_name')[:5]}
            domain.append(('campus_ids', 'in', campuses.ids))
        Program = self.env['edicai.program']
        total_count = Program.search_count(domain)
        effective_limit = min(max(int(limit or 10), 1), 25)
        programs = Program.search(domain, limit=effective_limit)
        rows = []
        for program in programs:
            rows.append({
                'id': program.id,
                'name': program.name,
                'code': program.code,
                'level': program.program_type,
                'degree_title': program.degree_title,
                'campuses': program.campus_ids.mapped('display_name'),
                'entry_qualification': program.min_entry_qualification,
                'tuition_per_semester': program.tuition_fee_per_semester,
            })
        return {
            'programs': rows,
            'total_count': total_count,
            'truncated': total_count > len(rows),
            'sources': self._cite(programs),
        }

    @api.model
    def _tool_seat_availability(self, cycle=None, program=None):
        Cycle = self.env['edicai.admission.cycle']
        Seat = self.env['edicai.admission.cycle.seat']
        company_id = self._company_id()
        cycle_rec = False
        if cycle:
            cycle_rec = Cycle.search([
                ('company_id', '=', company_id),
                '|', ('code', '=', cycle), ('name', 'ilike', cycle),
            ], limit=1)
            if not cycle_rec:
                return {
                    'seats': [],
                    'sources': [],
                    'note': _('No admission cycle found for "%s".') % cycle,
                }
        else:
            cycle_rec = Cycle.search([
                ('company_id', '=', company_id),
                ('state', '=', 'active'),
            ], limit=1)
            if not cycle_rec:
                return {
                    'seats': [],
                    'sources': [],
                    'note': _('No active admission cycle.'),
                }
        seat_domain = [
            ('cycle_id', '=', cycle_rec.id),
        ]
        if program:
            program_rec = self.env['edicai.program'].search([
                ('company_id', '=', company_id),
                '|', ('code', '=', program), ('name', 'ilike', program),
            ], limit=1)
            if not program_rec:
                return {
                    'seats': [],
                    'sources': self._cite(cycle_rec),
                    'note': _('No program found for "%s".') % program,
                }
            seat_domain.append(('program_id', '=', program_rec.id))
        # Locked read: plain search/read only — no write, no SELECT FOR UPDATE.
        seats = Seat.search(seat_domain, limit=25)
        rows = [{
            'program': seat.program_id.display_name,
            'total_seats': seat.total_seats,
            'reserved_seats': seat.reserved_seats,
            'committed': seat.committed_count,
            'available_seats': seat.available_seats,
        } for seat in seats]
        return {
            'cycle': cycle_rec.display_name,
            'cycle_state': cycle_rec.state,
            'seats': rows,
            'sources': self._cite(cycle_rec) + self._cite(seats),
        }

    @api.model
    def _tool_docs_checklist(self, program=None):
        company_id = self._company_id()
        Category = self.env['edicai.document.category']
        categories = Category.search([
            ('company_id', '=', company_id),
            ('category_type', '=', 'applicant'),
        ])
        program_rec = False
        entry_qualification = False
        if program:
            program_rec = self.env['edicai.program'].search([
                ('company_id', '=', company_id),
                '|', ('code', '=', program), ('name', 'ilike', program),
            ], limit=1)
            if program_rec:
                entry_qualification = program_rec.min_entry_qualification
        rows = [{
            'category': cat.complete_name or cat.name,
            'description': cat.description,
        } for cat in categories]
        sources = self._cite(categories)
        if program_rec:
            sources += self._cite(program_rec)
        return {
            'program': program_rec.display_name if program_rec else program,
            'entry_qualification': entry_qualification,
            'checklist': rows,
            'sources': sources,
        }

    @api.model
    def _tool_fee_structure_quote(self, program=None, academic_year=None):
        company_id = self._company_id()
        Structure = self.env['edicai.fee.structure']
        domain = [
            ('company_id', '=', company_id),
            ('structure_state', '=', 'active'),
        ]
        program_rec = False
        if program:
            program_rec = self.env['edicai.program'].search([
                ('company_id', '=', company_id),
                '|', ('code', '=', program), ('name', 'ilike', program),
            ], limit=1)
            if not program_rec:
                return {
                    'quotes': [],
                    'sources': [],
                    'note': _('No program found for "%s".') % program,
                }
            domain.append(('program_id', '=', program_rec.id))
        structures = Structure.search(domain, limit=10)
        quotes = []
        for struct in structures:
            quotes.append({
                'structure': struct.name,
                'program': (struct.program_id.display_name
                            if struct.program_id else False),
                'academic_year': (struct.academic_year_id.display_name
                                  if struct.academic_year_id else False),
                'total_amount': struct.total_amount,
                'currency': (struct.currency_id.display_name
                             if struct.currency_id else False),
                'components': [{
                    'name': line.display_name,
                    'amount': line.amount,
                } for line in struct.line_ids],
            })
        sources = self._cite(structures)
        base_tuition = False
        if program_rec:
            base_tuition = program_rec.tuition_fee_per_semester
            sources += self._cite(program_rec)
        return {
            'program': program_rec.display_name if program_rec else program,
            'base_tuition_per_semester': base_tuition,
            'quotes': quotes,
            'disclaimer': _(
                'Estimate only — payable fees are confirmed by the '
                'finance office, not by this assistant.',
            ),
            'sources': sources,
        }

    # ------------------------------------------------------------------
    # WRITE tool — draft creation ONLY (lead + applicant inquiry draft)
    # ------------------------------------------------------------------

    @api.model
    def _tool_draft_inquiry(self, name=None, email=None, mobile=None,
                            gender=None, date_of_birth=None, cycle=None,
                            program=None, campus=None, notes=None):
        """Create a crm.lead inquiry; optionally an applicant DRAFT.

        Applicant creation goes ONLY through the existing validated
        ``edicai.admission.applicant.create()`` with required fields and
        ``state='inquiry'``. No writes / transitions on existing records,
        no ``action_*`` calls.
        """
        company_id = self._company_id()
        if not name or not email:
            raise ValidationError(_(
                'A name and an email are required to draft an inquiry.',
            ))
        lead = self.env['crm.lead'].create({
            'name': _('%s — admission inquiry') % name,
            'contact_name': name,
            'email_from': email,
            'phone': mobile or False,
            'description': notes or False,
            'type': 'lead',
            'company_id': company_id,
        })
        result = {
            'lead_id': lead.id,
            'applicant_id': False,
            'application_number': False,
            'sources': self._cite(lead),
        }
        full_details = all([
            mobile, gender, date_of_birth, cycle, program, campus,
        ])
        if not full_details:
            result['note'] = _(
                'Lead created. Applicant draft skipped: mobile, gender, '
                'date of birth, cycle, program and campus are all required.',
            )
            return result
        cycle_rec = self.env['edicai.admission.cycle'].search([
            ('company_id', '=', company_id),
            '|', ('code', '=', cycle), ('name', 'ilike', cycle),
        ], limit=1)
        program_rec = self.env['edicai.program'].search([
            ('company_id', '=', company_id),
            '|', ('code', '=', program), ('name', 'ilike', program),
        ], limit=1)
        campus_rec = self.env['edicai.campus'].search([
            ('company_id', '=', company_id),
            ('name', 'ilike', campus),
        ], limit=1)
        missing = []
        if not cycle_rec:
            missing.append('cycle:%s' % cycle)
        if not program_rec:
            missing.append('program:%s' % program)
        if not campus_rec:
            missing.append('campus:%s' % campus)
        if missing:
            result['note'] = _('Lead created. Applicant draft skipped: '
                                'unknown %s.') % ', '.join(missing)
            return result
        applicant = self.env['edicai.admission.applicant'].create({
            'name': name,
            'email': email,
            'mobile': mobile,
            'gender': gender,
            'date_of_birth': date_of_birth,
            'cycle_id': cycle_rec.id,
            'program_id': program_rec.id,
            'campus_id': campus_rec.id,
            'state': 'inquiry',
            'company_id': company_id,
        })
        result.update({
            'applicant_id': applicant.id,
            'application_number': applicant.application_number,
            'sources': result['sources'] + self._cite(applicant),
        })
        return result
