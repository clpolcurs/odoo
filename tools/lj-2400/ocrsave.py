"""ocrsave.py TOOLRESULT.json OUTDIR: saves the fileContent of a Drive read_file_content result in OUTDIR."""

import json
import os
import sys
from pathlib import Path

d = json.loads(Path(sys.argv[1]).read_text())
path = os.path.join(sys.argv[2], os.path.basename(d["title"]) + ".txt")
Path(path).write_text(d["fileContent"])
print(path, len(d["fileContent"]))
