import os
import re

modules = [
    "edicai_progression", "edicai_discipline", "edicai_grievance",
    "edicai_mentor", "edicai_skill_assessment", "edicai_appointment",
    "edicai_secure_transcript", "edicai_digital_library", "edicai_quiz",
    "edicai_placement", "edicai_thesis",
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
            r'parent="edicai_student\.menu_edicai_student_root"',
            '',
            content,
        )

        with open(menu_path, "w") as f:
            f.write(content)

print("Menus and manifests updated successfully.")
