from odoo import api, models

ONES = [
    '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
    'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen',
    'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen',
    'Nineteen',
]

TENS = [
    '', '', 'Twenty', 'Thirty', 'Forty', 'Fifty',
    'Sixty', 'Seventy', 'Eighty', 'Ninety',
]


def _convert_below_hundred(n):
    if n < 20:
        return ONES[n]
    return TENS[n // 10] + (' ' + ONES[n % 10] if n % 10 else '')


def _convert_below_thousand(n):
    if n < 100:
        return _convert_below_hundred(n)
    h = n // 100
    r = n % 100
    return ONES[h] + ' Hundred' + (' ' + _convert_below_hundred(r) if r else '')


def amount_to_words(amount):
    if amount is None:
        return 'Zero Rupees Only'

    integer_part = int(amount)
    decimal_part = round((amount - integer_part) * 100)

    if integer_part == 0 and decimal_part == 0:
        return 'Zero Rupees Only'

    crore = integer_part // 10000000
    remainder = integer_part % 10000000
    lakh = remainder // 100000
    remainder = remainder % 100000
    thousand = remainder // 1000
    remainder = remainder % 1000

    parts = []
    if crore:
        parts.append(_convert_below_hundred(crore) + ' Crore' + ('s' if crore > 1 else ''))
    if lakh:
        parts.append(_convert_below_hundred(lakh) + ' Lakh' + ('s' if lakh > 1 else ''))
    if thousand:
        parts.append(_convert_below_thousand(thousand) + ' Thousand')
    if remainder:
        parts.append(_convert_below_thousand(remainder))

    result = ' '.join(parts) + ' Rupees'
    if decimal_part:
        result += ' ' + _convert_below_hundred(decimal_part) + ' Paise'

    result += ' Only'
    return result


def indian_format(amount):
    if amount is None:
        return '0.00'
    integer_part = int(amount)
    decimal_part = int(round((amount - integer_part) * 100))
    s = str(integer_part)
    n = len(s)
    if n <= 3:
        result = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        result = ','.join(groups) + ',' + last3
    return '₹ ' + result + '.' + str(decimal_part).zfill(2)


class UniCoreFeeReceiptReport(models.AbstractModel):
    _name = 'report.unicore_fees.fee_receipt_template'
    _description = 'Fee Payment Receipt Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        payments = self.env['unicore.fee.payment'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'unicore.fee.payment',
            'docs': payments,
            'amount_to_words': amount_to_words,
            'indian_format': indian_format,
            'data': data or {},
        }
