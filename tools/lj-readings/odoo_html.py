"""What Odoo stores for a markup sent through the API, computed with Odoo's own sanitizer.

The API puts the markup into Html fields, whose sanitizer reads `<<kỳ nghỉ hè>>` as the tag `<kỳ>` and drops it (the
markers of kanji survive: `<` must be followed by a letter to start a tag). Markups are therefore sent with `<<`
escaped, the way the Odoo editor stores them, and checked against html_sanitize of odoo/tools/mail.py in this
repository, loaded without the rest of Odoo.
"""

import importlib.util
import re
import sys
import types
from pathlib import Path

import markupsafe

MAIL = Path(__file__).resolve().parents[2] / "odoo" / "tools" / "mail.py"
# the options of an Html field (odoo/orm/fields_textual.py)
FIELD = dict(
    silent=True,
    sanitize_tags=True,
    sanitize_attributes=True,
    sanitize_style=False,
    sanitize_form=True,
    sanitize_conditional_comments=True,
    output_method="html",
    strip_style=False,
    strip_classes=False,
)


def _mail():
    misc = types.ModuleType("odoo.tools.misc")
    misc.html_escape = markupsafe.escape  # the only part of misc that mail.py needs at import time
    for name, module in (("odoo", None), ("odoo.tools", None), ("odoo.tools.misc", misc)):
        sys.modules.setdefault(name, module or types.ModuleType(name))
    sys.modules["odoo.tools"].misc = sys.modules["odoo.tools.misc"]
    spec = importlib.util.spec_from_file_location("odoo.tools.mail", MAIL)
    mail = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mail)
    return mail


html_sanitize = _mail().html_sanitize


def to_send(markup):
    """The markup as it is sent: `<<` escaped. `>` never opens a tag, so `>>` can stay."""
    return markup.replace("<<", "&lt;&lt;")


def to_source(stored):
    """What the API shows for a stored value (custom_addons/learning_japanese/services/markup.py): `<` pairs are
    taken from the right, so `&lt;&lt;&lt;質問 - しつもん&gt;&gt;&gt;` is `&lt;<<質問 - しつもん>>&gt;`."""

    def pairs(run):
        count = len(run.group(0)) // len("&lt;")
        return "&lt;" * (count % 2) + "<<" * (count // 2)

    return re.sub(r"(?:&lt;){2,}", pairs, stored).replace("&gt;&gt;", ">>")


def read_back(markup):
    """The markup the API will show after this markup is written."""
    return to_source(str(html_sanitize(to_send(markup), **FIELD)))
