#!/usr/bin/env python3
"""Deterministic read-only source analysis. Never import or execute Odoo modules."""
import argparse, ast, json, re
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
SITE=Path(__file__).resolve().parents[1]
ADDONS=ROOT/"custom_addons"

def read_manifest(path):
    data=ast.literal_eval(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data,dict): raise ValueError("Manifest must be a dictionary")
    return data

def inspect_python(path):
    try: tree=ast.parse(path.read_text(encoding="utf-8-sig"))
    except (SyntaxError,UnicodeError): return {"models":[],"inherits":[]}
    models=set(); inherits=set()
    for node in ast.walk(tree):
        if not isinstance(node,ast.ClassDef): continue
        for field in node.body:
            if not isinstance(field,ast.Assign): continue
            for target in field.targets:
                if not isinstance(target,ast.Name):continue
                if target.id not in ("_name","_inherit"):continue
                try: val=ast.literal_eval(field.value)
                except (ValueError,SyntaxError,TypeError):continue
                values=[val] if isinstance(val,str) else val if isinstance(val,(list,tuple)) else []
                if target.id=="_name":models.update(v for v in values if isinstance(v,str))
                else:inherits.update(v for v in values if isinstance(v,str))
    return {"models":sorted(models),"inherits":sorted(inherits)}

def scan_xml(path):
    try: root=ET.parse(path).getroot()
    except (ET.ParseError,UnicodeError):return {"menus":[],"actions":[],"groups":[]}
    menus=[];actions=[];groups=[]
    for x in root.iter():
        if x.tag=="menuitem": menus.append(x.get("id"))
        if x.tag!="record":continue
        model=x.get("model") or ""
        if model=="ir.ui.menu":menus.append(x.get("id"))
        if model.startswith("ir.actions."):actions.append(x.get("id"))
        if model=="res.groups":groups.append(x.get("id"))
    return {"menus":[x for x in menus if x],"actions":[x for x in actions if x],"groups":[x for x in groups if x]}

def gather():
    out=[]
    for p in sorted(ADDONS.glob("*/__manifest__.py")):
        d=read_manifest(p); slug=p.parent.name
        models=set();inherits=set();menus=set();actions=set();groups=set()
        for py in p.parent.rglob("*.py"):
            if "tests" in py.parts:continue
            facts=inspect_python(py);models.update(facts["models"]);inherits.update(facts["inherits"])
        for xml in p.parent.rglob("*.xml"):
            facts=scan_xml(xml);menus.update(facts["menus"]);actions.update(facts["actions"]);groups.update(facts["groups"])
        out.append({"slug":slug,"name":str(d.get("name") or slug),"summary":str(d.get("summary") or "Odoo addon"),"version":str(d.get("version") or "unspecified"),"depends":[v for v in d.get("depends",[]) if isinstance(v,str)],"application":bool(d.get("application",False)),"installable":bool(d.get("installable",True)),"models":sorted(models),"inherits":sorted(inherits),"menus":sorted(menus),"actions":sorted(actions),"groups":sorted(groups)})
    return out

def markdown(m,names):
    title=m["name"].replace('"',"'").replace("\n"," ")
    summary=m["summary"].replace("\n"," ")
    deps="\n".join("- [`"+d+"`](./"+d+".md)" if d in names else "- `"+d+"`" for d in m["depends"]) or "No dependencies declared."
    return f"""---
id: {m['slug']}
title: "{title}"
---
# {title}

> **Source-confirmed metadata.** This is not proof that the module is installed or operational.

{summary}

| Property | Declared value |
|---|---|
| Technical name | `{m['slug']}` |
| Version | `{m['version']}` |
| Application flag | {'Yes' if m['application'] else 'No'} |
| Installable | {'Yes' if m['installable'] else 'No'} |

## Dependencies

{deps}

## Static implementation signals

- {len(m['models'])} declared model names
- {len(m['menus'])} XML menu IDs
- {len(m['actions'])} XML action IDs
- {len(m['groups'])} XML security groups

Static counts are approximate and do not indicate successful UI rendering.

## Source and validation

[Manifest](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/{m['slug']}/__manifest__.py).

Detailed role-based workflows and screenshots are pending testing on a safe Odoo demo instance.
"""

def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check",action="store_true")
    mode.add_argument("--write",action="store_true")
    args=parser.parse_args()
    if not ADDONS.is_dir():parser.error("Cannot locate custom_addons")
    modules=gather()
    if not modules:parser.error("No Odoo manifests found")
    folder=SITE/"docs/modules"
    names={x["slug"] for x in modules}
    old={x.stem for x in folder.glob("*.md")}
    if args.check:
        if old!=names:raise SystemExit(f"Module pages mismatch: missing={sorted(names-old)}, extra={sorted(old-names)}")
        print(f"PASS: {len(names)} module pages correspond to available manifests")
        return
    folder.mkdir(parents=True,exist_ok=True)
    for x in modules:(folder/(x["slug"]+".md")).write_text(markdown(x,names),encoding="utf-8")
    dataset=[{"title":x["name"],"description":x["summary"],"path":"/docs/modules/"+x["slug"],"keywords":x["slug"]+" "+" ".join(x["depends"])} for x in modules]
    dataset.append({"title":"Complete Module Catalog","description":"All Clasflow modules","path":"/docs/reference/module-catalog","keywords":"catalog modules"})
    data=SITE/"static/data";data.mkdir(parents=True,exist_ok=True)
    (data/"search-index.json").write_text(json.dumps(dataset,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (data/"source-inventory.json").write_text(json.dumps(modules,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"Generated {len(modules)} source-backed pages and search records")
if __name__=="__main__":main()
