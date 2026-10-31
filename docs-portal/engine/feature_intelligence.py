#!/usr/bin/env python3
"""Static, source-traceable Odoo feature audit; never imports addons or touches databases."""
from __future__ import annotations
import argparse
import ast
import csv
import json
import os
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
ADDONS=ROOT/"custom_addons"
OUT=ROOT/"docs-portal"/"audit"
TYPES={"Char","Text","Html","Integer","Float","Monetary","Boolean","Date","Datetime","Selection","Many2one","One2many","Many2many","Binary","Image","Json","Reference","Many2oneReference","Properties"}

def val(node):
    try: return ast.literal_eval(node)
    except (ValueError,TypeError,SyntaxError,RecursionError): return None

def located(path,lineno,**kwargs):
    try: name=path.relative_to(ROOT).as_posix()
    except ValueError: name=path.as_posix()
    return {"source":name,"line":lineno,**kwargs}

def manifest(path):
    tree=ast.parse(path.read_text(encoding="utf-8-sig"))
    d=val(tree.body[0].value)
    if not isinstance(d,dict): raise ValueError("manifest is not a literal dictionary")
    return d

def python_details(path):
    tree=ast.parse(path.read_text(encoding="utf-8-sig"),filename=str(path))
    result={"models":[],"fields":[],"methods":[]}
    for cls in ast.walk(tree):
        if not isinstance(cls,ast.ClassDef): continue
        attrs={}
        for item in cls.body:
            if isinstance(item,ast.Assign):
                for target in item.targets:
                    if isinstance(target,ast.Name) and target.id in ("_name","_inherit","_description"):
                        attrs[target.id]=val(item.value)
        name=attrs.get("_name")
        inheritance=attrs.get("_inherit")
        if not isinstance(name,str) and not isinstance(inheritance,(str,list,tuple)): continue
        result["models"].append(located(path,cls.lineno,python_class=cls.name,model=name,inherit=inheritance))
        for item in cls.body:
            if isinstance(item,ast.Assign):
                for target in item.targets:
                    if not isinstance(target,ast.Name) or not isinstance(item.value,ast.Call): continue
                    f=item.value.func
                    if not (isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and f.value.id=="fields" and f.attr in TYPES): continue
                    first=val(item.value.args[0]) if item.value.args else None
                    flags={}
                    for k in item.value.keywords:
                        if k.arg in ("required","readonly","store","compute","related","ondelete","string"):
                            v=val(k.value)
                            if isinstance(v,(bool,str,int,float,type(None))): flags[k.arg]=v
                    result["fields"].append(located(path,item.lineno,python_class=cls.name,model=name,field=target.id,kind=f.attr,comodel=first if isinstance(first,str) else None,flags=flags))
            if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)):
                decorators=[d.attr if isinstance(d,ast.Attribute) else d.id for d in item.decorator_list if isinstance(d,(ast.Attribute,ast.Name))]
                if item.name.startswith(("action_","button_")) or "constrains" in decorators or "depends" in decorators:
                    result["methods"].append(located(path,item.lineno,python_class=cls.name,model=name,name=item.name,decorators=decorators))
    return result

def xml_details(path):
    root=ET.parse(path).getroot()
    out={k:[] for k in ("menus","actions","views","groups","rules","reports")}
    for elem in root.iter():
        if elem.tag=="menuitem":
            out["menus"].append(located(path,None,xml_id=elem.get("id"),name=elem.get("name"),parent=elem.get("parent"),action=elem.get("action"),groups=elem.get("groups")))
        if elem.tag=="report":
            out["reports"].append(located(path,None,xml_id=elem.get("id"),name=elem.get("string"),model=elem.get("model")))
        if elem.tag!="record": continue
        typ=elem.get("model","")
        fields={x.get("name"): (x.text or "").strip() or x.get("ref") for x in elem.findall("field") if x.get("name")}
        item=located(path,None,xml_id=elem.get("id"),name=fields.get("name"))
        if typ=="ir.ui.menu":out["menus"].append({**item,"parent":fields.get("parent_id"),"action":fields.get("action")})
        elif typ=="ir.actions.report":
            out["reports"].append({**item,"report_model":fields.get("model")})
            out["actions"].append({**item,"action_type":typ,"model":fields.get("model")})
        elif typ.startswith("ir.actions."):
            out["actions"].append({**item,"action_type":typ,"model":fields.get("res_model")})
        elif typ=="ir.ui.view":
            out["views"].append({**item,"model":fields.get("model"),"inherit":fields.get("inherit_id")})
        elif typ=="ir.rule":
            out["rules"].append({**item,"model":fields.get("model_id"),"groups":fields.get("groups")})
        elif typ=="res.groups":out["groups"].append(item)
    return out

