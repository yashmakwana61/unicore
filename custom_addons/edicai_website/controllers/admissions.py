from datetime import date

from odoo import _, fields, http
from odoo.http import request


class AdmissionsWebsite(http.Controller):

    def _form_values(self, error=None, submitted=None):
        company = request.website.company_id
        cycles = request.env['edicai.admission.cycle'].sudo().search([
            ('company_id', '=', company.id),
            ('state', '=', 'active'),
        ], order='start_date desc, id desc')
        programs = cycles.mapped('seat_ids.program_id').filtered(
            lambda program: program.program_state == 'active'
        )
        grade_levels = request.env['edicai.academic.unit'].sudo().search([
            ('company_id', '=', company.id),
            ('unit_type_id.code', '=', 'GRADE'),
        ], order='name')
        return {
            'company': company,
            'cycles': cycles,
            'programs': programs,
            'grade_levels': grade_levels,
            'genders': [
                ('female', _('Female')),
                ('male', _('Male')),
                ('other', _('Other')),
                ('prefer_not', _('Prefer not to say')),
            ],
            'error': error,
            'submitted': submitted or {},
        }

    @http.route(
        '/admissions/apply',
        type='http',
        auth='public',
        website=True,
        sitemap=True,
    )
    def admission_application(self, **kwargs):
        return request.render(
            'edicai_website.admission_application_form',
            self._form_values(),
        )

    @http.route(
        '/admissions/apply/submit',
        type='http',
        auth='public',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def admission_application_submit(self, **post):
        submitted = {
            key: (post.get(key) or '').strip()
            for key in (
                'name', 'email', 'mobile', 'date_of_birth',
                'gender', 'cycle_id', 'program_id', 'grade_level_id',
                'guardian_name', 'guardian_relation', 'guardian_mobile',
                'guardian_email',
            )
        }
        values = self._form_values(submitted=submitted)

        if post.get('website'):
            values['error'] = _('Unable to submit the application. Please try again.')
            return request.render(
                'edicai_website.admission_application_form', values
            )

        required_fields = (
            'name', 'email', 'mobile', 'date_of_birth', 'gender',
            'cycle_id', 'program_id',
        )
        if any(not submitted[field] for field in required_fields):
            values['error'] = _('Please complete all required fields.')
            return request.render(
                'edicai_website.admission_application_form', values
            )

        try:
            cycle_id = int(submitted['cycle_id'])
            program_id = int(submitted['program_id'])
            dob = fields.Date.to_date(submitted['date_of_birth'])
        except (TypeError, ValueError):
            cycle_id = program_id = 0
            dob = False

        cycle = values['cycles'].filtered(lambda record: record.id == cycle_id)
        program = values['programs'].filtered(
            lambda record: record.id == program_id
        )
        seat = request.env['edicai.admission.cycle.seat'].sudo().search([
            ('cycle_id', '=', cycle_id),
            ('program_id', '=', program_id),
        ], limit=1)
        if (not cycle or not program or not seat or not dob
                or dob >= date.today()
                or program.company_id != values['company']
                or cycle.campus_id.company_id != values['company']):
            values['error'] = _(
                'Please choose a valid active admission cycle and class, '
                'and enter a valid date of birth.'
            )
            return request.render(
                'edicai_website.admission_application_form', values
            )

        if submitted['gender'] not in dict(values['genders']):
            values['error'] = _('Please select a valid gender option.')
            return request.render(
                'edicai_website.admission_application_form', values
            )

        grade_level = request.env['edicai.academic.unit'].sudo().browse()
        if submitted['grade_level_id']:
            try:
                grade_id = int(submitted['grade_level_id'])
            except ValueError:
                grade_id = 0
            grade_level = values['grade_levels'].filtered(
                lambda record: record.id == grade_id
            )
        if (program.cohort_kind == 'grade_batch'
                and (not grade_level
                     or (program.academic_unit_id
                         and program.academic_unit_id != grade_level))):
            values['error'] = _(
                'Select the grade level for the chosen class.'
            )
            return request.render(
                'edicai_website.admission_application_form', values
            )

        email = submitted['email'].lower()
        if ('@' not in email or email.startswith('@') or email.endswith('@')
                or any(character.isspace() for character in email)):
            values['error'] = _('Enter a valid email address.')
            return request.render(
                'edicai_website.admission_application_form', values
            )
        guardian_email = submitted['guardian_email'].lower()
        if guardian_email and (
                '@' not in guardian_email
                or guardian_email.startswith('@')
                or guardian_email.endswith('@')
                or any(character.isspace() for character in guardian_email)):
            values['error'] = _('Enter a valid guardian email address.')
            return request.render(
                'edicai_website.admission_application_form', values
            )
        Applicant = request.env['edicai.admission.applicant'].sudo()
        if Applicant.search_count([
            ('email', '=ilike', email),
            ('cycle_id', '=', cycle.id),
            ('program_id', '=', program.id),
            ('company_id', '=', values['company'].id),
        ]):
            values['error'] = _(
                'An application for this email and class has already been received.'
            )
            return request.render(
                'edicai_website.admission_application_form', values
            )

        applicant = Applicant.create({
            'name': submitted['name'],
            'email': email,
            'mobile': submitted['mobile'],
            'date_of_birth': dob,
            'gender': submitted['gender'],
            'cycle_id': cycle.id,
            'campus_id': cycle.campus_id.id,
            'program_id': program.id,
            'grade_level_id': grade_level.id or False,
            'guardian_name': submitted['guardian_name'],
            'guardian_relation': submitted['guardian_relation'],
            'guardian_mobile': submitted['guardian_mobile'],
            'guardian_email': guardian_email,
            'company_id': values['company'].id,
            'state': 'inquiry',
        })
        return request.render(
            'edicai_website.admission_application_thank_you',
            {
                'company': values['company'],
                'application_number': applicant.application_number,
            },
        )
