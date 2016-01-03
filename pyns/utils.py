
def isolated(f):
    return f()


def isolated_with_self(**kwargs):
    def decorate(f):
        return f(self=f, **kwargs)

    return decorate
