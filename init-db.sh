#!/bin/bash
# init-db.sh
# Initializes the Odoo database with the correct module dependency order.

echo "Starting Odoo 19 with empty DB and installing modules in correct dependency order..."

# The calculated correct install order to prevent silent failure during dependency resolution
INSTALL_ORDER="unicore_design,muk_web_chatter,unicore_base,muk_web_dialog,muk_web_colors,muk_web_refresh,muk_web_appsbar,muk_web_group,telegram_odoo_integration,unicore_theme,unicore_security,unicore_ai,muk_web_theme,unicore_campus,unicore_academic_generic,unicore_institution_profile,unicore_academic,unicore_calendar,unicore_student,unicore_placement,unicore_alumni,unicore_convocation,unicore_hostel,unicore_faculty_profile,unicore_quiz,unicore_transport,unicore_thesis,unicore_library,unicore_mentor,unicore_asset_request,unicore_guardian,unicore_discipline,unicore_skill_assessment,unicore_appointment,unicore_curriculum,unicore_transport_fleet,unicore_digital_library,unicore_notice_board,unicore_timetable,unicore_admission,unicore_attendance,unicore_website,unicore_crm,unicore_documents,unicore_exam,unicore_grading,unicore_fees,unicore_progression,unicore_secure_transcript,unicore_scholarship,unicore_notify,unicore_analytics,unicore_finance_report,unicore_assignment,unicore_api,unicore_portal_student,unicore_gradebook,unicore_demo,unicore_payment,unicore_portal_faculty,unicore_portal_guardian,unicore_lms,unicore_grievance,unicore_student_leave"

sudo docker-compose up -d db

# Wait for DB to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 10

echo "Installing modules..."
sudo docker-compose run --rm web odoo -c /etc/odoo/odoo.conf -d postgres -i $INSTALL_ORDER --stop-after-init

echo "Initialization complete. You can now run: sudo docker-compose up -d web"
