"""
Oacis Library Book Models
Book catalogue with subject classification and
individual copy tracking per accession number.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class OacisLibrarySubject(models.Model):
    _name = 'oacis.library.subject'
    _description = 'Library Subject / Classification'
    _order = 'name'

    name = fields.Char(
        string='Subject Name',
        required=True,
    )
    code = fields.Char(
        string='Subject Code',
        size=20,
    )
    parent_id = fields.Many2one(
        comodel_name='oacis.library.subject',
        string='Parent Subject',
        ondelete='set null',
    )
    description = fields.Text(string='Description')
    book_count = fields.Integer(
        string='Books',
        compute='_compute_book_count',
        store=False,
    )

    def _compute_book_count(self):
        Book = self.env['oacis.library.book']
        for rec in self:
            rec.book_count = Book.search_count([
                ('subject_ids', 'in', [rec.id]),
            ])

    _sql_constraints = [
        ('unique_subject_code',
         'UNIQUE(code)',
         'Subject code must be unique.'),
    ]


class OacisLibraryPublisher(models.Model):
    _name = 'oacis.library.publisher'
    _description = 'Publisher'
    _order = 'name'

    name = fields.Char(
        string='Publisher Name',
        required=True,
    )
    country_id = fields.Many2one(
        comodel_name='res.country',
        string='Country',
    )
    website = fields.Char(string='Website')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')

    _sql_constraints = [
        ('unique_publisher_name',
         'UNIQUE(name)',
         'Publisher name must be unique.'),
    ]


class OacisLibraryBook(models.Model):
    _name = 'oacis.library.book'
    _description = 'Library Book'
    _inherit = ['oacis.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'title'
    _check_company_auto = True

    # --- IDENTITY ---

    title = fields.Char(
        string='Title',
        required=True,
        tracking=True,
        index=True,
    )
    subtitle = fields.Char(string='Subtitle')
    isbn = fields.Char(
        string='ISBN',
        size=20,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    # --- AUTHORS ---

    author_ids = fields.Many2many(
        comodel_name='oacis.library.author',
        relation='oacis_book_author_rel',
        column1='book_id',
        column2='author_id',
        string='Authors',
    )
    author_display = fields.Char(
        string='Authors',
        compute='_compute_author_display',
        store=True,
    )

    @api.depends('author_ids')
    def _compute_author_display(self):
        for rec in self:
            rec.author_display = ', '.join(
                rec.author_ids.mapped('name'),
            )

    # --- PUBLICATION ---

    publisher_id = fields.Many2one(
        comodel_name='oacis.library.publisher',
        string='Publisher',
        ondelete='set null',
    )
    publication_year = fields.Integer(
        string='Year of Publication',
    )
    edition = fields.Char(
        string='Edition',
        size=20,
        help='e.g. 1st, 2nd, Revised',
    )
    language = fields.Selection(
        string='Language',
        selection=[
            ('english', 'English'),
            ('hindi', 'Hindi'),
            ('gujarati', 'Gujarati'),
            ('other', 'Other'),
        ],
        default='english',
    )
    pages = fields.Integer(string='Number of Pages')

    # --- CLASSIFICATION ---

    subject_ids = fields.Many2many(
        comodel_name='oacis.library.subject',
        relation='oacis_book_subject_rel',
        column1='book_id',
        column2='subject_id',
        string='Subjects',
    )
    book_type = fields.Selection(
        string='Book Type',
        required=True,
        default='book',
        selection=[
            ('book', 'Book'),
            ('reference', 'Reference Book'),
            ('journal', 'Journal / Periodical'),
            ('thesis', 'Thesis / Dissertation'),
            ('magazine', 'Magazine'),
            ('ebook', 'E-Book'),
            ('cd', 'CD / DVD'),
            ('other', 'Other'),
        ],
    )
    call_number = fields.Char(
        string='Call Number',
        help='Dewey Decimal or Library call number',
    )
    location = fields.Char(
        string='Shelf Location',
        help='e.g. Rack A-12, Ground Floor',
    )

    # --- COVER IMAGE ---

    cover_image = fields.Binary(
        string='Cover Image',
        attachment=True,
    )

    # --- COPY STATS ---

    copy_ids = fields.One2many(
        comodel_name='oacis.library.book.copy',
        inverse_name='book_id',
        string='Copies',
    )
    total_copies = fields.Integer(
        string='Total Copies',
        compute='_compute_copy_stats',
        store=True,
    )
    available_copies = fields.Integer(
        string='Available',
        compute='_compute_copy_stats',
        store=True,
    )
    issued_copies = fields.Integer(
        string='Issued',
        compute='_compute_copy_stats',
        store=True,
    )

    @api.depends('copy_ids',
                 'copy_ids.copy_state')
    def _compute_copy_stats(self):
        for rec in self:
            copies = rec.copy_ids.filtered(
                lambda c: c.copy_state != 'withdrawn',
            )
            rec.total_copies = len(copies)
            rec.available_copies = len(
                copies.filtered(
                    lambda c: c.copy_state
                    == 'available',
                ),
            )
            rec.issued_copies = len(
                copies.filtered(
                    lambda c: c.copy_state
                    == 'issued',
                ),
            )

    is_available = fields.Boolean(
        string='Available',
        compute='_compute_copy_stats',
        store=False,
    )
    description = fields.Text(
        string='Description / Synopsis',
    )
    table_of_contents = fields.Text(
        string='Table of Contents',
    )
    notes = fields.Text(string='Internal Notes')

    # --- STATUS ---

    book_state = fields.Selection(
        string='Status',
        required=True,
        default='active',
        tracking=True,
        selection=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('lost', 'Lost'),
        ],
    )

    _sql_constraints = [
        ('unique_isbn_company',
         'UNIQUE(isbn, company_id)',
         'A book with this ISBN already exists.'),
    ]

    def action_add_copy(self):
        """Quick action to add a new copy."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Copy'),
            'res_model': 'oacis.library.book.copy',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_book_id': self.id,
                'default_company_id': (
                    self.company_id.id
                ),
            },
        }


