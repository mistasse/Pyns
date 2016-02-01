import config
from pyns.macros import *
from unittest import TestCase, main

def assertRepr(a, b):
    str_a = ast_repr(a)
    str_b = ast_repr(b)
    assert str_a == str_b, '%s should be the same as %s' % (str_a, str_b)


@compile_with_macros(globals(), locals())
class asrteq(Macro):

    def matchers(self, name):
        return {
            Call: m_dict(func=m_inst(Name, id=name), args=list, args__len=2)
        }

    def instr_Call(self, node: Call):
        a, b = node.args
        n = q[self.assertEqual(u[a], u[b])]
        return self.transform(n)


@compile_with_macros(globals(), locals())
class asrtast(Macro):

    def matchers(self, name):
        return {
            Call: m_dict(func=m_inst(Name, id=name), args=list, args__len=2)
        }

    def instr_Call(self, node: Call):
        a, b = node.args
        n = q[assertRepr(u[a], u[b])]
        return self.transform(n)


@macro_block
def execute(var, items, body, **kwargs):
    return body


if __name__ == '__main__' and with_macros(__name__, globals(), locals()):

    class BlockTest(TestCase):

        def test_block_macro(self):
            with q as [a, b], None:
                pass
                pass
            assert isinstance(a, Pass) and isinstance(b, Pass)

            try:
                with execute, None:
                    raise AssertionError
            except AssertionError:
                assert True
            else:
                assert False, 'The block should have raised an exception'

    class JustDefinedTest(TestCase):

        def test_asrteq(self):
            asrteq(1, 1)
            try:
                asrteq(1, 2)
                asrteq('1st', '2nd')
            except AssertionError:
                assert True
            else:
                assert False, 'asrteq should have thrown an error'

        def test_asrtast(self):
            asrtast(q[1], Num(1))
            try:
                asrtast(q[1], Num(2))
            except AssertionError:
                assert True
            else:
                assert False, 'asrtast should have thrown an error'

    class Test(TestCase):

        def test_interpolation(self):
            x = "test"
            asrteq(s['{x}'], x)
            asrteq(s['{x}{x}'], x*2)
            asrteq(s[x], x)

        def test_quote(self):
            x = 4
            asrtast(q[4], Num(4))
            asrtast(q[f(u[Num(x)])], Call(Name('f', Load()), [Num(4)], []))

        def test_ast(self):
            x = 4
            asrtast(q[x], Name('x', Load()))
            asrtast(q[ast[x]], Num(4))

        def test_quicklambdas(self):
            asrteq(f[_0*_1](4, 2), 8)
            asrtast(f[q[x]](), q[x])

            args_f = f["{}".format(_macro_args)]
            asrteq(args_f(), '()')
            asrteq(args_f(0), '(0,)')
            asrteq(args_f(0, 2), '(0, 2)')

        def test_mix(self):
            x = "lol"
            asrteq(f[s[x]](), x)
            asrteq(f[s["lol"]](), x)
            asrteq(f[_0](s["{x}"]), x)

            asrtast(q[ast[f[3]()]], Num(3))
            asrteq(q[u[f[1]]](), 1)

            asrteq(f[s["{_macro_args}"]](), '()')

            try:
                asrteq(f[s["{x}"]](), x)
            except KeyError:
                assert True
            else:
                assert False, '''Shouldn't have found x in the local context of the quick lambda'''

    main()
