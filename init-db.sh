#!/usr/bin/env bash
# init-db.sh — one-shot EDICAI database initialization.
# Installs all EDICAI modules in dependency order, then stops.
#
# Usage:
#   EDICAI_DB_NAME=edicai ./init-db.sh
set -euo pipefail

DB_NAME="${EDICAI_DB_NAME:-edicai}"

echo "Starting Odoo 19 with empty DB and installing modules in correct dependency order..."

# The calculated correct install order to prevent silent failure during dependency resolution.
# NOTE: edicai_demo is intentionally excluded; enable it only for
# demo/staging databases created with demonstration data.
INSTALL_ORDER="muk_web_chatter,edicai_base,muk_web_dialog,muk_web_colors,muk_web_refresh,muk_web_appsbar,muk_web_group,telegram_odoo_integration,edicai_security,edicai_ai,muk_web_theme,edicai_theme,edicai_studio,edicai_campus,edicai_academic_generic,edicai_institution_profile,edicai_academic,edicai_calendar,edicai_student,edicai_placement,edicai_alumni,edicai_convocation,edicai_hostel,edicai_faculty_profile,edicai_quiz,edicai_transport,edicai_thesis,edicai_library,edicai_mentor,edicai_asset_request,edicai_guardian,edicai_discipline,edicai_skill_assessment,edicai_appointment,edicai_curriculum,edicai_transport_fleet,edicai_digital_library,edicai_notice_board,edicai_timetable,edicai_admission,edicai_attendance,edicai_website,edicai_crm,edicai_documents,edicai_exam,edicai_grading,edicai_fees,edicai_admission_fees,edicai_progression,edicai_secure_transcript,edicai_scholarship,edicai_notify,edicai_analytics,edicai_finance_report,edicai_assignment,edicai_api,edicai_portal_student,edicai_gradebook,edicai_payment,edicai_portal_faculty,edicai_portal_guardian,edicai_lms,edicai_grievance,edicai_student_leave"

docker compose up -d db

# Wait for DB to be ready (healthchecked in compose, but poll anyway)
echo "Waiting for PostgreSQL to be ready..."
until docker compose exec -T db pg_isready -U "${EDICAI_DB_USER:-odoo}" >/dev/null 2>&1; do
  sleep 2
done

echo "Installing modules into database '${DB_NAME}'..."
docker compose run --rm --no-deps web \
  odoo -c /etc/odoo/odoo.conf -d "$DB_NAME" -i "$INSTALL_ORDER" --stop-after-init

echo "Initialization complete. You can now run: docker compose up -d web"
