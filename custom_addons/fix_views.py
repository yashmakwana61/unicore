import glob
import re

modules = [
    "unicore_progression", "unicore_discipline", "unicore_grievance",
    "unicore_mentor", "unicore_skill_assessment", "unicore_appointment",
    "unicore_secure_transcript", "unicore_digital_library", "unicore_quiz",
    "unicore_placement", "unicore_thesis",
]

avatar_fields = ["student_id", "mentor_id", "supervisor_id", "raised_by_id", "reviewer_id", "faculty_id"]

for mod in modules:
    for filepath in glob.glob(f"{mod}/views/*.xml"):
        with open(filepath) as f:
            content = f.read()

        # Add widget="many2one_avatar" to specific fields if they don't have a widget yet
        for field in avatar_fields:
            content = re.sub(
                fr'<field\s+name="{field}"\s*/>',
                f'<field name="{field}" widget="many2one_avatar"/>',
                content,
            )
            content = re.sub(
                fr'<field\s+name="{field}"\s+invisible="1"\s*/>',
                f'<field name="{field}" invisible="1"/>',  # Skip if invisible
                content,
            )
            content = re.sub(
                fr'<field\s+name="{field}"(?=[^>]*)((?!widget=)[^>]*?)\s*/>',
                f'<field name="{field}"\\1 widget="many2one_avatar"/>',
                content,
            )

        # Replace <field name="..._ids" widget="many2many_tags"/> inside <page> with embedded lists
        # Example: <field name="student_ids" widget="many2many_tags"/>
        content = re.sub(
            r'(<page[^>]*>)\s*<field\s+name="([a-zA-Z0-9_]+_ids)"\s+widget="many2many_tags"\s*/>\s*(</page>)',
            r'\1\n                                <field name="\2">\n                                    <list>\n                                        <field name="display_name"/>\n                                    </list>\n                                </field>\n                            \3',
            content,
        )

        # Adding html widget to large text fields in pages
        content = re.sub(
            r'(<page[^>]*>)\s*<field\s+name="(notes|abstract|description)"\s+placeholder="([^"]*)"\s*/>\s*(</page>)',
            r'\1\n                                <field name="\2" widget="html" placeholder="\3"/>\n                            \4',
            content,
        )
        content = re.sub(
            r'(<page[^>]*>)\s*<field\s+name="(notes|abstract|description)"\s*/>\s*(</page>)',
            r'\1\n                                <field name="\2" widget="html"/>\n                            \3',
            content,
        )

        with open(filepath, "w") as f:
            f.write(content)
