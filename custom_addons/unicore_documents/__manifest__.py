{
    'name': 'Documents',
    'version': '19.0.1.0.1',
    'category': 'Education',
    'summary': 'Centralised document management '
               'for students, faculty and institution',
    'description': """
        UniCore Documents provides a lightweight
        document management system:

        - Document Categories: hierarchical folder
          structure (Student Docs, Faculty Docs,
          Institutional, Templates)
        - Document Records: metadata + ir.attachment
          file storage with version tracking
        - Access Control: per-category permissions
          controlling who can upload, view, download
        - Student Documents: marksheets, certificates,
          ID proofs linked to student records
        - Faculty Documents: contracts, qualifications,
          appointment letters
        - Institutional Documents: policies, notices,
          academic calendars, circulars
        - Document Templates: reusable templates for
          bonafide letters, certificates, transcripts

        Standalone app in Odoo home screen.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'unicore_base', 'unicore_security',
        'unicore_campus', 'unicore_academic',
        'unicore_calendar', 'unicore_student',
        'unicore_faculty_profile',
        'unicore_admission', 'mail',
    ],
    'data': [
        'security/unicore_documents_record_rules.xml',
        'security/ir.model.access.csv',
        'data/unicore_documents_category_data.xml',
        'views/unicore_document_category_views.xml',
        'views/unicore_document_views.xml',
        'views/document_search_phase1.xml',
        'views/unicore_document_template_views.xml',
        'menus/unicore_documents_menus.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_documents,'
                'static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
