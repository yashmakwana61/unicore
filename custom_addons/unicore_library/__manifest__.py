{
    'name': 'Library',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'University library management with '
               'catalogue, issue tracking and fines',
    'description': """
        UniCore Library provides a complete university
        library management system:

        - Book Catalogue: ISBN, authors, subjects,
          publishers with multi-copy tracking
        - Book Copies: individual physical copies
          with accession numbers and condition
        - Library Members: students and faculty
          with borrowing privileges and limits
        - Issue and Return: book lending with
          configurable due dates and fine rates
        - Overdue Tracking: automatic fine
          calculation at configurable rates
        - Reservations: queue-based reservation
          for currently issued books
        - Dashboard: overdue books, pending returns,
          popular books analytics

        Appears as a dedicated app in the Odoo
        home screen.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base', 'unicore_security',
        'unicore_campus', 'unicore_academic',
        'unicore_student', 'unicore_faculty_profile',
        'mail',
    ],
    'data': [
        'security/unicore_library_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_library_config_data.xml',
        'views/unicore_library_book_views.xml',
        'views/unicore_library_member_views.xml',
        'views/unicore_library_issue_views.xml',
        'views/library_issue_search_phase1.xml',
        'views/unicore_library_reservation_views.xml',
        'menus/unicore_library_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'web_icon': 'unicore_library,'
                'static/description/icon.png',
}
