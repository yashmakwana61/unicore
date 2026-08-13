{
    'name': 'Convocation Management',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Bridge UniCore convocation into Odoo events',
    'description': """
        Convocation Management
        =======================

        Bridges UniCore's convocation ceremony into Odoo's native Event
        module so the university can manage graduation ceremonies with
        standard event features: venue booking, seat allocation,
        registration tracking, and communication.

        Key behaviour:
        - A ``event.event`` is auto-created for each convocation cycle
          with the ceremony date, venue, and capacity.
        - Graduated students are auto-registered for the upcoming
          convocation event.
        - A smart button on the student form opens the convocation event.
        - A smart button on the convocation event shows registered
          graduates.
        - No core ``unicore_student`` or ``event`` logic is modified.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'event',
        'unicore_student',
        'unicore_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/convocation_data.xml',
        'views/student_convocation_views.xml',
        'views/event_event_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_convocation,static/description/icon.png',
    'installable': True,
    'application': False,
    'auto_install': False,
}
