from ast import *
from .matching import *
from functools import wraps

import re
import sys
import inspect
import collections
import io


_ast = None


def macros_enabled():
    return _ast is not None


class Macro:
    """A macro consists into matchers and instrumentation functions.

    Here's a very simple example:

    class q(Macro):
        matchers = {
            Subscript: lambda name: m_dict(value=m_inst(Name, id=name))
        }

        def instr_Subscript(self, node):
            return locate(ast_genast(node), node)
    """
    matchers = {
        # UnaryOp: lambda name: m_dict(m_inst(), id=name),
        # ...
    }

    can_interfere = False

    def __init__(self, name, **kwargs):
        self.name = name
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.matchers = {k: v(name) for k, v in self.matchers.items()}

    def instr(self, node):
        method = 'instr_'+node.__class__.__name__
        visitor = getattr(self, method)
        return visitor(node)


def macro_inline(f=None, *, allow_interferences=False):
    def _(f):
        class _InlineMacro(Macro):
            can_interfere = allow_interferences
            matchers = {
                Subscript: lambda name: m_dict(value=m_inst(Name, id=name))
            }

            def __init__(self, name, **kwargs):
                Macro.__init__(self, name)
                self.kwargs = kwargs

            def instr_Subscript(self, node):
                return f(node.slice.value, **self.kwargs)

        return _InlineMacro

    if f is not None:
        return _(f)
    return _


def locate(newnode, oldnode):
    return fix_missing_locations(copy_location(newnode, oldnode))


class MacroVisitor(NodeTransformer):
    """Given a dictionary, registers the macros using their name, then it is
    able to apply all the modifications.
    """

    def __init__(self, candidates):
        self.macros = collections.defaultdict(list)
        for name, cls in candidates.items():
            if isinstance(cls, type) and issubclass(cls, Macro):
                current = cls(name, macro_visitor=self)
                for nodecls, matcher in current.matchers.items():
                    self.macros[nodecls].append((matcher, current))

    def visit(self, node):
        for matcher, macro in self.macros[node.__class__]:
            if matcher(node):
                if macro.can_interfere:
                    node = self.generic_visit(node)
                return locate(macro.instr(node), node)
        return self.generic_visit(node)


def without_macros():
    return _ast is None


def with_macros(name, globals, locals):
    """Usage:
        from macros import f

        # ... Defining my custom macros

        if with_macros(__name__, globals(), locals()):
            # ... My code to be processed by macros
    """
    global _ast
    _mod = sys.modules[name]

    # _ast is not defined yet, we want to take it and expand macros
    if _ast is None:
        # we take the whole module, parse it
        _ast = parse(inspect.getsource(_mod), _mod.__file__, 'exec')

        # we look for global macros, use them on the module using their name
        m = MacroVisitor(globals)
        _ast = m.visit(_ast)

        exec(compile(_ast, _mod.__file__, 'exec'), globals, locals)
        _ast = None
        return False
    # we are willing to execute the module body
    else:
        return True


_is_annot = re.compile(r'^\s*@')


def strip_decorators(src):
    # Add \n since cleandoc only acts from the second line, imagine we could have
    # def a():
    #   return x
    # a = mod(a)
    src = inspect.cleandoc('\n'+src).split('\n')

    # We just find the first line without annotation. The others one are already being executed on the result
    # of the modification
    i = 0
    while _is_annot.match(src[i]) is not None:
        i += 1
    return '\n'.join(src[i:])


def compile_with_macros(globals, locals):
    def _(f):
        # if macros are enabled, it has already been compiled
        if macros_enabled():
            return f

        # get the ast from the source of the function
        ast = parse(strip_decorators(inspect.getsource(f)))

        # we look for global macros, use them on the source using their name
        m = MacroVisitor(globals)
        ast = m.visit(ast)

        exec(compile(ast, f.__name__, 'exec'), globals, locals)
        return eval(f.__name__, globals, locals)

    return _

