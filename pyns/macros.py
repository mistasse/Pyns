from .core import *
from .matching import *

# TODO: Rewrite with macros and embedded nodes

@isolated
def _q_specific():
    u_matcher = m_inst(Subscript, value=m_inst(Name, id='u'))
    ast_matcher = m_inst(Subscript, value=m_inst(Name, id='ast'))

    def q_specific(node):
        if u_matcher(node):
            return q.macro_visitor.visit(node.slice.value)
        if ast_matcher(node):
            return Call(Name('ast_genast', Load()), [q.macro_visitor.visit(node.slice.value)], [])
        return None

    return q_specific


q = MacroMixer()

@q.register
@macro_inline
def q(node, macro_visitor, **kwargs):
    with tmp_attr(q, macro_visitor=macro_visitor):
        return ast_genast(node, _q_specific)


@q.register
@macro_block
def q(var, items, body, macro_visitor, **kwargs):
    with tmp_attr(q, macro_visitor=macro_visitor):
        return Assign(targets=[var], value=ast_genast(body, _q_specific))


@macro_inline
@compile_with_macros(globals(), locals())
def s(node, **kwargs):
    return q[u[node].format(**locals())]


@macro_inline(allow_interferences=True)
@instantiate
@compile_with_macros(globals(), locals())
class f(NodeTransformer):
    def __init__(self):
        self.var = m_dict(id__re=r'^\_[0-9]+$')

    def visit_Name(self, node):
        if self.var(node):
            return locate(q[_macro_args[u[Num(int(node.id[1:]))]]], node)
        return self.generic_visit(node)

    def __call__(self, node, **kwargs):
        # we convert the inner variables
        value = self.visit(node)
        # we build the anonymous function
        n = q[lambda *_macro_args: u[value]]
        return n
