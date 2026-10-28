import pytest

from pyglottolog.references.util import compute_pages


@pytest.mark.parametrize(
    'pages_string,pages_int',
    [
        ('43-68, A1-A56', 26+56),
        ('297+772+708+981', 297+772+708+981),
        ('2-31, 128-128', 30+1),
        ('x+23', 33),
        ('x + 23', 33),
        ('x. 23', 33),
        ('23,xi', 34),
        ('23,ix', 32),
        ('ix', 9),
        ('12-45', 34),
        ('125-9', 5),
        ('7-3', 5),
    ]
)
def test_compute_pages(pages_string, pages_int):
    assert compute_pages(pages_string)[2] == pages_int


@pytest.mark.parametrize(
    'pages,expected',
    [
        ('A125-A9', (125, 129, 5)),
        ('a125-a9', (125, 129, 5)),
        ('S100-S8', (100, 108, 9)),
        ('s100-s8', (100, 108, 9)),
        ('E516-E32', (516, 532, 17)),
        ('e516-e32', (516, 532, 17)),
        ('125-A9', (125, 129, 5)),
        ('125-A99', (125, 199, 75)),
        ('A125-9', (125, 129, 5)),
        ('A125-A09', (109, 125, 17)),
        ('S10-S01', (1, 10, 10)),
        ('E009-E12', (9, 12, 4)),
        ('viii, A125-A9', (None, None, 13)),
        ('12-15; S100-S8', (None, None, 13)),
        ('x + E516-E32', (None, None, 27)),
    ],
)
def test_compute_pages_prefixed_abbreviations(pages, expected):
    assert compute_pages(pages) == expected
