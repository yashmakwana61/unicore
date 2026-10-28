import glob
import re

modules = [
    "edicai_progression", "edicai_discipline", "edicai_grievance",
    "edicai_mentor", "edicai_skill_assessment", "edicai_appointment",
    "edicai_secure_transcript", "edicai_digital_library", "edicai_quiz",
    "edicai_placement", "edicai_thesis",
]

for mod in modules:
    for filepath in glob.glob(f"{mod}/models/*.py"):
        with open(filepath) as f:
            content = f.read()

        # Replace _rec_name = "display_name" or 'display_name'
        content = re.sub(r"_rec_name\s*=\s*[\"']display_name[\"']", "_rec_name = 'name'", content)

        # Replace display_name = fields.Char( to name = fields.Char(
        content = re.sub(r"display_name\s*=\s*fields\.Char\(", "name = fields.Char(", content)

        # Replace _compute_display_name to _compute_name
        content = content.replace(r"_compute_display_name", "_compute_name")

        # Replace rec.display_name =  to rec.name =
        content = re.sub(r"rec\.display_name\s*=", "rec.name =", content)

        with open(filepath, "w") as f:
            f.write(content)

    for filepath in glob.glob(f"{mod}/views/*.xml"):
        with open(filepath) as f:
            content = f.read()

        content = content.replace('name="display_name"', 'name="name"')

        with open(filepath, "w") as f:
            f.write(content)