def ast_repr(thing, omit=None):
    """From an AST node, will build an expression that can be evaluated to build it.
    How is that useful?

    Imagine you type some code a+3 somewhere, and you want to recover the AST to manipulate it, like to replace a by a
    constant. You can run

    eval(real_repr(ast.parse('a+3', mode='eval').body))
                         |------ Provides the nodes
             |------ converts the nodes to a string
      |--- creates new nodes

    to obtain the AST node.
    """
    if omit is not None:
        o = omit(thing)
        if o is not None:
            return o
    if isinstance(thing, AST):
        fields = [ast_repr(b, omit) for _, b in iter_fields(thing)]
        return '%s(%s)' % (thing.__class__.__name__, ', '.join(fields))
    elif isinstance(thing, list):
        return '[%s]' % ', '.join((ast_repr(t, omit) for t in thing))
    return repr(thing)


def unparse(tree):
    """We generate the python code from its AST
    """
    if isinstance(tree, list):
        return [CodeGenerator().visit(t) for t in tree]
    return CodeGenerator().visit(tree)


def _ast_genast(tree, specific=None):
    """Generates an AST that, when evaluated, will return the AST it as been generated from.
    as_is_matcher is a function returning true when we don't want to expand the inner expression anymore.
    """
    if isinstance(tree, AST):
        if specific is not None:
            val = specific(tree)
            if val is not None:
                return val
        params = []
        for _, value in iter_fields(tree):
            params.append(ast_genast(value, specific))
        return Call(func=Name(tree.__class__.__name__, Load()), args=params, keywords=[])
    if isinstance(tree, list):
        elems = []
        for e in tree:
            elems.append(ast_genast(e, specific))
        return List(elems, Load())
    if tree is None or tree is True or tree is False:
        return NameConstant(tree)
    if isinstance(tree, (int, float, complex)):
        return Num(tree)
    if isinstance(tree, str):
        return Str(tree)
    return tree

def ast_genast(tree, specific=None):
    return _ast_genast(tree, specific)

def comp_expr(ast, name=None):
    if name is None:
        name = unparse_code(ast)
    return compile(ast if isinstance(ast, Expression) else Expression(ast), name, 'eval')

def comp_block(ast, name=None):
    if name is None:
        name = unparse_code(ast)
    return compile(ast, '\n'.join(name), 'exec')

#    ###     ######  ########    ##     ##  #######  ########  #### ######## #### ######## ########
#   ## ##   ##    ##    ##       ###   ### ##     ## ##     ##  ##  ##        ##  ##       ##     ##
#  ##   ##  ##          ##       #### #### ##     ## ##     ##  ##  ##        ##  ##       ##     ##
# ##     ##  ######     ##       ## ### ## ##     ## ##     ##  ##  ######    ##  ######   ########
# #########       ##    ##       ##     ## ##     ## ##     ##  ##  ##        ##  ##       ##   ##
# ##     ## ##    ##    ##       ##     ## ##     ## ##     ##  ##  ##        ##  ##       ##    ##
# ##     ##  ######     ##       ##     ##  #######  ########  #### ##       #### ######## ##     ##


def ASTModifier(f):
    """Makes a function taking one argument an AST modifier.
    """
    def _(to_modify):
        ast = getattr(to_modify, 'ast', None)
        if ast is None:
            src = strip_decorators(inspect.getsource(to_modify))
            # now, we parse to get the AST
            ast = parse(src, '<{}>'.format(to_modify.__name__), 'exec')

        ast = f(ast)
        exec(compile(ast, to_modify.__name__, 'exec'))
        res = wraps(to_modify)(eval(to_modify.__name__))
        res.ast = ast
        return res

    return _


def no_ast(f):
    """removes the ast of a function when she has finished going through its modifiers
    """
    delattr(f, 'ast')
    return f


#  ######   #######  ########  ########     ######   ######## ##    ## ######## ########     ###    ########  #######  ########
# ##    ## ##     ## ##     ## ##          ##    ##  ##       ###   ## ##       ##     ##   ## ##      ##    ##     ## ##     ##
# ##       ##     ## ##     ## ##          ##        ##       ####  ## ##       ##     ##  ##   ##     ##    ##     ## ##     ##
# ##       ##     ## ##     ## ######      ##   #### ######   ## ## ## ######   ########  ##     ##    ##    ##     ## ########
# ##       ##     ## ##     ## ##          ##    ##  ##       ##  #### ##       ##   ##   #########    ##    ##     ## ##   ##
# ##    ## ##     ## ##     ## ##          ##    ##  ##       ##   ### ##       ##    ##  ##     ##    ##    ##     ## ##    ##
#  ######   #######  ########  ########     ######   ######## ##    ## ######## ##     ## ##     ##    ##     #######  ##     ##


