from .core import *
from .matching import *


# TODO: Rewrite with macros and embedded nodes


class _Embedded(AST):
    def __init__(self, node):
        self.node = node


@macro_inline
def u(node, container, transform, **kwargs):
    if not q.into:
        raise AssertionError('Cannot use the u macro without being in a quote')
    return _Embedded(locate(transform(node), container))


@macro_inline
def ast(node, container, transform, **kwargs):
    if not q.into:
        raise AssertionError('Cannot use the ast macro without being in a quote')
    return _Embedded(locate(Call(Name('ast_genast', Load()), [transform(node)], []), container))


def _q_specific(node):
    if isinstance(node, _Embedded):
        return node.node
    return None


q = MacroMixer()
q.into = False


@q.register
@macro_inline
def q(node, container, transform, **kwargs):
    print(ast_repr(node))
    with tmp_attr(q, into=True):
        return locate(ast_genast(transform(node), _q_specific), container)


@q.register
@macro_block
def q(var, items, body, container, transform, **kwargs):
    with tmp_attr(q, into=True):
        return locate(Assign(targets=[var], value=ast_genast(transform(body), _q_specific)), container)


@isolated
@compile_with_macros(globals(), locals())
def test():
    print(ast_repr(q[2*u[2]]))


@macro_inline
@compile_with_macros(globals(), locals())
def s(node, container, transform, **kwargs):
    return locate(q[u[transform(node)].format(**locals())], container)


@macro_inline
@instantiate
@compile_with_macros(globals(), locals())
class f(NodeTransformer):
    def __init__(self):
        self.var = m_dict(id__re=r'^\_[0-9]+$')

    def visit_Name(self, node):
        if self.var(node):
            return locate(q[_macro_args[u[Num(int(node.id[1:]))]]], node)
        return self.generic_visit(node)

    def __call__(self, node, container, transform, **kwargs):
        # we convert the inner variables
        value = self.visit(transform(node))
        # we build the anonymous function
        n = q[lambda *_macro_args: u[value]]
        return locate(n, container)
