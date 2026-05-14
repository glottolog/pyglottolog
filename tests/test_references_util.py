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
