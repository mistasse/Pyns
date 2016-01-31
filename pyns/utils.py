from contextlib import contextmanager

_empty = object()


@contextmanager
def tmp_attr(obj, **kwargs):
    early = {}
    for k, v in kwargs.items():
        early[k] = getattr(obj, k, _empty)
        setattr(obj, k, v)

    yield

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
