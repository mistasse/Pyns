import config
import pyns
from pyns.utils import *
from pyns.parsers import *
from unittest import TestCase, main
from contextlib import contextmanager
import weakref
import gc


@contextmanager
def should_fail():
    try:
        yield
    except:
        assert True
    else:
        assert False, 'Should have failed'


class TestParsers(TestCase):

    def test_rootparser(self):
        a = p_str('ok')
        assert a._ is not a
        assert a._('ok') == ('ok', 2) == a('ok')
        assert a._('zok') == a('zok')

    def test_phrase(self):
        parser = p_phrase(p_str('ok'), p_regex(r'\s*'))
        assert parser('ok') == (['ok', ''], 2)
        assert parser('okok') == (['ok', ''], 2)
        assert parser('') == (None, -1)

        parser = p_phrase(p_str('ok'), p_regex(r'\s*'), keep=[]).tuple()
        assert parser('ok') == ((), 2)

    def test_or(self):
        parser = p_or(p_str('1'), p_str('2'))
        assert parser('2') == ('2', 1)
        assert parser('1') == ('1', 1)
        assert parser('3') == (None, -1)


class MemoryTest(TestCase):

    def test_ref(self):
        tmpSugarParser = pyns.parsers.SugarParser
        def _SugarParser(*args, **kwargs):
            ret = tmpSugarParser(*args, **kwargs)
            refs.add(ret)
            return ret

        with tmp_attr(pyns.parsers, SugarParser=_SugarParser):
            refs = weakref.WeakSet()

            a = p_str('x')
            a = a._
            b = p_phrase(p_str(''), p_str(''))._
            print(len(refs))
            gc.collect()
            assert len(refs) == 0


if __name__ == '__main__':
    main()
