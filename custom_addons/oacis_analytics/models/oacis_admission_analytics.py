"""
Oacis Admission Analytics
PostgreSQL VIEW-based models for admission funnel,
conversion rates and applicant analytics.
"""

import logging

from odoo import fields, models, tools
from odoo.orm.fields_misc import Id

_logger = logging.getLogger(__name__)


class OacisAdmissionFunnelReport(models.Model):
    _name = 'oacis.admission.funnel.report'
    _description = 'Admission Funnel Analytics'
    _auto = False
    _rec_name = 'program_id'
    _order = 'academic_year_id desc, program_id'

    id = Id()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        readonly=True,
    )
    cycle_id = fields.Many2one(
        comodel_name='oacis.admission.cycle',
        string='Admission Cycle',
        readonly=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='oacis.academic.year',
        string='Academic Year',
        readonly=True,
    )
    program_id = fields.Many2one(
        comodel_name='oacis.program',
        string='Program',
        readonly=True,
    )
    total_applications = fields.Integer(
        string='Total Applications',
        readonly=True,
    )
    shortlisted = fields.Integer(
        string='Shortlisted',
        readonly=True,
    )
    offer_sent = fields.Integer(
        string='Offers Sent',
        readonly=True,
    )
    confirmed = fields.Integer(
        string='Confirmed',
        readonly=True,
    )
    rejected = fields.Integer(
        string='Rejected',
        readonly=True,
    )
    withdrawn = fields.Integer(
        string='Withdrawn',
        readonly=True,
    )
    shortlist_rate = fields.Float(
        string='Shortlist Rate %',
        readonly=True,
        digits=(5, 1),
    )
    offer_conversion_rate = fields.Float(
        string='Offer Conversion %',
        readonly=True,
        digits=(5, 1),
    )
    admission_rate = fields.Float(
        string='Admission Rate %',
        readonly=True,
        digits=(5, 1),
    )
    avg_entrance_score = fields.Float(
        string='Avg Entrance Score',
        readonly=True,
        digits=(5, 1),
    )
    avg_aggregate_pct = fields.Float(
        string='Avg Aggregate %',
        readonly=True,
        digits=(5, 1),
    )

    def init(self):
        tools.drop_view_if_exists(
            self.env.cr,
            'oacis_admission_funnel_report',
        )
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW
            oacis_admission_funnel_report AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    a.company_id,
                    a.cycle_id,
                    ac.academic_year_id,
                    a.program_id,
                    COUNT(a.id) AS total_applications,
                    COUNT(CASE WHEN a.state
                        IN ('shortlisted',
                            'merit_listed',
                            'offer_sent',
                            'fee_pending',
                            'confirmed')
                        THEN 1 END) AS shortlisted,
                    COUNT(CASE WHEN a.state
                        IN ('offer_sent',
                            'fee_pending',
                            'confirmed')
                        THEN 1 END) AS offer_sent,
                    COUNT(CASE WHEN a.state
                        = 'confirmed'
                        THEN 1 END) AS confirmed,
                    COUNT(CASE WHEN a.state
                        = 'rejected'
                        THEN 1 END) AS rejected,
                    COUNT(CASE WHEN a.state
                        = 'withdrawn'
                        THEN 1 END) AS withdrawn,
                    ROUND(
                        (COUNT(CASE WHEN a.state
                            IN ('shortlisted',
                                'merit_listed',
                                'offer_sent',
                                'fee_pending',
                                'confirmed')
                            THEN 1 END)::numeric
                        / NULLIF(COUNT(a.id), 0)
                        * 100), 1
                    ) AS shortlist_rate,
                    ROUND(
                        (COUNT(CASE WHEN a.state
                            = 'confirmed'
                            THEN 1 END)::numeric
                        / NULLIF(COUNT(CASE WHEN
                            a.state IN
                            ('offer_sent','fee_pending',
                             'confirmed') THEN 1 END), 0)
                        * 100), 1
                    ) AS offer_conversion_rate,
                    ROUND(
                        (COUNT(CASE WHEN a.state
                            = 'confirmed'
                            THEN 1 END)::numeric
                        / NULLIF(COUNT(a.id), 0)
                        * 100), 1
                    ) AS admission_rate,
                    ROUND(
                        AVG(a.entrance_score)::numeric, 1
                    ) AS avg_entrance_score,
                    ROUND(
                        AVG(a.aggregate_percentage)
                        ::numeric, 1
                    ) AS avg_aggregate_pct
                FROM oacis_admission_applicant a
                JOIN oacis_admission_cycle ac
                    ON ac.id = a.cycle_id
                GROUP BY
                    a.company_id,
                    a.cycle_id,
                    ac.academic_year_id,
                    a.program_id
            )
        """)


class OacisApplicantCategoryReport(models.Model):
    _name = 'oacis.applicant.category.report'
    _description = 'Applicant Category Analytics'
    _auto = False
    _rec_name = 'category'
    _order = 'academic_year_id desc, category'

    id = Id()
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        readonly=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='oacis.academic.year',
        string='Academic Year',
        readonly=True,
    )
    category = fields.Selection(
        string='Category',
        readonly=True,
        selection=[
            ('general', 'General'),
            ('obc', 'OBC'),
            ('sc', 'SC'),
            ('st', 'ST'),
            ('ews', 'EWS'),
            ('pwd', 'PwD'),
            ('nri', 'NRI'),
            ('other', 'Other'),
        ],
    )
    gender = fields.Selection(
        string='Gender',
        readonly=True,
        selection=[
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other'),
        ],
    )
    total_applicants = fields.Integer(
        string='Total Applicants',
        readonly=True,
    )
    confirmed = fields.Integer(
        string='Admitted',
        readonly=True,
    )
    avg_score = fields.Float(
        string='Avg Composite Score',
        readonly=True,
        digits=(5, 1),
    )

    def init(self):
        tools.drop_view_if_exists(
            self.env.cr,
            'oacis_applicant_category_report',
        )
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW
            oacis_applicant_category_report AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    a.company_id,
                    ac.academic_year_id,
                    'general'::varchar AS category,
                    a.gender,
                    COUNT(a.id) AS total_applicants,
                    COUNT(CASE WHEN a.state
                        = 'confirmed'
                        THEN 1 END) AS confirmed,
                    ROUND(
                        AVG(a.composite_score)::numeric, 1
                    ) AS avg_score
                FROM oacis_admission_applicant a
                JOIN oacis_admission_cycle ac
                    ON ac.id = a.cycle_id
                GROUP BY
                    a.company_id,
                    ac.academic_year_id,
                    a.gender
            )
        """)
