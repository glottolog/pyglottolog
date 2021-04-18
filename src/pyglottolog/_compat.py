# Python compatibility backports

import sys

__all__ = ['nullcontext',
           'removesuffix']


if sys.version_info < (3, 7):
    import contextlib

    @contextlib.contextmanager
    def nullcontext(enter_result=None):
        yield enter_result

else:
    from contextlib import nullcontext


if sys.version_info < (3, 9):
    def removesuffix(s: str, suffix: str) -> str:
        """See https://www.python.org/dev/peps/pep-0616/

        >>> removesuffix('spam.bib', '.bib')
        'spam'
        """
        if suffix and s.endswith(suffix):
            return s[:-len(suffix)]
        else:
            return s

else:
    import operator

    def removesuffix(s: str, suffix: str) -> str:
        """See https://www.python.org/dev/peps/pep-0616/

        >>> removesuffix('spam.bib', '.bib')
        'spam'
        """
        return s.removesuffix(suffix)
