"""
Auto-generate methods for PARI functions.
"""

#*****************************************************************************
#       Copyright (C) 2015 Jeroen Demeyer <jdemeyer@cage.ugent.be>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#                  http://www.gnu.org/licenses/
#*****************************************************************************

from __future__ import print_function
import os, re

from sage_setup.autogen.pari.args import (PariArgumentGEN,
        PariInstanceArgument)
from sage_setup.autogen.pari.parser import (sage_src_pari,
        read_pari_desc, read_decl, parse_prototype)


gen_banner = '''# This file is auto-generated by {}

cdef class gen_auto(RingElement):
    """
    Part of the :class:`gen` class containing auto-generated functions.

    This class is not meant to be used directly, use the derived class
    :class:`gen` instead.
    """
'''.format(__file__)

instance_banner = '''# This file is auto-generated by {}

cdef class PariInstance_auto(ParentWithBase):
    """
    Part of the :class:`PariInstance` class containing auto-generated functions.

    You must never use this class directly (in fact, Sage may crash if
    you do), use the derived class :class:`PariInstance` instead.
    """
'''.format(__file__)


function_re = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
function_blacklist = {"O"}  # O(p^e) needs special parser support

class PariFunctionGenerator(object):
    """
    Class to auto-generate ``auto_gen.pxi`` and ``auto_instance.pxi``.

    The PARI file ``pari.desc`` is read and all suitable PARI functions
    are written as methods of either :class:`gen` or
    :class:`PariInstance`.
    """
    def __init__(self):
        self.declared = read_decl()
        self.gen_filename = os.path.join(sage_src_pari(), 'auto_gen.pxi')
        self.instance_filename = os.path.join(sage_src_pari(), 'auto_instance.pxi')

    def can_handle_function(self, function, cname, **kwds):
        """
        Can we actually handle this function in Sage?

        EXAMPLES::

            sage: from sage_setup.autogen.pari.generator import PariFunctionGenerator
            sage: G = PariFunctionGenerator()
            sage: G.can_handle_function("bnfinit", "bnfinit0", **{"class":"basic"})
            True
            sage: G.can_handle_function("_bnfinit", "bnfinit0", **{"class":"basic"})
            False
            sage: G.can_handle_function("bnfinit", "BNFINIT0", **{"class":"basic"})
            False
            sage: G.can_handle_function("bnfinit", "bnfinit0", **{"class":"hard"})
            False
        """
        if function in function_blacklist:
            # Blacklist specific troublesome functions
            return False
        if not function_re.match(function):
            # Not a legal function name, like "!_"
            return False
        if cname not in self.declared:
            # PARI function not in Sage's decl.pxi or declinl.pxi
            return False
        cls = kwds.get("class", "unknown")
        sec = kwds.get("section", "unknown")
        if cls not in ("basic", "highlevel"):
            # Different class: probably something technical or
            # gp2c-specific
            return False
        if sec == "programming/control":
            # Skip if, return, break, ...
            return False
        return True

    def handle_pari_function(self, function, cname="", prototype="", help="", doc="", **kwds):
        r"""
        Handle one PARI function: decide whether or not to add the
        function to Sage, in which file (as method of :class:`gen` or
        of :class:`PariInstance`?) and call :meth:`write_method` to
        actually write the code.

        EXAMPLES::

            sage: from sage_setup.autogen.pari.parser import read_pari_desc
            sage: from sage_setup.autogen.pari.generator import PariFunctionGenerator
            sage: G = PariFunctionGenerator()
            sage: G.gen_file = sys.stdout
            sage: G.instance_file = sys.stdout
            sage: G.handle_pari_function("bnfinit",
            ....:     cname="bnfinit0", prototype="GD0,L,DGp",
            ....:     help=r"bnfinit(P,{flag=0},{tech=[]}): compute...",
            ....:     doc=r"Doc: initializes a \var{bnf} structure",
            ....:     **{"class":"basic", "section":"number_fields"})
                def bnfinit(P, long flag=0, tech=None, long precision=0):
                    cdef GEN _P = P.g
                    cdef GEN _tech = NULL
                    if tech is not None:
                        tech = objtogen(tech)
                        _tech = (<gen>tech).g
                    precision = prec_bits_to_words(precision)
                    pari_catch_sig_on()
                    cdef GEN _ret = bnfinit0(_P, flag, _tech, precision)
                    return pari_instance.new_gen(_ret)
            <BLANKLINE>
            sage: G.handle_pari_function("ellmodulareqn",
            ....:     cname="ellmodulareqn", prototype="LDnDn",
            ....:     help=r"ellmodulareqn(N,{x},{y}): return...",
            ....:     doc=r"return a vector [\kbd{eqn},$t$] where \kbd{eqn} is...",
            ....:     **{"class":"basic", "section":"elliptic_curves"})
                def ellmodulareqn(self, long N, x=None, y=None):
                    cdef PariInstance pari_instance = <PariInstance>self
                    cdef long _x = -1
                    if x is not None:
                        _x = pari_instance.get_var(x)
                    cdef long _y = -1
                    if y is not None:
                        _y = pari_instance.get_var(y)
                    pari_catch_sig_on()
                    cdef GEN _ret = ellmodulareqn(N, _x, _y)
                    return pari_instance.new_gen(_ret)
            <BLANKLINE>
            sage: G.handle_pari_function("setrand",
            ....:     cname="setrand", prototype="vG",
            ....:     help=r"setrand(n): reset the seed...",
            ....:     doc=r"reseeds the random number generator...",
            ....:     **{"class":"basic", "section":"programming/specific"})
                def setrand(n):
                    cdef GEN _n = n.g
                    pari_catch_sig_on()
                    setrand(_n)
                    pari_instance.clear_stack()
            <BLANKLINE>
        """
        if not self.can_handle_function(function, cname, **kwds):
            return

        try:
            args, ret = parse_prototype(prototype, help)
        except NotImplementedError:
            return  # Skip unsupported prototype codes

        # Is the first argument a GEN?
        if len(args) > 0 and isinstance(args[0], PariArgumentGEN):
            # If yes, write a method of the gen class.
            cargs = args
            f = self.gen_file
        else:
            # If no, write a method of the PariInstance class.
            # Parse again with an extra "self" argument.
            args, ret = parse_prototype(prototype, help, [PariInstanceArgument()])
            cargs = args[1:]
            f = self.instance_file

        self.write_method(function, cname, args, ret, cargs, f)

    def write_method(self, function, cname, args, ret, cargs, file):
        """
        Write Cython code with a method to call one PARI function.

        INPUT:

        - ``function`` -- name for the method

        - ``cname`` -- name of the PARI C library call

        - ``args``, ``ret`` -- output from ``parse_prototype``,
          including the initial args like ``self``

        - ``cargs`` -- like ``args`` but excluding the initial args

        - ``file`` -- a file object where the code should be written to
        """
        protoargs = ", ".join(a.prototype_code() for a in args)
        callargs = ", ".join(a.call_code() for a in cargs)

        s = "    def {function}({protoargs}):\n"
        for a in args:
            s += a.convert_code()
        s += "        pari_catch_sig_on()\n"
        s += ret.assign_code("{cname}({callargs})")
        s += ret.return_code()

        s = s.format(function=function, protoargs=protoargs, cname=cname, callargs=callargs)
        print (s, file=file)

    def __call__(self):
        """
        Top-level function to generate the auto-generated files.
        """
        D = read_pari_desc()
        D = sorted(D.values(), key=lambda d: d['function'])

        self.gen_file = open(self.gen_filename, 'w')
        self.gen_file.write(gen_banner)
        self.instance_file = open(self.instance_filename, 'w')
        self.instance_file.write(instance_banner)

        for v in D:
            self.handle_pari_function(**v)

        self.gen_file.close()
        self.instance_file.close()