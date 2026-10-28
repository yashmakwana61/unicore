# UNICORE SIS — Manual Test Report + Logical Loopholes
Odoo 19.0, `edicai/custom_addons` (65 modules). Server verified on `:8069`, DB `odoo_crm`.
Method: manifest + models state machines + constrains/SQL + security CSV/XML + controllers.

## 1. Admission → Enrollment (edicai_admission, edicai_student)
Test manually:
- Inquiry → Apply → Docs → Merit → Offer → Fee-pending → Confirm → Student + Enroll wizard → Enrolled → Completed/Cancelled.
- Cycle seats, merit list, entrance test, offer letter, waitlist promotion, drop/re-enroll after deadline.
Loopholes:
- Kanban drag / `write(state)` skips checks (`admission_applicant.py:287-334`). Test: drag inquiry→confirmed, bypasses `action_confirm_admission:404`.
- Re-confirm creates 2nd student, no docs/fee/offer check (`:404-435`). Test: confirm, reset to fee_pending, confirm again.
- No applicant uniqueness; confirmed applicant deletable (access CSV:11). Test: duplicate email/program/cycle; delete confirmed.
- Seat check non-atomic, computed non-stored (`admission_cycle.py:182-207`, `applicant.py:381-390`). Test: 1 seat, 2 concurrent offers.
- `admission.enrollment` pending→completed direct, empty enroll, wizard duplicates (`admission_enrollment.py:107-122`, wizard:239-250). Test: run wizard twice.
- `edicai.enrollment` create-only validation, `write` bypass, `search_count` overbook race, waitlist pos race, `force_enrollment_override` no group check, student has create/write (CSV:36) (`edicai_enrollment.py:336-428`, waitlist:410-413). Test: student RPC create with override; `write(enrollment_state=completed)` post-deadline.
- Drop→re-enroll blocked by UNIQUE(student,course,semester) (`:234-241`). Test: enroll→drop→re-enroll = IntegrityError.
- Student any→any state (`edicai_student.py:517-659`); finance can edit status (CSV:5). Test: admitted→alumni direct; login finance → edit state/CGPA.

## 2. Curriculum / Timetable / Attendance (edicai_curriculum, edicai_timetable, edicai_attendance, edicai_calendar, edicai_campus)
Test: curriculum draft→review→approve→activate→retire; course active→discontinue; offering draft→ongoing→completed; time slots, entries, room bookings, generate sessions, open→close→reopen attendance, face check-in.
Loopholes:
- Curriculum approve skips review, retire/reset from any state (`edicai_curriculum.py:196-236`). Test: draft→approve; active→reset draft with live offerings.
- Course discontinue/reset ignores live offerings (`edicai_course.py:411-427`). Test: discontinue course with active offering.
- Offering start/completion ungated, min_enrollment warning only, max_enrollment reducible below enrolled (`edicai_course_offering.py:298-341`). Test: max 40→5; start with 0 students.
- Overlap check exact `time_slot_id` only; 09:00-10:00 vs 09:30-10:30 both confirm (`timetable_entry.py:229-298`, `room_booking.py:143-187`). Test: same room/day, overlapping different slots.
- Cancel/reset timetable ignores closed attendance sessions (`:342-355`). Test: close sessions → cancel entry.
- Attendance reopen ungated, `force_write_closed_session` no group check (`session.py:360-366`, `record.py:283-293`). Test: reopen closed, edit; RPC with context flag.
- Close with zero marking marks all absent (`:317-358`). Test: open→close immediately.
- Late enrollments get no record; face check-in accepts any registration id (`record.py:305-332`). Test: check-in A with B's face id.
- Session/record uniqueness via `models.Constraint` not `_sql_constraints` — verify DB enforcement under concurrency.
- Holiday overlap warning only (`edicai_holiday.py:129-144`); year activate auto-completes prior (`academic_year.py:287-300`). Test: overlapping holidays; activate second year.

