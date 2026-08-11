import os, glob, re

modules = [
    "unicore_progression", "unicore_discipline", "unicore_grievance",
    "unicore_mentor", "unicore_skill_assessment", "unicore_appointment",
    "unicore_secure_transcript", "unicore_digital_library", "unicore_quiz",
    "unicore_placement", "unicore_thesis"
]

for mod in modules:
    # Update manifest
    manifest_path = os.path.join(mod, "__manifest__.py")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            content = f.read()
        content = content.replace("'application': False", "'application': True")
        content = content.replace('"application": False', '"application": True')
        with open(manifest_path, "w") as f:
            f.write(content)
            
    # Update menu.xml
    menu_path = os.path.join(mod, "views", "menu.xml")
    if os.path.exists(menu_path):
        with open(menu_path, "r") as f:
            content = f.read()
        
        # Remove parent from root menus
        content = re.sub(
            r'parent="unicore_student\.menu_unicore_student_root"', 
            '', 
            content
        )
        
        with open(menu_path, "w") as f:
            f.write(content)

print("Menus and manifests updated successfully.")
