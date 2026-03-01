#!/usr/bin/env bash
set -euo pipefail

echo "== Dockerless validation started =="
echo "Timestamp: $(date -Iseconds)"

echo
echo "[1/4] Tool availability"
for cmd in docker python3; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "  - $cmd: OK ($(command -v "$cmd"))"
  else
    echo "  - $cmd: MISSING"
  fi
done

echo
echo "[2/4] Docker Compose config validation"
docker compose -f docker-compose.yml config --no-interpolate >/tmp/docker-compose.rendered.yml
echo "  - docker compose config: OK"
echo "  - rendered file: /tmp/docker-compose.rendered.yml"

echo
echo "[3/4] YAML syntax validation"
python3 - <<'PY'
from pathlib import Path
import yaml

target = Path("docker-compose.yml")
yaml.safe_load(target.read_text(encoding="utf-8"))
print("  - PyYAML parse: OK")
PY

echo
echo "[4/4] Python dependency validation"
if [[ -x ".venv/bin/pip" ]]; then
  .venv/bin/pip install --dry-run -r requirements.txt >/tmp/pip-dry-run.log
  echo "  - pip dry-run: OK (details: /tmp/pip-dry-run.log)"
else
  echo "  - .venv/bin/pip not found, skipped pip dry-run"
fi

python3 - <<'PY'
import ast
import re
import sys
from pathlib import Path

reqs = []
for raw in Path("requirements.txt").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    reqs.append(re.split(r"[<>=!~\[]", line, 1)[0].strip().lower().replace("_", "-"))
req_set = set(reqs)

local_modules = {"backend"}
for py in Path("backend").rglob("*.py"):
    local_modules.add(py.stem)
for pkg in Path("backend").rglob("__init__.py"):
    local_modules.add(pkg.parent.name)

stdlib = {
    "asyncio", "collections", "contextlib", "datetime", "functools", "json", "logging",
    "operator", "os", "pathlib", "re", "sys", "typing", "unittest", "inspect"
}
optional_runtime = {"IPython"}
mapping = {
    "pydantic_settings": "pydantic-settings",
    "langchain_openai": "langchain-openai",
    "langchain_core": "langchain-core",
    "dotenv": "python-dotenv",
}

imports = set()
for py in Path("backend").rglob("*.py"):
    if "tests" in py.parts:
        continue
    tree = ast.parse(py.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.add(node.module.split(".")[0])

missing = []
for mod in sorted(imports):
    if mod in stdlib or mod in local_modules:
        continue
    pkg = mapping.get(mod, mod.lower().replace("_", "-"))
    if mod in optional_runtime:
        continue
    if pkg not in req_set:
        missing.append((mod, pkg))

if missing:
    print("  - import coverage: FAIL")
    for mod, pkg in missing:
        print(f"    * missing dependency for import '{mod}': expected '{pkg}'")
    sys.exit(1)

print("  - import coverage: OK")
PY

echo
echo "== Dockerless validation completed successfully =="