## 3. Exam → Grading → Progression → Transcript (edicai_exam, edicai_grading, edicai_gradebook, edicai_progression, edicai_secure_transcript)
Test: exam schedule, hall tickets, seating, marks entry draft→submitted→verified→published→locked, gradebook apply, promote/repeat/probation/dismiss, transcript issue/verify/revoke.
Loopholes:
- No policy = eligible; pct from single `limit=1` record (`exam_schedule.py:325-352`). Test: delete policy → all eligible.
- Exam date outside semester warning only (`:281-290`). Test: date outside semester saves.
- Exam state jumps, seating overflow silently drops students (`:370-440`). Test: draft→complete; 100 tickets/30 seats → 70 dropped log-only.
- `force_approve` context no group check, `override_approve` any→approved, manual seating no eligibility check (`hall_ticket.py:183-208`, `seating.py:141-170`). Test: seat blocked/ineligible ticket.
- Re-generate skips existing tickets (`:329-334`). Test: attendance drops after generation → ticket stays eligible.
- Verify/lock skip steps, faculty self-verify/publish/lock own entries (CSV:18, rules:40-50) (`grade_entry.py:346-380`). Test: draft→locked as same faculty.
- Reset published→draft re-publishes +credits again, fail resets to registered (`:382-416`). Test: publish→reset→publish = double credits.
- Grade entry for stale/completed enrollment, optional exam link (`:36-99`). Test: prior-year completed enrollment graded now.
- No scale + %>0 = fail with empty letter (`:224-257`). Test: remove scale, enter 85% → fail.
- Gradebook overwrites manual CA, 0-100 weight faculty-editable, roll-up excludes dropped, per-line apply bypasses audit (`config.py:223-377`, `student_line.py:201-293`). Test: hand-enter CA → apply overwrites; weight→100.
- Assignment return→draft→resubmit after grading, late penalty dead (`submission.py:346-432`, `assignment.py:309-315`). Test: grade 4/10 → return → reset → resubmit.
- Quiz single-attempt Python-only, submit no ownership check, tab_switches client-trusted, rule no state limit (`quiz.py:88-117`, CSV:15) . Test: concurrent creates; student A submits B attempt.
- LMS sync adds only, manual, vocab mismatch, no company check (`slide_channel.py:32-51`). Test: drop student → still in channel after re-sync.
- Progression pure manual, snapshots via onchange only, no UNIQUE(student,year), no side effect (`progression_record.py:91-136`). Test: 5 fails → promote; duplicate dismiss; semester unchanged.
- Transcript checks count not quality, hash covers aggregates only, revoke/re-issue keeps old QR, deletable (`transcript.py:82-137`, CSV:2). Test: issue fail/withheld unpublished via RPC; revoke→re-issue old QR still verifies.

## 4. Fees / Payment / Scholarship / Reports (edicai_fees, edicai_payment, edicai_scholarship, edicai_finance_report, edicai_analytics)
Test: fee structure → batch generate → invoice sent → GL move → online pay / legacy pay → reconcile → discount/late fee → cancel/reverse → scholarship apply→approve→award→disburse → snapshots/KPIs/dashboards.
Loopholes:
- UNIQUE(student,semester) bypassed by NULL semester; generator check-then-create races; cancelled blocks re-issue; no company filter (`fee_invoice.py:233-342`). Test: 2 NULL-semester invoices; concurrent generate.
- Overpay guard tautology (`amount > outstanding+amount`), legacy pays invisible to balance, `action_reverse` always crashes (`fee_payment.py:129-188`, `invoice.py:175-200`). Test: double 9999 pay; reverse → ValidationError.
- Discount editable post-GL, GL diverges, `reset_draft` unguarded paid→draft (`invoice.py:125-288`, `gl_ext.py:63-144`). Test: send → edit discount → totals mismatch.
- Batch wizard + hourly cron not idempotent, orphan GL moves; reconcile path calls missing method (`migration.py:99-291`, `gl_ext.py:44`). Test: double-click migrate → 2 moves; reconcile run → AttributeError.
- Cancelled→paid flip via reconcile hook (`status_ext.py:53-54`). Test: cancel posted → trigger reconcile → paid.
- Payment `_post_process` done-only, stored amounts not recomputed, wrong tx ref, duplicate chatter (`transaction_ext.py:28-47`). Test: partial pay stays sent; 2 txs same ref.
- Payment link no payer=student check, token-only auth (`payment_ext.py:83-133`). Test: incognito pay with third-party card.
- Award > invoice, silent `min()` truncation, unlimited stacking, domain UI-only + sudo write (`award.py:123-233`). Test: 20k invoice, 15k+15k awards → 30k disbursed stats.
- Approve skips eligibility/shortlist, deadline advisory, quota race (`application:337-426`). Test: ineligible → approve; past deadline submit.
- Analytics `ROW_NUMBER()` ids unstable, company-only rules leak cross-campus, draft inflates billed, payment report reads legacy only, missing company join (`financial_analytics.py:100-170`, `academic_analytics:183`, rules:1-93). Test: campus-A sees campus-B; draft 1M jumps billed.
- Snapshot NULL-semester dup key + race, scholarship all-time subtracted from single semester, KPI online ~0 (`snapshot.py:154-316`, `kpi.py:214-250`). Test: double daily snapshot; semester net negative.

