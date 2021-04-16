# Python 3.6 compatibility backports

import sys

__all__ = ['nullcontext']


if sys.version_info < (3, 7):
    import contextlib

    @contextlib.contextmanager
    def nullcontext(enter_result=None):
        yield enter_result

else:
    from contextlib import nullcontext
