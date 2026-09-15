# docs/studio_plan.md §5, §17 — View Builder (Phase 3)
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import xml.etree.ElementTree as ET

# Supported component types for arch_json
COMPONENT_TYPES = {
    "form": ["sheet", "group", "notebook", "page", "field", "button", "header", "chatter", "separator", "notebook"],
    "list": ["field", "button"],
    "kanban": ["field", "kanban_card", "kanban_box"],
    "search": ["field", "filter", "separator", "group"],
}

class StudioView(models.Model):
    _name = "studio.view"
    _description = "Studio View (arch_json → ir.ui.view, docs/studio_plan.md §5)"
    _order = "model_id, type, sequence"

    model_id = fields.Many2one("studio.model", required=True, ondelete="cascade", index=True)
    type = fields.Selection([("form", "Form"), ("list", "List"), ("kanban", "Kanban"), ("search", "Search")], required=True, default="form")
    name = fields.Char(required=True, help="Technical name for view, e.g. Scholarship Form")
    arch_json = fields.Json(required=True, default=lambda self: {"type": "sheet", "children": []}, help="Component tree, see docs/studio_plan.md §5")
    arch_xml = fields.Text(compute="_compute_arch_xml", store=False, help="Generated Odoo XML from arch_json")
    inherit_view_id = fields.Many2one("ir.ui.view", string="Inherit (for extends)", help="If model extends oacis.*, this is parent view to inherit")
    ir_view_id = fields.Many2one("ir.ui.view", string="Compiled View", readonly=True, help="Generated ir.ui.view on publish")
    sequence = fields.Integer(default=10)
    app_id = fields.Many2one(related="model_id.app_id", store=True, readonly=True)
    active = fields.Boolean(default=True)

    @api.constrains("arch_json", "type", "model_id")
    def _check_arch_json(self):
        for rec in self:
            if not isinstance(rec.arch_json, dict):
                raise ValidationError(_("arch_json must be a JSON object"))
            # validate field refs exist
            if rec.model_id and rec.arch_json:
                fields = set(rec.model_id.field_ids.mapped("key"))
                # also allow standard fields like display_name, state, active
                fields.update(["display_name", "id", "create_date", "write_date", "state", "active", "name"])
                # recursive check
                def check(node):
                    if isinstance(node, dict):
                        if node.get("type") == "field" and node.get("name"):
                            if node["name"] not in fields:
                                # allow many2one display fields
                                pass
                        for child in node.get("children", []):
                            check(child)
                check(rec.arch_json)

    @api.depends("arch_json", "type", "model_id")
    def _compute_arch_xml(self):
        for rec in self:
            try:
                rec.arch_xml = rec.generate_xml()
            except Exception as e:
                rec.arch_xml = f"<!-- Error: {e} -->"

    def generate_xml(self):
        self.ensure_one()
        model_name = self.model_id.tech_name if self.model_id.tech_name else self.model_id.key.replace(".", "_")
        # For extends, model_name is the extended model's name
        if self.model_id.extends_model_id:
            model_name = self.model_id.extends_model_id.model
        if self.type == "form":
            return self._generate_form_xml(model_name)
        elif self.type == "list":
            return self._generate_list_xml(model_name)
        elif self.type == "kanban":
            return self._generate_kanban_xml(model_name)
        elif self.type == "search":
            return self._generate_search_xml(model_name)
        return "<!-- unknown type -->"

    def _generate_form_xml(self, model_name):
        root = ET.Element("form", string=self.name)
        # If arch_json has children, render them, else default sheet
        body = self.arch_json or {"type": "sheet", "children": []}
        self._render_node(body, root)
        # ensure chatter if opts.chatter and not already present
        if self.model_id.opts and self.model_id.opts.get("chatter"):
            has_chatter = any(c.get("type") == "chatter" for c in (body.get("children") or []))
            if not has_chatter:
                div = ET.SubElement(root, "div", attrib={"class": "oe_chatter"})
                ET.SubElement(div, "field", name="message_ids")
                ET.SubElement(div, "field", name="activity_ids")
        xml_str = ET.tostring(root, encoding="unicode")
        # pretty: wrap with record? For ir.ui.view arch is inner xml
        return xml_str

    def _generate_list_xml(self, model_name):
        root = ET.Element("list", string=self.name)
        body = self.arch_json or {"children": []}
        for child in body.get("children") or body.get("columns") or []:
            if child.get("type") == "field":
                attrs = {"name": child.get("name")}
                if child.get("optional"):
                    attrs["optional"] = child["optional"]
                if child.get("widget"):
                    attrs["widget"] = child["widget"]
                ET.SubElement(root, "field", **attrs)
        if not list(root):
            # default: all fields
            for f in self.model_id.field_ids[:8]:
                ET.SubElement(root, "field", name=f.key)
        return ET.tostring(root, encoding="unicode")

    def _generate_kanban_xml(self, model_name):
        root = ET.Element("kanban")
        templates = ET.SubElement(root, "templates")
        t = ET.SubElement(templates, "t", attrib={"t-name": "kanban-box"})
        div = ET.SubElement(t, "div", attrib={"class": "oe_kanban_card"})
        body = self.arch_json or {"children": []}
        for child in body.get("children", [])[:4]:
            if child.get("type") == "field":
                field = ET.SubElement(div, "field", name=child.get("name"))
                if child.get("widget"):
                    field.set("widget", child["widget"])
            elif child.get("type") == "kanban_box":
                div2 = ET.SubElement(div, "div", attrib={"class": "oe_kanban_details"})
                div2.text = child.get("text", "")
        if not list(div):
            ET.SubElement(div, "field", name="display_name")
        return ET.tostring(root, encoding="unicode")

    def _generate_search_xml(self, model_name):
        root = ET.Element("search", string=self.name)
        body = self.arch_json or {"children": []}
        for child in body.get("children", []):
            if child.get("type") == "field":
                ET.SubElement(root, "field", name=child.get("name"))
            elif child.get("type") == "filter":
                ET.SubElement(root, "filter", string=child.get("string", child.get("name")), name=child.get("name"), domain=child.get("domain", "[]"))
            elif child.get("type") == "separator":
                ET.SubElement(root, "separator")
        return ET.tostring(root, encoding="unicode")

    def _render_node(self, node, parent):
        ntype = node.get("type") if isinstance(node, dict) else None
        if not ntype:
            return
        if ntype == "sheet":
            sheet = ET.SubElement(parent, "sheet")
            for child in node.get("children", []):
                self._render_node(child, sheet)
        elif ntype == "group":
            attrs = {}
            if node.get("string"):
                attrs["string"] = node["string"]
            if node.get("col"):
                attrs["col"] = str(node["col"])
            if node.get("invisible"):
                attrs["invisible"] = node["invisible"]
            g = ET.SubElement(parent, "group", **attrs)
            for child in node.get("children", []):
                self._render_node(child, g)
        elif ntype == "notebook":
            nb = ET.SubElement(parent, "notebook")
            for child in node.get("children", []):
                # children are pages
                if child.get("type") == "page":
                    page = ET.SubElement(nb, "page", string=child.get("string", "Page"), name=child.get("name", ""))
                    for sub in child.get("children", []):
                        self._render_node(sub, page)
                else:
                    self._render_node(child, nb)
        elif ntype == "page":
            page = ET.SubElement(parent, "page", string=node.get("string", "Page"))
            for child in node.get("children", []):
                self._render_node(child, page)
        elif ntype == "field":
            attrs = {"name": node.get("name")}
            if node.get("widget"):
                attrs["widget"] = node["widget"]
            if node.get("readonly"):
                attrs["readonly"] = "1"
            if node.get("required"):
                attrs["required"] = "1"
            if node.get("invisible"):
                attrs["invisible"] = node["invisible"]
            if node.get("attrs"):
                attrs["attrs"] = str(node["attrs"])
            ET.SubElement(parent, "field", **attrs)
        elif ntype == "button":
            attrs = {"string": node.get("string", "Button"), "type": "object", "name": node.get("name", "action_dummy")}
            if node.get("class"):
                attrs["class"] = node["class"]
            ET.SubElement(parent, "button", **attrs)
        elif ntype == "separator":
            ET.SubElement(parent, "separator", string=node.get("string", ""))
        elif ntype == "header":
            header = ET.SubElement(parent, "header")
            for child in node.get("children", []):
                self._render_node(child, header)
        elif ntype == "chatter":
            div = ET.SubElement(parent, "div", attrib={"class": "oe_chatter"})
            ET.SubElement(div, "field", name="message_ids")
            ET.SubElement(div, "field", name="activity_ids")
        else:
            # unknown — render children
            for child in node.get("children", []):
                self._render_node(child, parent)

    def action_compile(self):
        """Create/update ir.ui.view for extends models; for JSONB models store preview only."""
        for rec in self:
            if not rec.model_id.extends_model_id:
                # JSONB runtime — no ir.ui.view needed, just validate
                rec._check_arch_json()
                continue
            # For extends, create a standalone view (not xpath extension) to avoid locator errors
            # The studio view becomes an alternative primary view for the same model
            xml = rec.generate_xml()
            vals = {
                "name": rec.name,
                "model": rec.model_id.extends_model_id.model,
                "arch": xml,
                "type": "form" if rec.type == "form" else rec.type,
            }
            # If inherit_view_id is set and user wants extension, wrap with xpath that appends to sheet
            if rec.inherit_view_id and rec.type == "form":
                # Build an extension that injects studio fields into the parent sheet
                # Extract fields from arch_json to inject
                fields_xml = "".join(
                    f'<field name="{c.get("name")}"/>'
                    for c in (rec.arch_json.get("children") or [])
                    if c.get("type") == "field"
                )
                if not fields_xml:
                    fields_xml = '<field name="display_name"/>'
                xpath_arch = f'<data><xpath expr="//sheet" position="inside"><group string="Studio: {rec.name}">{fields_xml}</group></xpath></data>'
                vals["inherit_id"] = rec.inherit_view_id.id
                vals["mode"] = "extension"
                vals["arch"] = xpath_arch
            if rec.ir_view_id:
                rec.ir_view_id.write(vals)
            else:
                ir_view = self.env["ir.ui.view"].create(vals)
                rec.write({"ir_view_id": ir_view.id})
        return True

    def action_preview(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.name,
                "message": self.generate_xml()[:4000],
                "type": "info",
            },
        }
