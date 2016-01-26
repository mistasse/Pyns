from pyns.utils import *
import re

# a matcher is a function returning True or False to indicate whether the argument fits or not


def m_gt(a):
    return lambda b: b > a


def m_ge(a):
    return lambda b: b >= a


def m_lt(a):
    return lambda b: b < a


def m_le(a):
    return lambda b: b <= a


def m_is(a):
    return lambda b: a is b


def m_nis(a):
    return lambda b: a is not b


def m_eq(a):
    return lambda b: a == b


def m_neq(a):
    return lambda b: a != b


def m_len(a):
    return lambda b: len(b) == a


def m_inst(a, **kwargs):
    if len(kwargs) > 0:
        return m_and(m_inst(a), m_dict(**kwargs))

    return lambda b: isinstance(b, a)


def m_contains(a):
    return lambda b: a in b


def m_ncontains(a):
    return lambda b: a not in b


def m_regex(a, flags=0):
    p = re.compile(a, flags)
    return lambda b: p.match(b)


shortcuts = {
    "is": m_is,
    "ni": m_nis,
    "eq": m_eq,
    "ne": m_neq,
    "cont": m_contains,
    "ncont": m_ncontains,
    "lt": m_lt,
    "le": m_le,
    "gt": m_gt,
    "ge": m_ge,
    "len": m_len,
    "inst": m_inst,
    "re": m_regex,
    "": lambda a: a,
}


@isolated_with_self(custom=False)
def m_dict(*, custom=True, self=None):
    _not_found = object()

    if custom:
        short = shortcuts.copy()
    else:
        short = shortcuts

    def _(**kwargs):
        newd = {}
        for k, v in kwargs.items():
            s = k.split('__')
            if len(s) == 2:
                newd[s[0]] = short[s[1]](v)
            else:
                if isinstance(v, type):
                    newd[k] = m_inst(v)
                elif callable(v):
                    newd[k] = v
                else:
                    newd[k] = m_eq(v)

        del kwargs

        def match(d):
            if isinstance(d, dict):
                for k, v in newd.items():
                    if not v(d.get(k, _not_found)):
                        return False
                return True
            else:
                for k, v in newd.items():
                    if not v(getattr(d, k, _not_found)):
                        return False
                return True

        return match

    if self is not None:
        _.gen = self
    if custom:
        _.shortcuts = short

    return _


# TODO: operators
def m_and(*matchers):
    def match(a):
        for m in matchers:
            if not m(a):
                return False
        return True

    return match


def m_or(*matchers):
    def match(a):
        for m in matchers:
            if m(a):
                return True

        return False

    return match


def m_all(matcher):
    def match(a, offset=0):
        for i in range(offset, len(a)):
            if not matcher(a[i]):
                return False
        return True

    return match


def m_any(matcher):
    def match(a, offset=0):
        for i in range(offset, len(a)):
            if matcher(a[i]):
                return True
        return False

    return match


def m_atleast(n, matcher):
    def match(a, offset=0):
        cnt = 0
        for i in range(offset, len(a)):
            if matcher(a[i]):
                cnt += 1
        return cnt >= n

    return match


def m_store(lst, matcher):
    def match(a):
        if matcher(a):
            lst.append(a)
            return True
        return False

    return match


def m_array(*args):
    def match(a, offset=0):
        if len(a) - offset < len(args):
            return False
        for i in range(0, len(args)):
            if not args[i](a[i + offset]):
                return False
        return True

    return match
