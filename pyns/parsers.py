import re


# a parser is a function of str, offset, returns (node, length)


#  ######  ##     ##  ######      ###    ########
# ##    ## ##     ## ##    ##    ## ##   ##     ##
# ##       ##     ## ##         ##   ##  ##     ##
#  ######  ##     ## ##   #### ##     ## ########
#       ## ##     ## ##    ##  ######### ##   ##
# ##    ## ##     ## ##    ##  ##     ## ##    ##
#  ######   #######   ######   ##     ## ##     ##


class SugarParser:

    def __init__(self, parser):
        self._parser = parser
        if not isinstance(parser, self.__class__):
            setattr(parser, '_', parser)

    def __call__(self, str, offset=0):
        return self._parser(str, offset)

    def __neg__(self):
        return +self.no()

    @property
    def _(self):
        return self._parser

    # println
    def println(self, format="%r"):
        p = self._parser
        @SugarParser
        def parser(str, offset=0):
            n, l = p(str, offset)
            if l < 0:
                return n, l
            print(n)
            return n, l
        return parser


    # trans
    def trans(self, cls, ret_length=False, on_failure=False):
        p = self._parser
        @SugarParser
        def parse(str, offset=0):
            n, l = p(str, offset)
            if l < 0 and not on_failure:
                return n, l
            ret = trans(str, n, offset, l)
            return (ret, l) if ret_length is False else ret

        return parse

    # str
    def str(self):
        p = self._parser
        @SugarParser
        def parse(str, offset=0):
            n, l = p(str, offset)
            if l < 0:
                return n, l
            return str[offset:offset+l], l

        return parse

    def try_replace(self, p2):
        p = self._parser
        @SugarParser
        def parser(str, offset=0):
            n1, l1 = p(str, offset)
            n2, l2 = p2(str, offset)
            if n1 != n2 or l1 != l2:
                print("orig: %s\nnew : %s\n" % (n1, n2))
            return n1, l1

        return parser

    def tuple(self):
        p = self._parser
        @SugarParser
        def parse(str, offset=0):
            n, l = p(str, offset)
            if l < 0:
                return n, l
            return tuple(n), l

        return parse

    def no(self):
        p = self._parser
        @SugarParser
        def parse(str, offset=0):
            n, l = p(str, offset)
            if l < 0:
                return None, 0
            return None, -1

        return parse

class DeferredParser(SugarParser):
    def __init__(self, l):
        def replace_and_parse(str, offset=0):
            self._parser = p = l()
            return p(str, offset)
        super(DeferredParser, self).__init__(replace_and_parse)

    def __setattr__(self, key, value):
        if key == 'parser':
            self._parser = value
            return
        return SugarParser.__setattr__(self, key, value)

    def __pos__(self):
        self('')
        if not hasattr(self._parser, '__pos__'):
            return self._parser
        return +self._parser

# ##    ##  #######  ########
# ###   ## ##     ##    ##
# ####  ## ##     ##    ##
# ## ## ## ##     ##    ##
# ##  #### ##     ##    ##
# ##   ### ##     ##    ##
# ##    ##  #######     ##

def p_not(parser):
    @SugarParser
    def parse(str, offset=0):
        n, l = parser(str, offset)
        if l < 0:
            return None, 0
        return None, -1

    return parse

# ########  ########  ######   ######## ##     ##
# ##     ## ##       ##    ##  ##        ##   ##
# ##     ## ##       ##        ##         ## ##
# ########  ######   ##   #### ######      ###
# ##   ##   ##       ##    ##  ##         ## ##
# ##    ##  ##       ##    ##  ##        ##   ##
# ##     ## ########  ######   ######## ##     ##

def p_regex(regex, flags=0):
    """ p_regex returns a parser that matches a regex at the current offset """
    r = re.compile(regex, flags=flags)

    @SugarParser
    def parse(str, offset=0):
        match = r.match(str, offset)
        if match is None:
            return None, -1
        match = match.group(0)
        return match, len(match)

    return parse

#  ######  ######## ########
# ##    ##    ##    ##     ##
# ##          ##    ##     ##
#  ######     ##    ########
#       ##    ##    ##   ##
# ##    ##    ##    ##    ##
#  ######     ##    ##     ##

def p_str(s):
    """ p_str returns a parser that matches a string at the current offset """
    @SugarParser
    def parse(str, offset=0):
        if not str.startswith(s, offset):
            return None, -1
        else:
            return s, len(s)

    return parse

