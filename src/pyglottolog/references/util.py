import re

from .roman import romanint

ROMAN = r'[ivxlcdmIVXLCDM]+'

ROMANPATTERN = re.compile(ROMAN + '$')

ARABIC = r'[0-9]+'

ARABICPATTERN = re.compile(ARABIC + '$')

SEPPAGESPATTERN = re.compile(
    r'(?P<n1>{0}|{1})\s*(,|;|\.|\+|/)\s*(?P<n2>{0}|{1})'.format(ROMAN, ARABIC))

PAGES_PATTERN = re.compile(
    r'(?P<start>{0}|{1})\s*\-\-?\s*(?P<end>{0}|{1})'.format(ROMAN, ARABIC))

ART_NO_PATTERN = re.compile(r'\(art\.\s*[0-9]+\)')

MAX_PAGE = 10_000


def get_int(s):
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        if ROMANPATTERN.match(s):
            return romanint(s.lower())


def compute_pages(pages):
    """

    >>> compute_pages('x+23')
    (None, None, 33)

    >>> compute_pages('x + 23')
    (None, None, 33)

    >>> compute_pages('x. 23')
    (None, None, 33)

    >>> compute_pages('23,xi')
    (None, None, 34)

    >>> compute_pages('23,ix')
    (None, None, 32)

    >>> compute_pages('ix')
    (1, 9, 9)

    >>> compute_pages('12-45')
    (12, 45, 34)

    >>> compute_pages('125-9')
    (125, 129, 5)

    >>> compute_pages('7-3')
    (3, 7, 5)
    """
    pages = ART_NO_PATTERN.sub('', pages)
    pages = pages.strip().replace('\u2013', '-')
    if pages.endswith('.'):
        pages = pages[:-1]
    if pages.endswith('pp'):
        pages = pages[:-2]

    # trivial case: just one number:
    number = get_int(pages)
    if number:
        start = 1
        if number > MAX_PAGE:
            number, start = None, None
        return (start, number, number)

    # next case: ,|.|+ separated numbers:
    m = SEPPAGESPATTERN.match(pages)
    if m:
        number = sum(map(get_int, [m.group('n1'), m.group('n2')]))
        if number > MAX_PAGE:
            number = None
        return (None, None, number)

    # next case: ranges:
    start = None
    end = None
    number = None

    for match in PAGES_PATTERN.finditer(pages):
        s_start, s_end = match.group('start'), match.group('end')
        s, e = get_int(s_start), get_int(s_end)
        if ARABICPATTERN.match(s_end) and ARABICPATTERN.match(s_start) \
                and len(s_end) < len(s_start):
            # the case 516-32:
            s_end = s_start[:-len(s_end)] + s_end
            e = get_int(s_end)
        if s > e:
            # the case 532-516:
            e, s = s, e
        if start is None:
            start = s
        end = e
        number = (number or 0) + (end - s + 1)

    if start and start > MAX_PAGE:
        start = None
    if end and end > MAX_PAGE:
        end = None
    if number and number > MAX_PAGE:
        number = None

    return (start, end, number if (number is not None and number > 0) else None)
