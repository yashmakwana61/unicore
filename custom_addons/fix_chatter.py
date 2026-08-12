import glob
import re

modules = [
    "unicore_progression", "unicore_discipline", "unicore_grievance",
    "unicore_mentor", "unicore_skill_assessment", "unicore_appointment",
    "unicore_secure_transcript", "unicore_digital_library", "unicore_quiz",
    "unicore_placement", "unicore_thesis",
]

for mod in modules:
    for filepath in glob.glob(f"{mod}/views/*.xml"):
        with open(filepath) as f:
            content = f.read()

        # Replace the entire <div class="oe_chatter">...</div> with <chatter/>
        content = re.sub(
            r'<div\s+class="oe_chatter">\s*<field\s+name="message_follower_ids"\s*/>\s*<field\s+name="activity_ids"\s*/>\s*<field\s+name="message_ids"\s*/>\s*</div>',
            r'<chatter/>',
            content,
        )

        # Also catch any variations with different field orders or missing fields but still in oe_chatter
        content = re.sub(
            r'<div\s+class="oe_chatter">\s*.*?</div>',
            r'<chatter/>',
            content,
            flags=re.DOTALL,
        )

        with open(filepath, "w") as f:
            f.write(content)

print("Chatter fixed!")
