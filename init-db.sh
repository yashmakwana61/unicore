#!/bin/bash
# init-db.sh
# Initializes the Odoo database with the correct module dependency order.

echo "Starting Odoo 19 with empty DB and installing modules in correct dependency order..."

# The calculated correct install order to prevent silent failure during dependency resolution
INSTALL_ORDER="oacis_design,muk_web_chatter,oacis_base,muk_web_dialog,muk_web_colors,muk_web_refresh,muk_web_appsbar,muk_web_group,telegram_odoo_integration,oacis_theme,oacis_security,oacis_ai,muk_web_theme,oacis_campus,oacis_academic_generic,oacis_institution_profile,oacis_academic,oacis_calendar,oacis_student,oacis_placement,oacis_alumni,oacis_convocation,oacis_hostel,oacis_faculty_profile,oacis_quiz,oacis_transport,oacis_thesis,oacis_library,oacis_mentor,oacis_asset_request,oacis_guardian,oacis_discipline,oacis_skill_assessment,oacis_appointment,oacis_curriculum,oacis_transport_fleet,oacis_digital_library,oacis_notice_board,oacis_timetable,oacis_admission,oacis_attendance,oacis_website,oacis_crm,oacis_documents,oacis_exam,oacis_grading,oacis_fees,oacis_progression,oacis_secure_transcript,oacis_scholarship,oacis_notify,oacis_analytics,oacis_finance_report,oacis_assignment,oacis_api,oacis_portal_student,oacis_gradebook,oacis_demo,oacis_payment,oacis_portal_faculty,oacis_portal_guardian,oacis_lms,oacis_grievance,oacis_student_leave"

sudo docker-compose up -d db

# Wait for DB to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 10

echo "Installing modules..."
sudo docker-compose run --rm web odoo -c /etc/odoo/odoo.conf -d postgres -i $INSTALL_ORDER --stop-after-init

echo "Initialization complete. You can now run: sudo docker-compose up -d web"
