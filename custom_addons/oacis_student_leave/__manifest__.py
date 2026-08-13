{
    'name': 'Oacis Student Leave Requests',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Student/guardian-initiated leave request '
               'workflow with approval routing',
    'description': """
        Provides a formal, student/guardian-initiated
        leave request workflow for Oacis ERP.

        Students or guardians can submit leave requests
        specifying reason, dates, and supporting documents.
        Requests route to faculty/registrar for approval
        before the existing "Place on Leave" state
        transition is triggered on oacis.student.

        FEATURES:
        - Portal-based request submission (student & guardian)
        - Backend review, approval and rejection workflow
        - Multi-channel notifications on submit/approve/reject
        - Automatic "Place on Leave" trigger on approval
        - Supporting document attachment
        - Activity-based notification for approvers
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'oacis_student',
        'oacis_guardian',
        'oacis_notify',
        'oacis_portal_student',
        'oacis_portal_guardian',
    ],
    'data': [
        'security/oacis_student_leave_record_rules.xml',
        'security/ir.model.access.csv',
        'data/oacis_student_leave_sequence_data.xml',
        'data/oacis_student_leave_notify_templates.xml',
        'views/oacis_student_leave_views.xml',
        'views/oacis_student_leave_portal_templates.xml',
        'menus/oacis_student_leave_menus.xml',
    ],
    'assets': {
        'web.assets_frontend': [],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
