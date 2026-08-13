import os
import re

modules = [
    "oacis_progression", "oacis_discipline", "oacis_grievance",
    "oacis_mentor", "oacis_skill_assessment", "oacis_appointment",
    "oacis_secure_transcript", "oacis_digital_library", "oacis_quiz",
    "oacis_placement", "oacis_thesis",
]

for mod in modules:
    # Update manifest
    manifest_path = os.path.join(mod, "__manifest__.py")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            content = f.read()
        content = content.replace("'application': False", "'application': True")
        content = content.replace('"application": False', '"application": True')
        with open(manifest_path, "w") as f:
            f.write(content)

    # Update menu.xml
    menu_path = os.path.join(mod, "views", "menu.xml")
    if os.path.exists(menu_path):
        with open(menu_path) as f:
            content = f.read()

        # Remove parent from root menus
        content = re.sub(
            r'parent="oacis_student\.menu_oacis_student_root"',
            '',
            content,
        )

        with open(menu_path, "w") as f:
            f.write(content)

print("Menus and manifests updated successfully.")