class OacisLibraryAuthor(models.Model):
    _name = 'oacis.library.author'
    _description = 'Book Author'
    _order = 'name'

    name = fields.Char(
        string='Author Name',
        required=True,
    )
    bio = fields.Text(string='Biography')
    country_id = fields.Many2one(
        comodel_name='res.country',
        string='Country',
    )

    _sql_constraints = [
        ('unique_author_name',
         'UNIQUE(name)',
         'Author name must be unique.'),
    ]


class OacisLibraryBookCopy(models.Model):
    _name = 'oacis.library.book.copy'
    _description = 'Book Copy'
    _inherit = ['oacis.mixin']
    _order = 'accession_number'
    _check_company_auto = True

    accession_number = fields.Char(
        string='Accession Number',
        required=True,
        index=True,
        readonly=True,
        copy=False,
    )
    book_id = fields.Many2one(
        comodel_name='oacis.library.book',
        string='Book',
        required=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    acquisition_date = fields.Date(
        string='Date Acquired',
        default=fields.Date.today,
    )
    acquisition_cost = fields.Monetary(
        string='Cost',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        readonly=True,
        store=True,
    )
    condition = fields.Selection(
        string='Condition',
        required=True,
        default='good',
        selection=[
            ('new', 'New'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
            ('damaged', 'Damaged'),
        ],
    )
    copy_state = fields.Selection(
        string='Status',
        required=True,
        default='available',
        selection=[
            ('available', 'Available'),
            ('issued', 'Issued'),
            ('reserved', 'Reserved'),
            ('maintenance', 'Under Maintenance'),
            ('lost', 'Lost'),
            ('withdrawn', 'Withdrawn'),
        ],
    )
    current_issue_id = fields.Many2one(
        comodel_name='oacis.library.issue',
        string='Current Issue',
        readonly=True,
        ondelete='set null',
    )
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('accession_number'):
                vals['accession_number'] = (
                    self.env['ir.sequence'].next_by_code(
                        'oacis.library.book.copy',
                    ) or '/'
                )
        return super().create(vals_list)

    _sql_constraints = [
        ('unique_accession_number',
         'UNIQUE(accession_number)',
         'Accession number must be unique.'),
    ]
