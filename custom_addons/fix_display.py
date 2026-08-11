import os, glob, re

modules = [
    "unicore_progression", "unicore_discipline", "unicore_grievance",
    "unicore_mentor", "unicore_skill_assessment", "unicore_appointment",
    "unicore_secure_transcript", "unicore_digital_library", "unicore_quiz",
    "unicore_placement", "unicore_thesis"
]

for mod in modules:
    for filepath in glob.glob(f"{mod}/models/*.py"):
        with open(filepath, "r") as f:
            content = f.read()
        
        # Replace _rec_name = "display_name" or 'display_name'
        content = re.sub(r"_rec_name\s*=\s*[\"']display_name[\"']", "_rec_name = 'name'", content)
        
        # Replace display_name = fields.Char( to name = fields.Char(
        content = re.sub(r"display_name\s*=\s*fields\.Char\(", "name = fields.Char(", content)
        
        # Replace _compute_display_name to _compute_name
        content = re.sub(r"_compute_display_name", "_compute_name", content)
        
        # Replace rec.display_name =  to rec.name = 
        content = re.sub(r"rec\.display_name\s*=", "rec.name =", content)
        
        with open(filepath, "w") as f:
            f.write(content)

    for filepath in glob.glob(f"{mod}/views/*.xml"):
        with open(filepath, "r") as f:
            content = f.read()
            
        content = content.replace('name="display_name"', 'name="name"')
        
        with open(filepath, "w") as f:
            f.write(content)