# ##     ## ##     ## ##       ########
# ###   ### ##     ## ##          ##
# #### #### ##     ## ##          ##
# ## ### ## ##     ## ##          ##
# ##     ## ##     ## ##          ##
# ##     ## ##     ## ##          ##
# ##     ##  #######  ########    ##

def p_mult(parser, *, separator=p_regex(r'[\t\n ]*'), min_len=0):
    parsers = [parser._ for parser in parsers]
    @SugarParser
    def parse(str, offset=0):
        nodes = []
        length = 0
        wl = 0
        while True:
            n, l = parser(str, offset+length)
            if l < 0:
                length -= wl
                break
            length += l
            nodes.append(n)

            w, wl = separator(str, offset+length)
            if wl < 0:
                break
            length += wl

        if len(nodes) < min_len:
            return None, -1
        return nodes, length

    return parse

#  #######  ########  ########
# ##     ## ##     ##    ##
# ##     ## ##     ##    ##
# ##     ## ########     ##
# ##     ## ##           ##
# ##     ## ##           ##
#  #######  ##           ##

def p_opt(parser, node=None):
    """
        p_opt returns an optional parser. That means that if parser doesn't match the string, a default node is returned
    """
    @SugarParser
    def parse(str, offset=0):
        return node, 0
    return p_or(parser, parse)


#    ###    ##    ## ########
#   ## ##   ###   ## ##     ##
#  ##   ##  ####  ## ##     ##
# ##     ## ## ## ## ##     ##
# ######### ##  #### ##     ##
# ##     ## ##   ### ##     ##
# ##     ## ##    ## ########

_all = object()

def p_and(*parsers, extract=None, keep=_all):
    """
        p_and returns a parser that matches a sequence of parser at the current offset. If one fails, the generated
        parser returns an error.
    """
    parsers = [parser._ for parser in parsers]
    @SugarParser
    def parse(str, offset=0):
        nodes = [None for i in range(0, len(parsers) if keep is _all else len(keep))]
        length = 0
        for i, p in enumerate(parsers):
            (n, l) = p(str, offset+length)
            if l < 0:
                return None, -1

            if keep is _all:
                nodes[i] = n
            elif i in keep:
                nodes[keep.index(i)] = n

            length += l

        return nodes if extract is None else nodes[extract], length

    return parse

# ########  ##     ## ########     ###     ######  ########
# ##     ## ##     ## ##     ##   ## ##   ##    ## ##
# ##     ## ##     ## ##     ##  ##   ##  ##       ##
# ########  ######### ########  ##     ##  ######  ######
# ##        ##     ## ##   ##   #########       ## ##
# ##        ##     ## ##    ##  ##     ## ##    ## ##
# ##        ##     ## ##     ## ##     ##  ######  ########

def p_phrase(*parsers, extract=None, keep=_all, wp=p_regex(r'[\t\n ]*')):
    """
        p_phrase returns a parser that returns the result of a sequence of parser. Each call to a parser is preceded
        by a call to the wp (whitespace parser). The whitespaces are discarded from the resulting list, and as soon as
        one fails, returns None, -1 (error)
    """
    parsers = [parser._ for parser in parsers]
    @SugarParser
    def parse(str, offset=0):
        nodes = [None for i in range(0, len(parsers) if keep is _all else len(keep))]
        length = 0
        for i, p in enumerate(parsers):
            w, l = wp(str, offset+length)
            if l < 0:
                break
            length += l

            n, l = p(str, offset+length)
            if l < 0:
                return None, -1

            if keep is _all:
                nodes[i] = n
            elif i in keep:
                nodes[keep.index(i)] = n

            length += l

        return nodes if extract is None else nodes[extract], length

    return parse

#  #######  ########
# ##     ## ##     ##
# ##     ## ##     ##
# ##     ## ########
# ##     ## ##   ##
# ##     ## ##    ##
#  #######  ##     ##

def p_or(*parsers):
    """p_or returns a parser that returns the result of the first successful parser on the given string at the given
    offset
    """
    parsers = [parser._ for parser in parsers]
    @SugarParser
    def parse(str, offset=0):
        for p in parsers:
            (n, l) = p(str, offset)
            if l < 0:
                continue
            return n, l
        return None, -1

    return parse

# ########  ######## ######## ######## ########
# ##     ## ##       ##       ##       ##     ##
# ##     ## ##       ##       ##       ##     ##
# ##     ## ######   ######   ######   ########
# ##     ## ##       ##       ##       ##   ##
# ##     ## ##       ##       ##       ##    ##
# ########  ######## ##       ######## ##     ##

def p_defer(parser=None):
    return DeferredParser(parser)
