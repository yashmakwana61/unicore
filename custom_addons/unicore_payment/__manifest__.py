{
    'name': 'Online Fee Payments',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Online fee payment for UniCore through Odoo payment providers',
    'description': """
        Online Fee Payments
        ===================

        Enables students to pay their fee invoices online using the standard
        Odoo payment providers (Razorpay, Stripe, PayPal, ...).

        Because every UniCore fee invoice already generates a posted GL
        account.move (account_payment), this module is a thin bridge that
        reuses Odoo's native invoice payment flow:

        - Backend: "Payment Link" button on the fee invoice that opens the
          payment.link.wizard for the linked GL invoice (shareable link/QR).
        - Portal: "Pay Online" button on the student fee page linking to the
          native invoice checkout page.
        - Status sync: when the online transaction is confirmed, the fee
          invoice status is updated to 'partial' / 'paid' from the GL
          reconciliation.

        No fee-invoice state machine or accounting logic is modified.
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://precisefect.com',
    'license': 'OPL-1',
    'depends': [
        'account_payment',
        'payment',
        'unicore_fees',
        'unicore_portal_student',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/unicore_fee_invoice_payment_views.xml',
        'views/payment_portal_templates.xml',
    ],
    'images': ['static/description/icon.png'],
    'web_icon': 'unicore_payment,static/description/icon.png',
    'installable': True,
    'application': False,
    'auto_install': False,
}
