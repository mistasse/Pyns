from .core import *
from .matching import *


def trans_macro(transformer):
    """What is a trans_macro? This is a macro that creates a transformer for every instrumentation it has to make, and
    then just calls it to return the modified tree
    """
    class _Macro(Macro):
        def manipulate(self, name, tree):
            return transformer(name).visit(tree)

    return _Macro()


u = ast = None


def locate(newnode, oldnode):
    return fix_missing_locations(copy_location(newnode, oldnode))


@trans_macro
class q(NodeTransformer):

    def __init__(self, name):
        self.matcher = m_dict(value=m_inst(Name, id=name))
        self.u = m_inst(Subscript, value=m_inst(Name, id='u'))
        self.ast = m_inst(Subscript, value=m_inst(Name, id='ast'))

    def omit_u(self, x):
        if self.u(x):
            return locate(x.slice.value, x)
        if self.ast(x):
            # Could not use AST in this file if it was in the following form!
            # return locate(q[ast_genast(u[x.slice.value])], x)
            # But would give
            return locate(Call(Name('ast_genast', Load()), [x.slice.value], []), x)
        return None

    def visit_Subscript(self, node):
        if self.matcher(node):
            return locate(ast_genast(node.slice.value, self.omit_u), node)
        return self.generic_visit(node)

if with_macros(__name__, globals(), locals()):

    @trans_macro
    class s(NodeTransformer):
        def __init__(self, name):
            self.matcher = m_dict(value=m_inst(Name, id=name))

        def visit_Subscript(self, node):
            if self.matcher(node):
                n = q[u[node.slice.value].format(**locals())]
                return locate(n, node)
            return self.generic_visit(node)

    @trans_macro
    class f(NodeTransformer):
        def __init__(self, name):
            self.matcher = m_dict(value=m_inst(Name, id=name))
            self.var = m_dict(id__re=r'^\_[0-9]+$')
            self.into = False

        def visit_Name(self, node):
            if self.into and self.var(node):
                return locate(q[_macro_args[u[Num(int(node.id[1:]))]]], node)
            return self.generic_visit(node)

        def visit_Subscript(self, node):
            if self.matcher(node):
                # we convert the inner variables
                self.into = True
                value = self.visit(node.slice.value)
                self.into = False

                # we build the anonymous function
                n = q[lambda *_macro_args: u[value]]
                return locate(n, node)
            return self.generic_visit(node)