## 5. Campus life (edicai_hostel, edicai_transport, edicai_library, edicai_digital_library, edicai_appointment, edicai_asset_request, edicai_notice_board)
Test: hostel block→room→allocation→checkin→checkout→maintenance; route→stop→pass→trip + fleet sync; book→copy→member→issue→renew→return→reservation; slots→bookings; asset request; notices.
Loopholes:
- Hostel occupancy counts checked_in only, check on allocated race, cancelled blocks re-alloc via UNIQUE (`room.py:106-118`, `allocation.py:271-391`). Test: 2-bed → 5 allocated → all checkin over capacity.
- Transport no capacity check at all; NULL-semester dup passes (`route.py:119-135`, `vehicle.py:199-206`, `pass.py:204-217`). Test: 40-seat bus → 100 active passes.
- Library double-issue race (create-then-write, UI domain only), no partial unique, ready-reservation doesn't block renew, reservation UNIQUE blocks re-reserve, queue_number race (`issue.py:264-414`, `reservation.py:123-170`). Test: concurrent same-copy issues; renew while ready.
- Appointment confirm non-atomic, only same-student dup blocked (`appointment.py:56-169`). Test: max 1 → 5 drafts → confirm all.
- Room model no overlap/booking (`edicai_room.py:1-134`); UNIQUE as `models.Constraint` — verify DB.
- Notice cross-company portal leak (`portal_student:494-547`, faculty:850, guardian:431) + M2M unconstrained (`notice.py:65-78`). Test: company-B notice visible to A student.
- Digital library `enrolled_only` unenforced, `check_access_rights` no-op (`rules:4-13`, `material.py:38-40`). Test: unenrolled student reads enrolled_only.

## 6. People / portals / integrations (guardian, faculty, mentor, discipline, grievance, leave, placement, alumni, convocation, crm, website, skill, thesis, notify, api, telegram, ai, security)
Test: faculty/staff CRUD, guardian link + portal user, mentor allocation/meetings, misconduct, grievance ticket, leave request, skill assess, thesis+review, placement drive→application, alumni/event sync, convocation/event, lead↔applicant sync, website enquiry, portals (student/faculty/guardian) all routes, notify templates/automation/logs, API health/info/students/academic/notify, telegram intake, AI chat.
Loopholes:
- Guardian company ≠ student company allowed (`rel.py:36-42`, `guardian.py:88-92`). Test: A-guardian + B-student rel reads B data.
- Faculty portal: no `_is_public` guard, marks uncapped to max, criterion forge, status/late_minutes unvalidated (`portal_faculty:61-1302`). Test: POST `internal_9999`, foreign criterion, `status=admin&late=-60`.
- API quota swallowed → 500 + spam (`common.py:145-155`); body-size only on list; `/info` no scope check leaks login+modules (`main.py:31-48`); student reads no company scope → cross-company PII (`students.py:76-250`). Test: notify_only key → `/info` 200; A-key reads B-student.
- Telegram webhook no secret-token check (`telegram/main.py:17-43`). Test: unauth POST processes.
- Institution gating UI-only, detach=True bypass, nullable profile (`menus filter`, `has_feature`). Test: direct create on disabled-module model.
- edicai_crm/website/alumni/convocation bridges: no standalone loopholes beyond parent checks; verify stage-driven applicant sync can't loop lead↔applicant.

## 7. Manual regression checklist (run per release)
1. Applicant cannot skip stages via drag/RPC; duplicates blocked; delete confirmed blocked.
2. Seats atomic under concurrency; waitlist positions unique; student cannot self-enroll with override.
3. Timetable overlapping hours (not just slot id) blocked; cancel blocked with closed sessions.
4. Attendance closed immutable without perm; face id must match student; late enrollee gets record.
5. No exam ticket without policy+attendance+fees; seating never drops silently; re-gen refreshes.
6. Grading maker-checker (verify≠publisher); no double credits; transcript only published-pass + hash covers courses; old QR invalid after revoke.
7. One invoice per student/semester incl. NULL; discount locked post-GL; paid→draft blocked; reverse works.
8. Scholarship ≤ outstanding, one award/semester, eligibility enforced, deadline hard.
9. Hostel/transport/library/appointment caps enforced under concurrency.
10. Portals: student sees own only; guardian only flagged wards same company; faculty only own courses with capped marks; notices company-scoped.
11. API company-scoped + quota 429 + scope on /info; telegram secret required.
