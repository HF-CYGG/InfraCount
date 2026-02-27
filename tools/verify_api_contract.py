import argparse
import json
import difflib
import os
import sys
from typing import Any, Dict


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def _normalize(contract: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(contract or {})
    c.pop("generated_at", None)
    return c


def main() -> int:
    from tools.freeze_api_contract import build_contract

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--frozen",
        default="docs/frozen_api_contract_v1.json",
        help="frozen json file path",
    )
    args = parser.parse_args()

    frozen_path = str(args.frozen)
    with open(frozen_path, "r", encoding="utf-8") as f:
        frozen = json.load(f)

    current = build_contract()

    frozen_n = _normalize(frozen)
    current_n = _normalize(current)

    if frozen_n == current_n:
        return 0

    frozen_s = json.dumps(frozen_n, ensure_ascii=False, indent=2, sort_keys=True).splitlines(keepends=True)
    current_s = json.dumps(current_n, ensure_ascii=False, indent=2, sort_keys=True).splitlines(keepends=True)
    diff = difflib.unified_diff(
        frozen_s,
        current_s,
        fromfile=frozen_path,
        tofile="current",
    )
    for line in diff:
        print(line, end="")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