class CodeGenerator(NodeVisitor):

    def shiftright(self,        nodes):             return '\n'.join('    '+l for n in nodes for l in self.visit(n).split('\n'))
    def visit_or_None(self,     node):              return self.visit(node) if node is not None else ''  # Mostly for slices

    def visit_Module(self,      node: Module):      return '\n'.join(self.visit(b) for b in node.body)
    def visit_Import(self,      node: Import):      return 'import %s' % ', '.join((self.visit(n) for n in node.names))
    def visit_ImportFrom(self,  node: ImportFrom):  return 'from %s%s import %s' % ('.'*node.level, node.module, ', '.join(self.visit(n) for n in node.names))
    def visit_alias(self,       node: alias):       return '%s as %s' if node.asname else node.name
    def visit_Assign(self,      node: Assign):      return '%s = %s' % (', '.join((self.visit(t) for t in node.targets)), self.visit(node.value))
    def visit_With(self, node: With): return 'with %s:\n%s' % (', '.join(self.visit(n) for n in node.items), self.shiftright(node.body))
    def visit_withitem(self,    node: withitem):    return '%s as %s' % (self.visit(node.context_expr), self.visit(node.optional_vars)) if node.optional_vars else self.visit(node.context_expr)

    def visit_If(self, node: If):
        ret = 'if %s:\n%s' % (self.visit(node.test), self.shiftright(node.body))
        if not node.orelse:
            return ret
        return '%s\nelse:\n%s' % (ret, self.shiftright(node.orelse))

    def visit_While(self, node: While):
        ret = 'while %s:\n%s' % (self.visit(node.test), self.shiftright(node.body))
        if not node.orelse:
            return ret
        return '%s\nelse:\n%s' % (ret, self.shiftright(node.orelse))

    def visit_For(self, node: For):
        ret = 'for %s in %s:\n%s' % (self.visit(node.target), self.visit(node.iter), self.shiftright(node.body))
        if not node.orelse:
            return ret
        return '%s\nelse:\n%s' % (ret, self.shiftright(node.orelse))

    def visit_FunctionDef(self, node: FunctionDef):
        ret = ''
        for d in node.decorator_list:
            ret += '@%s\n' % (self.visit(d))
        ret += 'def %s(%s):\n%s' % (node.name, self.visit_arguments(node.args), self.shiftright(node.body))
        return ret

    def visit_arguments(self,   node: arguments):
        lst = []
        for i, a in enumerate(node.args):
            a_str = self.visit(a)
            if len(node.defaults) > i and node.defaults[i]:
                a_str += '=%s' % self.visit(node.defaults[i])
            lst.append(a_str)

        if node.vararg:
            lst.append('*%s' % self.visit(node.vararg))

        for i, kw in enumerate(node.kwonlyargs):
            a_str = self.visit(kw)

            if len(node.kw_defautls) > i and node.kw_defaults[i]:
                a_str += '=%s' % self.visit(node.kw_defaults[i])

            lst.append(a_str)

        if node.kwarg:
            lst.append('**%s' % self.visit(node.kwarg))

        return ', '.join(lst)

    def visit_ClassDef(self, node: ClassDef):
        ret = ''
        for d in node.decorator_list:
            ret += '@%s\n' % self.visit(d)

        return '%sclass %s(%s):\n%s%s' % (ret, node.name, ', '.join(self.visit(b) for b in node.bases), self.shiftright(node.keywords), self.shiftright(node.body))

    def visit_comprehension(self, node: comprehension):
        ret = 'for %s in %s' % (self.visit(node.target), self.visit(node.iter))
        for if_ in node.ifs:
            ret = '%s if %s' % (ret, self.visit(if_))
        return ret

    def visit_IfExp(self,       node: IfExp):       return '(%s if %s else %s)' % (self.visit(node.body), self.visit(node.test), self.visit(node.orelse))
    def visit_ListComp(self,    node: ListComp):    return '[%s %s]' % (self.visit(node.elt), ' '.join(self.visit(c) for c in node.generators))
    def visit_GeneratorExp(self,node: GeneratorExp):return '(%s %s)' % (self.visit(node.elt), ' '.join(self.visit(c) for c in node.generators))
    def visit_SetComp(self,     node: SetComp):     return '{%s %s}' % (self.visit(node.elt), ' '.join(self.visit(c) for c in node.generators))
    def visit_DictComp(self,    node: DictComp):    return '{%s: %s %s}' % (self.visit(node.key), self.visit(node.value), ' '.join(self.visit(c) for c in node.generators))

    def visit_arg(self,         node: arg):         return '%s:%s' % (node.arg, self.visit(node.annotation)) if node.annotation else node.arg
    def visit_Return(self,      node: Return):      return 'return %s' % self.visit(node.value) if node.value else 'return'
    def visit_Call(self,        node: Call):        return '%s(%s)' % (self.visit(node.func), ', '.join([self.visit(a) for a in node.args]+ [self.visit(kw) for kw in node.keywords]))
    def visit_keyword(self,     node: keyword):     return '%s=%s' % (node.arg, self.visit(node.value))

    def visit_Attribute(self,   node: Attribute):   return '%s.%s' % (self.visit(node.value), node.attr)
    def visit_Subscript(self,   node: Subscript):   return '%s[%s]' % (self.visit(node.value), self.visit(node.slice))
    def visit_Index(self,       node: Index):       return self.visit(node.value)
    def visit_Slice(self,       node: Slice):       return '%s:%s:%s' % (self.visit_or_None(node.lower), self.visit_or_None(node.upper), self.visit_or_None(node.step))

    def visit_List(self,        node: List):        return '[%s]' % (', '.join(self.visit(e) for e in node.elts))
    def visit_Tuple(self,       node: Tuple):       return '(%s)' % (', '.join(self.visit(e) for e in node.elts)) if len(node.elts) != 1 else '(%s,)' % self.visit(node.elts[0])
    def visit_Set(self,         node: Set):         return '{%s}' % (', '.join(self.visit(e) for e in node.elts))
    def visit_Expr(self,        node: Expr):        return self.visit(node.value)
    def visit_Str(self,         node: Str):         return '"%s"' % node.s
    def visit_Name(self,        node: Name):        return '%s' % node.id
    def visit_Num(self,         node: Num):         return '%d' % node.n

    def visit_AugAssign(self,   node: AugAssign):   return '%s %s= %s' % (self.visit(node.target), self.visit(node.op), self.visit(node.value))

    def visit_BinOp(self,       node: BinOp):       return '(%s %s %s)' % (self.visit(node.left), self.visit(node.op), self.visit(node.right))
    def visit_Add(self,         node: Add):         return '+'
    def visit_Sub(self,         node: Sub):         return '-'
    def visit_Mult(self,        node: Mult):        return '*'
    def visit_Mod(self,         node: Mod):         return '%'
    def visit_Div(self,         node: Div):         return '/'
    def visit_FloorDiv(self,    node: FloorDiv):    return '//'
    def visit_LShift(self,      node: LShift):      return '<<'
    def visit_RShift(self,      node: RShift):      return '>>'
    def visit_MatMult(self,     node):              return '@'

    def visit_BitAnd(self,      node: BitAnd):      return '&'
    def visit_BitOr(self,       node: BitOr):       return '|'
    def visit_BitXor(self,      node: BitXor):      return '^'

    def visit_BoolOp(self,      node: BoolOp):      return '(%s)' % (' {} '.format(self.visit(node.op)).join(self.visit(v) for v in node.values))
    def visit_And(self,         node: And):         return 'and'
    def visit_Or(self,          node: Or):          return 'or'

    def visit_Compare(self,     node: Compare):     return '(%s %s)' % (self.visit(node.left), ' '.join('%s %s' % (self.visit(op), self.visit(right)) for op, right in zip(node.ops, node.comparators)))
    def visit_Eq(self,          node: Eq):          return '=='
    def visit_NotEq(self,       node: NotEq):       return '!='
    def visit_Gt(self,          node: Gt):          return '>'
    def visit_GtE(self,         node: GtE):         return '>='
    def visit_Lt(self,          node: Lt):          return '<'
    def visit_LtE(self,         node: LtE):         return '<='
    def visit_Is(self,          node: Is):          return 'is'
    def visit_IsNot(self,       node: IsNot):       return 'is not'
    def visit_In(self,          node: In):          return 'in'
    def visit_NotIn(self,       node: NotIn):       return 'not in'

    def visit_NameConstant(self,node: NameConstant):return str(node.value)
    def visit_Global(self,      node: Global):      return 'global %s' % ', '.join(node.names)