def access_details(path):
    output=[]
    with path.open(encoding="utf-8-sig",newline="") as f:
        for n,row in enumerate(csv.DictReader(f),2):
            if not row:continue
            output.append(located(path,n,xml_id=row.get("id"),name=row.get("name"),model=row.get("model_id:id"),
              group=row.get("group_id:id"),read=row.get("perm_read"),write=row.get("perm_write"),create=row.get("perm_create"),delete=row.get("perm_unlink")))
    return output

def inspect(source=ADDONS):
    modules=[]; warnings=[]
    for mf in sorted(source.glob("*/__manifest__.py")):
        try:d=manifest(mf)
        except (SyntaxError,ValueError,UnicodeError) as e:
            warnings.append(located(mf,None,error=str(e)));continue
        mod=mf.parent
        result={"id":mod.name,"name":str(d.get("name",mod.name)),"version":str(d.get("version","")),
                "summary":str(d.get("summary","")),"depends":[v for v in d.get("depends",[]) if isinstance(v,str)],
                "installable":bool(d.get("installable",True)),"application":bool(d.get("application",False)),
                "manifest":located(mf,1)}
        for k in ("models","fields","methods","menus","actions","views","groups","rules","reports","access"):result[k]=[]
        for f in sorted(mod.rglob("*.py")):
            if f==mf or "tests" in f.relative_to(mod).parts:continue
            try:
                for k,items in python_details(f).items():result[k].extend(items)
            except (SyntaxError,UnicodeError) as e:warnings.append(located(f,None,error=str(e)))
        for f in sorted(mod.rglob("*.xml")):
            try:
                for k,items in xml_details(f).items():result[k].extend(items)
            except (ET.ParseError,UnicodeError) as e:warnings.append(located(f,None,error=str(e)))
        for f in sorted(mod.rglob("ir.model.access.csv")):
            try: result["access"].extend(access_details(f))
            except (csv.Error,UnicodeError) as e:warnings.append(located(f,None,error=str(e)))
        modules.append(result)
    return modules,warnings

def summary(modules,warnings):
    keys=["models","fields","methods","menus","actions","views","groups","rules","reports","access"]
    totals={k:sum(len(m[k]) for m in modules) for k in keys}
    lines=["# Edicai feature intelligence audit","","Static source declarations only; no verified UI or permission behavior.","",
           "Modules: "+str(len(modules))+". Parse warnings: "+str(len(warnings))+".","",
           "| Declared artifact | Count |","|---|---:|"]
    lines.extend("| "+k.title()+" | "+str(totals[k])+" |" for k in keys)
    lines+=["","## Coverage by addon","","| Addon | Models | Fields | Menus | Views | Actions | ACL / rules |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    for m in modules:
        lines.append("| "+m["id"]+" | "+" | ".join(str(len(m[k])) for k in ("models","fields","menus","views","actions"))+" | "+str(len(m["access"])+len(m["rules"]))+" |")
    lines+=["","## Limitations","","- Database-installed modules, dynamic menus and actual role permissions cannot be determined from static files.",
            "- Workflow completion, correctness and screenshots require an isolated demo database.",
            "- Full source inventory and ACL metadata remain internal CI artifacts, not public web pages.",""]
    if warnings:
        lines+=["## Parse warnings",""]
        lines.extend("- "+w["source"]+": "+w["error"][:150] for w in warnings[:70])
    return "\n".join(lines)+"\n",totals

def git_sha():
    if os.environ.get("GITHUB_SHA"):return os.environ["GITHUB_SHA"]
    try:return subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,text=True,capture_output=True,check=True,timeout=4).stdout.strip()
    except (OSError,subprocess.SubprocessError):return "unknown"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,default=OUT)
    p.add_argument("--strict",action="store_true")
    args=p.parse_args()
    modules,warnings=inspect()
    if not modules:raise SystemExit("No addons discovered")
    if args.strict and warnings:raise SystemExit(str(len(warnings))+" parsing warnings")
    args.output.mkdir(parents=True,exist_ok=True)
    document,counts=summary(modules,warnings)
    files={
        "feature-inventory.json":json.dumps({"schema":1,"source_sha":git_sha(),"modules":modules},indent=2,ensure_ascii=False)+"\n",
        "feature-summary.json":json.dumps({"source_sha":git_sha(),"module_count":len(modules),"counts":counts,"warnings":len(warnings)},indent=2)+"\n",
        "parse-warnings.json":json.dumps(warnings,indent=2)+"\n",
        "FEATURE_COVERAGE.md":document}
    for name,contents in files.items():(args.output/name).write_text(contents,encoding="utf-8")
    print("Edicai source modules:",len(modules),"counts:",counts,"warnings:",len(warnings))
if __name__=="__main__":main()
