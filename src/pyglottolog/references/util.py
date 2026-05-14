"""
Utilities for the handling of pages fields.
"""
import re
from typing import Optional

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


def get_int(s: str) -> Optional[int]:
    """
    >>> get_int('X')
    10
    """
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        if ROMANPATTERN.match(s):
            return romanint(s.lower())
    m = ARABICPATTERN.match(s)
    if m:
        if not s[0].isnumeric():
            return int(s[1:])
        # The case int(s) has already been handled above.
    return None


def compute_pages(pages: str) -> Optional[tuple[Optional[int], Optional[int], Optional[int]]]:
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
    parts = re.split(r'\s*[,;.+/]\s*', pages)
    if all(ARABICPATTERN.match(p) or ROMANPATTERN.match(p) for p in parts):
        number = sum(map(get_int, parts))
        return (None, None, number if number <= MAX_PAGE else None)
    if len(parts) > 1:
        s = None
        e = None
        n = None

        # Now parts may include ranges.
        for p in parts:
            res = compute_pages(p)
            if res[0] is not None:
                # More than range: We cannot turn this into a single range.
                s = res[0] if s is None else None
            if res[1] is not None:
                e = res[1] if e is None else None
            if res[2]:
                n = (n or 0) + res[2]
        return (s, e, n)

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
