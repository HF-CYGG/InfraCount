import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def _infer_auth(path: str, methods: List[str]) -> str:
    p = str(path or "")
    if p == "/api/v1/auth/login":
        return "public"
    if p == "/api/v1/auth/logout":
        return "optional_session"
    if p in {"/api/v1/auth/me", "/api/v1/auth/password"}:
        return "session"
    if p.startswith("/api/v1/users"):
        return "admin"
    if p == "/api/v1/system/status":
        return "admin"
    return "public"


def build_contract() -> Dict[str, Any]:
    from api.main import app

    routes: List[Dict[str, Any]] = []
    for r in app.routes:
        methods = sorted([m for m in (getattr(r, "methods", None) or [])])
        if not methods:
            continue
        endpoint = getattr(r, "endpoint", None)
        endpoint_ref: Optional[str] = None
        if endpoint is not None:
            mod = getattr(endpoint, "__module__", "")
            qn = getattr(endpoint, "__qualname__", getattr(endpoint, "__name__", ""))
            endpoint_ref = f"{mod}:{qn}"

        path = getattr(r, "path", "")
        include_in_schema = bool(getattr(r, "include_in_schema", True))
        name = str(getattr(r, "name", "") or "")
        routes.append(
            {
                "path": path,
                "methods": methods,
                "name": name,
                "endpoint": endpoint_ref,
                "include_in_schema": include_in_schema,
                "auth": _infer_auth(path, methods),
            }
        )

    routes.sort(key=lambda x: (x["path"], ",".join(x["methods"]), x.get("name") or ""))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app": {"title": getattr(app, "title", ""), "version": getattr(app, "version", "")},
        "auth_model": {
            "session": {"cookie": "session_token", "max_age_sec": 7 * 24 * 3600},
            "admin": {"requires": "session + role==admin"},
        },
        "routes": routes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default="docs/frozen_api_contract_v1.json",
        help="output json file path",
    )
    args = parser.parse_args()

    contract = build_contract()
    out_path = str(args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(contract, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
