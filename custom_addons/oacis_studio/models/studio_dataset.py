# docs/studio_plan.md §9
from odoo import fields, models

class StudioDataset(models.Model):
    _name = "studio.dataset"
    _description = "Studio Dataset (semantic query over oacis_* , docs/studio_plan.md §9)"
    _order = "app_id, key"

    app_id = fields.Many2one("studio.app", required=True, ondelete="cascade", index=True)
    key = fields.Char(required=True, help="Semantic key e.g. ds_grade_report")
    label = fields.Char(required=True)
    source_model = fields.Char(required=True, help="e.g. oacis.student, x_scholarship_application")
    joins = fields.Json(default=list, help="[{'path':'student_id','model':'oacis.student'}]")
    fields_json = fields.Json(default=list, help="['display_name','grade_ids.marks']")
    domain_json = fields.Json(default=list, help="Domain with variables, e.g. [['campus_id','in',user.campus_ids]]")
    group_by = fields.Json(default=list)
    aggregations = fields.Json(default=dict, help="{'total': 'sum:amount', 'avg': 'avg:marks'}")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("app_key_uniq", "unique(app_id, key)", "Dataset key must be unique per app"),
    ]
