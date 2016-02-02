from contextlib import contextmanager

_empty = object()


class tmp_attr:

    def __init__(self, obj, **kwargs):
        self.obj = obj
        self.kwargs = kwargs

    def __enter__(self):
        obj = self.obj
        kwargs = self.kwargs
        early = {}
        for k, v in kwargs.items():
            early[k] = getattr(obj, k, _empty)
            setattr(obj, k, v)
        self.early = early

    def __exit__(self, *args):
        early = self.early
        obj = self.obj
        for k, v in early.items():
            if v is _empty:
                delattr(obj, k)
            else:
                setattr(obj, k, v)


def instantiate(f):
    return f()


def isolated(f):
    return f()


def isolated_with_self(**kwargs):
    def decorate(f):
        return f(self=f, **kwargs)

    return decorate
