import doctest
from IPython.core.magic import (register_line_magic, register_cell_magic,
                                register_line_cell_magic)

import IPython

template = """
def f():
	\"\"\"
	%s
	\"\"\"
"""

@register_cell_magic
def rundoctest(line,cell):
	cell = template%"\n\t".join(cell.split("\n"))
	ishell = IPython.get_ipython()
	ishell.ex(cell)
	glob = ishell.ev("doctest.run_docstring_examples(f,globals())")