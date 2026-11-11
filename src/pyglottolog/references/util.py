"""
Utilities for the handling of pages fields.
"""
import re

from .roman import romanint

ROMAN = r'[ivxlcdmIVXLCDM]+'
ROMANPATTERN = re.compile(ROMAN + '$')
ARABIC = r'[AESaes]?[0-9]+'
ARABICPATTERN = re.compile(ARABIC + '$')
SEPPAGESPATTERN = re.compile(
    r'(?P<n1>{0}|{1})\s*([,;.+/])\s*(?P<n2>{0}|{1})'.format(  # pylint: disable=C0209
        ROMAN, ARABIC))
PAGES_PATTERN = re.compile(
    r'(?P<start>{0}|{1})\s*--?\s*(?P<end>{0}|{1})'.format(  # pylint: disable=C0209
        ROMAN, ARABIC))
ART_NO_PATTERN = re.compile(r'\(art\.\s*[0-9]+\)')

MAX_PAGE = 10_000


def get_int(s: str) -> int | None:
    """
    >>> get_int('X')
    10
    """
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        if ROMANPATTERN.fullmatch(s):
            return romanint(s.lower())
    m = ARABICPATTERN.fullmatch(s)
    if m:
        if not s[0].isnumeric():
            return int(s[1:])
        # The case int(s) has already been handled above.
    return None


def _in_range(number):
    return 0 < number < MAX_PAGE


def _accumulate(page_specs):
    s, e, n = None, None, None

    # Now parts may include ranges.
    for res in page_specs:
        if res[0] is not None:  # A range!
            s = res[0] if s is None else None
        if res[1] is not None:
            e = res[1] if e is None else None
        if res[2]:
            n = (n or 0) + res[2]
    return (s, e, n)


def compute_pages(pages: str) -> tuple[int | None, int | None, int | None]:
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
    res = get_int(pages)
    if res:
        return (1, res, res) if _in_range(res) else (None, None, None)

    # next case: ,|.|+ separated numbers:
    parts = re.split(r'\s*[,;.+/]\s*', pages)
    ints = list(map(get_int, parts))
    if ints and all(ints):
        number = sum(ints)
        return (None, None, number if _in_range(number) else None)

    if len(parts) > 1:  # Recurse.
        return _accumulate([compute_pages(p) for p in parts])

    assert len(parts) == 1
    match = PAGES_PATTERN.fullmatch(pages)
    if not match:
        return (None, None, None)

    s_start, s_end = match.group('start'), match.group('end')
    s, e = get_int(s_start), get_int(s_end)
    assert (s is not None) and (e is not None)
    if ARABICPATTERN.match(s_end) and ARABICPATTERN.match(s_start):
        # Expand abbreviated digits, excluding optional page prefixes.
        start_digits = s_start.lstrip('AESaes')
        end_digits = s_end.lstrip('AESaes')
        if len(end_digits) < len(start_digits):
            # the case 516-32 (or E516-E32):
            e = int(start_digits[:-len(end_digits)] + end_digits)
    if s > e:  # the case 532-516:
        e, s = s, e
    n = e - s + 1
    return (s if _in_range(s) else None, e if _in_range(e) else None, n if _in_range(n) else None)
