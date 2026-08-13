import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FacultyPublication(models.Model):
    _name = 'oacis.faculty.publication'
    _description = 'Faculty Publication or Research Work'
    _rec_name = 'title'
    _order = 'faculty_member_id, publication_year desc'

    faculty_member_id = fields.Many2one(
        'oacis.faculty.member',
        string='Faculty Member',
        required=True,
        ondelete='cascade',
    )
    title = fields.Char(string='Publication Title', required=True)
    publication_type = fields.Selection([
        ('journal', 'Journal Article'),
        ('conference', 'Conference Paper'),
        ('book', 'Book'),
        ('book_chapter', 'Book Chapter'),
        ('thesis', 'Thesis / Dissertation'),
        ('patent', 'Patent'),
        ('technical_report', 'Technical Report'),
        ('other', 'Other'),
    ], string='Publication Type', required=True, default='journal')
    journal_or_venue = fields.Char(string='Journal / Conference / Publisher')
    publication_year = fields.Integer(string='Year of Publication', required=True)
    doi_or_isbn = fields.Char(string='DOI / ISBN / Patent No.')
    url = fields.Char(string='Publication URL')
    co_authors = fields.Char(
        string='Co-Authors',
        help='Comma separated list of co-author names',
    )
    is_indexed = fields.Boolean(
        string='Indexed Publication',
        default=False,
        help='Scopus, Web of Science, PubMed etc.',
    )
    index_type = fields.Selection([
        ('scopus', 'Scopus'),
        ('wos', 'Web of Science'),
        ('pubmed', 'PubMed'),
        ('eric', 'ERIC'),
        ('other', 'Other'),
    ], string='Index Type')
    abstract = fields.Text(string='Abstract')

    @api.constrains('publication_year')
    def _check_publication_year(self):
        current_year = date.today().year
        for record in self:
            if record.publication_year < 1900 or record.publication_year > current_year + 1:
                raise ValidationError(_(
                    'Publication year must be between 1900 and %(year)d.',
                    year=current_year + 1,
                ))
