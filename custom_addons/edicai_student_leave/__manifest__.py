{
    'name': 'Edicai Student Leave Requests',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Student/guardian-initiated leave request '
               'workflow with approval routing',
    'description': """
        Provides a formal, student/guardian-initiated
        leave request workflow for Edicai ERP.

        Students or guardians can submit leave requests
        specifying reason, dates, and supporting documents.
        Requests route to faculty/registrar for approval
        before the existing "Place on Leave" state
        transition is triggered on edicai.student.

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
        'edicai_student',
        'edicai_guardian',
        'edicai_notify',
        'edicai_portal_student',
        'edicai_portal_guardian',
    ],
    'data': [
        'security/edicai_student_leave_record_rules.xml',
        'security/ir.model.access.csv',
        'data/edicai_student_leave_sequence_data.xml',
        'data/edicai_student_leave_notify_templates.xml',
        'views/edicai_student_leave_views.xml',
        'views/edicai_student_leave_portal_templates.xml',
        'menus/edicai_student_leave_menus.xml',
    ],
    'assets': {
        'web.assets_frontend': [],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
