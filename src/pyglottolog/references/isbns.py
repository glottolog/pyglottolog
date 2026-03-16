# isbns.py
"""
https://en.wikipedia.org/wiki/International_Standard_Book_Number
"""
import re

__all__ = ['Isbns', 'Isbn']


class Isbns(list):
    """ISBN numbers"""
    class Parser:  # pylint: disable=C0115,R0903
        @staticmethod
        def parse(ma):  # pylint: disable=C0116
            return ''.join(g for g in ma.groups() if g is not None)

    class Numeric(Parser):  # pylint: disable=C0115,R0903
        pattern = re.compile(r'(97[89])?(\d{9})([\dXx])(?![\dXx])')

    class Hyphened(Parser):  # pylint: disable=C0115,R0903
        pattern = re.compile(r'''
            (?:
              (?:ISBN[- ])? (97[89])-
              |
              ISBN-10[ ]
            )?
            (\d{1,5})- (\d+)- (\d+)- ([\dXx])(?![\dXx])''', flags=re.VERBOSE)

    class Ten99(Parser):  # pylint: disable=C0115,R0903
        pattern = re.compile(r'(99)-(\d{7})-([\dXx])(?![\dXx])')

    @classmethod
    def _iterparse(cls, s, pos=0, parsers=(Numeric, Hyphened, Ten99), delimiters=(', ', ' ')):
        while True:
            for p in parsers:
                ma = p.pattern.match(s, pos)
                if ma is not None:
                    yield p.parse(ma)
                    pos += len(ma.group())
                    break
            else:
                raise ValueError('no matching ISBN pattern at index {pos}: {s!r}')
            if pos == len(s):
                return
            for delim in delimiters:
                if s.startswith(delim, pos):
                    pos += len(delim)
                    break
            else:
                raise ValueError(f'no matching delimiter at index {pos}: {s!r}')

    @classmethod
    def from_field(cls, field):  # pylint: disable=C0116
        isbns = map(Isbn, cls._iterparse(field))
        seen = set()
        return cls(i for i in isbns if i not in seen and not seen.add(i))

    def to_string(self):  # pylint: disable=C0116
        return ', '.join(i.digits for i in self)


class Isbn:
    """A 13 digit ISBN from a string of 13 or 10 digits.

    see also https://en.wikipedia.org/wiki/International_Standard_Book_Number
    """

    _isbn10_prefix = '978'

    @staticmethod
    def _isbn13_check_digit(digits):
        assert len(digits) in (12, 13)
        halfes = (digits[i:12:2] for i in (0, 1))
        odd, even = (sum(map(int, h)) for h in halfes)
        return str(-(odd + 3 * even) % 10)

    @staticmethod
    def _isbn10_check_digit(digits):
        assert len(digits) in (9, 10)
        result = sum(i * int(d) for i, d in enumerate(digits[:9], 1)) % 11
        return 'X' if result == 10 else str(result)

    def __init__(self, digits):
        if len(digits) == 13:
            check = self._isbn13_check_digit(digits)
        elif len(digits) == 10:
            digits = digits.upper()
            check = self._isbn10_check_digit(digits)
        else:
            raise ValueError(f'invalid ISBN digits length ({len(digits)}): {digits!r}')

        if digits[-1] != check:
            raise ValueError(
                f'invalid ISBN check digit ({digits[-1]} instead of {check}): {digits!r}')

        if len(digits) == 10:  # convert
            digits = self._isbn10_prefix + digits[:9]
            digits += self._isbn13_check_digit(digits)
        self.digits = digits

    def __hash__(self):
        return hash(self.digits)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.digits == other.digits
        return NotImplemented  # pragma: no cover

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return self.digits != other.digits
        return NotImplemented  # pragma: no cover

    def __repr__(self):
        return f'{self.__class__.__name__}({self.digits!r})'
