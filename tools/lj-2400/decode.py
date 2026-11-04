"""decode.py TOOLRESULT.json OUTDIR: writes the base64 content of a Drive download to OUTDIR/<title>."""

import base64
import json
import os
import sys
from pathlib import Path

d = json.loads(Path(sys.argv[1]).read_text())
path = os.path.join(sys.argv[2], os.path.basename(d["title"]))
Path(path).write_bytes(base64.b64decode(d["content"]))
print(path, os.path.getsize(path))
