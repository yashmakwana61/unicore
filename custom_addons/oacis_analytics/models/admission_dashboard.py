import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AdmissionApplicantDashboard(models.Model):
    """Extend admission applicant with dashboard aggregation method."""
    _inherit = 'unicore.admission.applicant'

    @api.model
    def get_admission_dashboard_data(self, domain=None):
        """
        Aggregate admission data for dashboard.
        Returns KPI cards, funnel, and breakdown data.
        All aggregation is server-side via read_group.
        """
        if domain is None:
            domain = []

        data = {}

        # ============================================================
        # KPI CARDS
        # ============================================================

        # Total applicants in current filter scope
        total = self.search_count(domain)
        data['total_applicants'] = total

        # Count by state (all states for reference)
        state_counts = self.read_group(
            domain,
            fields=['state'],
            groupby=['state'],
        )
        state_map = {item['state']: item['state_count'] for item in state_counts}

        # Funnel progression stages (in order)
        funnel_states = [
            'inquiry', 'applied', 'documents_pending', 'under_review',
            'shortlisted', 'entrance_scheduled', 'merit_listed',
            'offer_sent', 'fee_pending', 'confirmed',
        ]
        funnel = []
        for state in funnel_states:
            count = state_map.get(state, 0)
            funnel.append({'state': state, 'label': self._format_state(state), 'count': count})
        data['funnel'] = funnel

        # Exit metrics (not part of linear progression)
        data['rejected'] = state_map.get('rejected', 0)
        data['withdrawn'] = state_map.get('withdrawn', 0)
        data['waitlisted'] = state_map.get('waitlisted', 0)

        # Confirmed (admitted)
        data['confirmed'] = state_map.get('confirmed', 0)

        # Admission rate (reuse VIEW definition: confirmed / total * 100)
        data['admission_rate'] = (
            round((data['confirmed'] / total * 100), 1) if total > 0 else 0
        )

        # Pending decisions: count in mid-pipeline awaiting action
        pending_states = ['under_review', 'shortlisted', 'offer_sent', 'fee_pending']
        data['pending_decisions'] = sum(
            state_map.get(state, 0) for state in pending_states
        )

        # Key conversion rates (reusing VIEW logic)
        shortlisted_count = sum(
            state_map.get(s, 0) for s in [
                'shortlisted', 'merit_listed', 'offer_sent',
                'fee_pending', 'confirmed',
            ]
        )
        data['shortlist_rate'] = (
            round((shortlisted_count / total * 100), 1) if total > 0 else 0
        )

        offer_sent_count = sum(
            state_map.get(s, 0) for s in ['offer_sent', 'fee_pending', 'confirmed']
        )
        data['offer_conversion_rate'] = (
            round((data['confirmed'] / offer_sent_count * 100), 1)
            if offer_sent_count > 0 else 0
        )

        # Average scores
        score_data = self.read_group(
            domain,
            fields=['composite_score:avg', 'entrance_score:avg', 'aggregate_percentage:avg'],
            groupby=[],
        )
        if score_data:
            data['avg_composite_score'] = round(score_data[0]['composite_score'], 1) if score_data[0]['composite_score'] else 0
            data['avg_entrance_score'] = round(score_data[0]['entrance_score'], 1) if score_data[0]['entrance_score'] else 0
            data['avg_aggregate_pct'] = round(score_data[0]['aggregate_percentage'], 1) if score_data[0]['aggregate_percentage'] else 0
        else:
            data['avg_composite_score'] = 0
            data['avg_entrance_score'] = 0
            data['avg_aggregate_pct'] = 0

        # ============================================================
        # BREAKDOWNS (by key dimensions)
        # ============================================================

        # By Program
        program_breakdown = self.read_group(
            domain,
            fields=['program_id', 'id:count'],
            groupby=['program_id'],
        )
        data['by_program'] = [
            {
                'program_id': item['program_id'][0] if item['program_id'] else None,
                'program_name': item['program_id'][1] if item['program_id'] else 'Unknown',
                'count': item['id'],
            }
            for item in program_breakdown
        ]

        # By Campus
        campus_breakdown = self.read_group(
            domain,
            fields=['campus_id', 'id:count'],
            groupby=['campus_id'],
        )
        data['by_campus'] = [
            {
                'campus_id': item['campus_id'][0] if item['campus_id'] else None,
                'campus_name': item['campus_id'][1] if item['campus_id'] else 'Unknown',
                'count': item['id'],
            }
            for item in campus_breakdown
        ]

        # By Academic Year (via cycle)
        year_breakdown = self.read_group(
            domain,
            fields=['cycle_id', 'id:count'],
            groupby=['cycle_id'],
        )
        data['by_academic_year'] = [
            {
                'cycle_id': item['cycle_id'][0] if item['cycle_id'] else None,
                'cycle_name': item['cycle_id'][1] if item['cycle_id'] else 'Unknown',
                'count': item['id'],
            }
            for item in year_breakdown
        ]

        # By Gender
        gender_breakdown = self.read_group(
            domain,
            fields=['gender', 'id:count'],
            groupby=['gender'],
        )
        data['by_gender'] = [
            {
                'gender': item['gender'],
                'label': self._format_gender(item['gender']),
                'count': item['id'],
            }
            for item in gender_breakdown
        ]

        # By Nationality
        nationality_breakdown = self.read_group(
            domain,
            fields=['nationality_id', 'id:count'],
            groupby=['nationality_id'],
        )
        data['by_nationality'] = [
            {
                'nationality_id': item['nationality_id'][0] if item['nationality_id'] else None,
                'nationality_name': item['nationality_id'][1] if item['nationality_id'] else 'Not Specified',
                'count': item['id'],
            }
            for item in nationality_breakdown
        ]

        # Applications over time (grouped by month of create_date)
        time_breakdown = self.read_group(
            domain,
            fields=['create_date', 'id:count'],
            groupby=['create_date:month'],
        )
        applications_over_time = []
        for item in time_breakdown:
            if item['create_date']:
                applications_over_time.append({
                    'month': item['create_date'],
                    'count': item['id'],
                })
        data['applications_over_time'] = applications_over_time

        return data

    def _format_state(self, state):
        """Format state selection value to display label."""
        state_labels = {
            'inquiry': 'Inquiry',
            'applied': 'Applied',
            'documents_pending': 'Documents Pending',
            'under_review': 'Under Review',
            'shortlisted': 'Shortlisted',
            'entrance_scheduled': 'Entrance Scheduled',
            'merit_listed': 'Merit Listed',
            'offer_sent': 'Offer Sent',
            'fee_pending': 'Fee Pending',
            'confirmed': 'Confirmed',
            'rejected': 'Rejected',
            'withdrawn': 'Withdrawn',
            'waitlisted': 'Waitlisted',
        }
        return state_labels.get(state, state)

    def _format_gender(self, gender):
        """Format gender selection value to display label."""
        gender_labels = {
            'male': 'Male',
            'female': 'Female',
            'other': 'Other',
            'prefer_not': 'Prefer Not to Say',
        }
        return gender_labels.get(gender, gender)
