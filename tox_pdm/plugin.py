from tox import __version__ as TOX_VERSION

if TOX_VERSION[0] == "4":
    from tox_pdm.plugin4 import *  # noqa
else:
    from tox_pdm.plugin3 import *  # noqa
