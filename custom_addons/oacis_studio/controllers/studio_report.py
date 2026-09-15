from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class StudioReportController(http.Controller):
    @http.route('/studio/report/<int:report_id>/pdf', type='http', auth='user', methods=['GET'], csrf=False)
    def report_pdf(self, report_id, record_id=None, **kw):
        # Check studio group
        if not request.env.user.has_group('oacis_studio.group_studio_user'):
            return request.not_found()
        report = request.env['studio.report'].sudo().browse(report_id)
        if not report.exists():
            return request.not_found()
        # Resolve record ids: ?record_id=1 or ?ids=1,2,3
        ids = []
        if record_id:
            try: ids = [int(record_id)] 
            except: pass
        elif kw.get('ids'):
            try: ids = [int(x) for x in kw['ids'].split(',') if x.strip()]
            except: pass
        html = report.sudo()._render_html(record_ids=ids or None, sample_limit=1 if not ids else len(ids))
        # Try wkhtmltopdf via ir.actions.report, fallback to HTML as PDF mime
        try:
            # Use Odoo's PDF helper if available
            pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_html(f"oacis_studio.report_{report.key}", report.id)
            # _render_qweb_html returns html, need pdf conversion
            # Try to use _run_wkhtmltopdf
            if hasattr(request.env['ir.actions.report'].sudo(), '_run_wkhtmltopdf'):
                pdf_content = request.env['ir.actions.report'].sudo()._run_wkhtmltopdf([html])
                if isinstance(pdf_content, (list, tuple)):
                    pdf_content = pdf_content[0]
                headers = [('Content-Type', 'application/pdf'), ('Content-Disposition', f'inline; filename="{report.key}.pdf"')]
                return request.make_response(pdf_content, headers=headers)
        except Exception as e:
            _logger.info("Studio PDF fallback HTML: %s", e)
        # Fallback: return HTML with PDF headers (browser print to PDF)
        # For bulk, generate multi-record HTML
        headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Disposition', f'inline; filename="{report.key}.html"')]
        return request.make_response(html, headers=headers)

    @http.route('/studio/dashboard/<int:dashboard_id>/pdf', type='http', auth='user', methods=['GET'], csrf=False)
    def dashboard_pdf(self, dashboard_id, **kw):
        if not request.env.user.has_group('oacis_studio.group_studio_user'):
            return request.not_found()
        dash = request.env['studio.dashboard'].sudo().browse(dashboard_id)
        if not dash.exists():
            return request.not_found()
        # Simple dashboard PDF: HTML table of widgets
        html = f"<html><head><title>{dash.name}</title><style>body{{font-family:Arial;}} .widget{{border:1px solid #e2e8f0; padding:12px; margin:8px; border-radius:6px;}}</style></head><body><h2>{dash.name}</h2><p>{dash.description or ''}</p>"
        layout = dash.layout_json or {}
        for w in layout.get('widgets', []):
            html += f"<div class='widget'><b>{w.get('title','Widget')}</b> — {w.get('type','')} <br/><small>col_span {w.get('col_span',4)}</small></div>"
        html += "</body></html>"
        headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Disposition', f'inline; filename="dashboard_{dash.key or dash.id}.html"')]
        return request.make_response(html, headers=headers)
