# Py'ns

*Py'nstrumentation* could help you give your code more expressiveness.

This is an attempt at providing macro support to python. However, the core features are still in progress. (the project has just started) Even the way macros are called to modify the code should soon be reviewed, so I don't encourage trying to implement things with that yet.

A lot of the code isn't documented yet, but this should be coming soon, just like more tests.

A short example with the actual implementation:

```python
# import the macros
from pyns.macros import *

if with_macros(__name__, globals(), locals()):
    # you code using macros

    # string interpolation
    x = 3
    print(s["{x}"])  # 3

    # quoting
    print(ast_repr(q[2])) # Num(2)
    print(ast_repr(q[test()])) # Call(Name('test', Load()))

```

This is kind of standards macros at the moment.
