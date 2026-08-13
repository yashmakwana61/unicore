from odoo import http
from odoo.http import request


class TranscriptVerifyController(http.Controller):

    @http.route('/transcript/verify/<string:hash_code>', type='http', auth='public', website=True)
    def verify_transcript(self, hash_code, **kwargs):
        transcript = request.env['unicore.secure.transcript'].sudo().search([
            ('verification_hash', '=', hash_code),
            ('state', '=', 'issued'),
        ], limit=1)
        values = {
            'transcript': transcript,
            'hash_code': hash_code,
            'verified': bool(transcript),
        }
        return request.render('unicore_secure_transcript.transcript_verify_page', values)
