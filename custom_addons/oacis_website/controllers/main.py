from odoo import fields, http
from odoo.http import request


class OacisAdmissionsWebsite(http.Controller):

    def _get_admissions_company(self):
        return request.website.company_id

    def _get_open_cycles(self, company):
        Cycle = request.env['oacis.admission.cycle']
        return Cycle.sudo().search([
            ('state', '=', 'active'),
            ('company_id', '=', company.id),
        ], order='start_date desc, id desc')

    def _get_programs_by_cycle(self, cycles):
        Seat = request.env['oacis.admission.cycle.seat']
        programs_by_cycle = {}
        for cycle in cycles:
            entries = []
            seats = Seat.sudo().search([
                ('cycle_id', '=', cycle.id),
            ], order='program_id')
            for seat in seats:
                entries.append({
                    'program': seat.program_id,
                    'available': seat.available_seats,
                    'apply_url': '/admissions/apply?cycle_id=%d&program_id=%d'
                                 % (cycle.id, seat.program_id.id),
                })
            programs_by_cycle[cycle.id] = entries
        return programs_by_cycle

    @http.route('/admissions/programs', type='http', auth='public',
                website=True)
    def programs(self, **kw):
        company = self._get_admissions_company()
        cycles = self._get_open_cycles(company)
        return request.render('oacis_website.oacis_admissions_programs', {
            'company': company,
            'cycles': cycles,
            'programs_by_cycle': self._get_programs_by_cycle(cycles),
        })

    @http.route('/admissions/apply', type='http', auth='public',
                website=True)
    def apply(self, **kw):
        company = self._get_admissions_company()
        cycles = self._get_open_cycles(company)
        programs_by_cycle = self._get_programs_by_cycle(cycles)
        countries = request.env['res.country'].sudo().search(
            [], order='name')
        values = {
            'company': company,
            'cycles': cycles,
            'programs_by_cycle': programs_by_cycle,
            'countries': countries,
        }
        if request.httprequest.method == 'POST':
            result = self._apply_submit(kw, cycles)
            if not isinstance(result, dict):
                return result
            values.update(result)
        else:
            cycle_id = int(kw.get('cycle_id') or (cycles[:1].id or 0))
            program_id = int(kw.get('program_id') or 0)
            values['errors'] = {}
            values['form'] = {
                'name': '',
                'email': '',
                'mobile': '',
                'gender': '',
                'date_of_birth': '',
                'nationality_id': '',
                'cycle_id': cycle_id,
                'program_id': program_id,
            }
        return request.render('oacis_website.oacis_admissions_apply', values)

    def _apply_submit(self, kw, cycles):
        errors = {}
        name = (kw.get('name') or '').strip()
        email = (kw.get('email') or '').strip()
        mobile = (kw.get('mobile') or '').strip()
        gender = kw.get('gender')
        raw_dob = kw.get('date_of_birth')
        raw_nationality = kw.get('nationality_id')
        cycle_id = int(kw.get('cycle_id') or 0)
        program_id = int(kw.get('program_id') or 0)

        if not name:
            errors['name'] = 'Please enter your full name.'
        if not email:
            errors['email'] = 'Please enter your email address.'
        if not mobile:
            errors['mobile'] = 'Please enter your mobile number.'
        if gender not in ('male', 'female', 'other', 'prefer_not'):
            errors['gender'] = 'Please select your gender.'
        dob = False
        if not raw_dob:
            errors['date_of_birth'] = 'Please enter your date of birth.'
        else:
            dob = fields.Date.from_string(raw_dob)
            if not dob:
                errors['date_of_birth'] = 'Please enter a valid date of birth.'

        company = self._get_admissions_company()
        cycle = cycles.filtered(lambda c: c.id == cycle_id)
        if not cycle:
            errors['cycle_id'] = 'Please choose an open admission cycle.'
        program = False
        if cycle:
            seat = request.env['oacis.admission.cycle.seat'].sudo().search([
                ('cycle_id', '=', cycle.id),
                ('program_id', '=', program_id),
            ], limit=1)
            if not seat:
                errors['program_id'] = 'Please choose a program offered in this cycle.'
            elif seat.available_seats <= 0:
                errors['program_id'] = 'Sorry, all seats for this program are filled.'
            else:
                program = seat.program_id

        form = {
            'name': name,
            'email': email,
            'mobile': mobile,
            'gender': gender or '',
            'date_of_birth': raw_dob or '',
            'nationality_id': raw_nationality or '',
            'cycle_id': cycle_id,
            'program_id': program_id,
        }
        if errors:
            return {'errors': errors, 'form': form}

        nationality_id = int(raw_nationality) if raw_nationality else False
        applicant = request.env['oacis.admission.applicant'].sudo().create({
            'name': name,
            'email': email,
            'mobile': mobile,
            'gender': gender,
            'date_of_birth': dob,
            'nationality_id': nationality_id,
            'cycle_id': cycle.id,
            'campus_id': cycle.campus_id.id,
            'program_id': program.id,
            'company_id': company.id,
            'state': 'inquiry',
        })
        return request.redirect(
            '/admissions/apply/thank-you?application=%s'
            % applicant.application_number)

    @http.route('/admissions/apply/thank-you', type='http', auth='public',
                website=True)
    def apply_thanks(self, application=None, **kw):
        return request.render('oacis_website.oacis_admissions_thank_you', {
            'application': application or '',
        })