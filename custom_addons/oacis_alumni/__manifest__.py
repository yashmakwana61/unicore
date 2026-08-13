{
    'name': 'Alumni Engagement',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Bridge Oacis alumni into Odoo mass mailing and events',
    'description': """
        Alumni Engagement
        =================

        Bridges Oacis alumni records into Odoo's native Mass Mailing
        and Event modules so the alumni office can run newsletters,
        reunion events, and fundraising campaigns.

        Key behaviour:
        - A ``mass_mailing.mailing.list`` is auto-created when a student
          transitions to the ``alumni`` state, and the student is added
          as a contact.
        - Alumni can be registered for ``event.event`` records; event
          registrations are synced bidirectionally.
        - Smart buttons on the student form open linked mailing lists
          and alumni events.
        - No core ``oacis_student``, ``mass_mailing``, or ``event``
          logic is modified.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'mass_mailing',
        'event',
        'oacis_student',
        'oacis_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/alumni_data.xml',
        'views/student_alumni_views.xml',
        'views/mass_mailing_views.xml',
        'views/event_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'oacis_alumni,static/description/icon.png',
    'installable': True,
    'application': False,
    'auto_install': False,
}
