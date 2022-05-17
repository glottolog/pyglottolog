# Python compatibility backports

import sys

__all__ = ['removesuffix']


if sys.version_info < (3, 9):
    def removesuffix(s: str, suffix: str) -> str:
        """See https://www.python.org/dev/peps/pep-0616/

        >>> removesuffix('spam.bib', '.bib')
        'spam'
        """
        return s[:-len(suffix)] if suffix and s.endswith(suffix) else s

else:  # pragma: no cover
    def removesuffix(s: str, suffix: str) -> str:
        """See https://www.python.org/dev/peps/pep-0616/

        >>> removesuffix('spam.bib', '.bib')
        'spam'
        """
        return s.removesuffix(suffix)
