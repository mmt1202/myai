from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

PUBLIC_PATHS = {"/health", "/v1/health", "/docs", "/openapi.json"}

PATH_SCOPE_RULES = [
    ("GET", "/v1/skills/list", "skills:read"),
    ("POST", "/v1/skills/call", "skills:call"),
    ("GET", "/v1/mcp/tools", "mcp:read"),
    ("POST", "/v1/mcp/call", "mcp:call"),
    ("POST", "/v1/memory/search", "memory:read"),
    ("POST", "/v1/memory/write", "memory:write"),
    ("POST", "/v1/rules/evaluate", "rules:evaluate"),
    ("POST", "/v1/agent/run", "agent:run"),
    ("POST", "/v1/chat", "model:invoke"),
    ("POST", "/v1/reason", "model:invoke"),
    ("POST", "/v1/multimodal/analyze", "model:invoke"),
    ("POST", "/v1/route", "model:route"),
    ("POST", "/v1/token/count", "foundation:read"),
    ("POST", "/v1/cost/estimate", "foundation:read"),
]


class AuthError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 403) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "status_code": self.status_code}


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def load_key_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"auth_name": "empty", "keys": []}
    return json.loads(path.read_text(encoding="utf-8"))


def auth_required_from_env() -> bool:
    value = os.environ.get("FOUNDATION_AUTH_REQUIRED", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def key_store_path_from_env(project_root: Path) -> Path:
    configured = os.environ.get("FOUNDATION_API_KEYS")
    if configured:
        return Path(configured)
    return project_root / "configs" / "auth" / "api_keys.json"


def required_scope_for(method: str, path: str) -> str | None:
    if path in PUBLIC_PATHS:
        return None
    normalized_method = method.upper()
    for rule_method, rule_path, scope in PATH_SCOPE_RULES:
        if normalized_method == rule_method and path == rule_path:
            return scope
    if path.startswith("/v1/"):
        return "foundation:read"
    return None


def find_key_record(store: dict[str, Any], api_key: str) -> dict[str, Any] | None:
    digest = hash_api_key(api_key)
    for item in store.get("keys", []):
        candidate = str(item.get("sha256") or "")
        if candidate and hmac.compare_digest(candidate, digest):
            return item
    return None


def scope_allowed(record: dict[str, Any], required_scope: str | None) -> bool:
    if not required_scope:
        return True
    scopes = set(record.get("scopes") or [])
    return "*" in scopes or required_scope in scopes


def workspace_allowed(record: dict[str, Any], workspace_id: str | None) -> bool:
    if not workspace_id:
        return True
    workspaces = set(record.get("workspaces") or [])
    return "*" in workspaces or workspace_id in workspaces


def authorize_api_key(store: dict[str, Any], api_key: str | None, *, required_scope: str | None = None, workspace_id: str | None = None) -> dict[str, Any]:
    if not api_key:
        raise AuthError("auth_required", "missing API key", status_code=401)
    record = find_key_record(store, api_key)
    if not record:
        raise AuthError("permission_denied", "invalid API key", status_code=401)
    if record.get("status") != "active":
        raise AuthError("permission_denied", "API key is not active", status_code=403)
    if not scope_allowed(record, required_scope):
        raise AuthError("permission_denied", f"missing required scope: {required_scope}", status_code=403)
    if not workspace_allowed(record, workspace_id):
        raise AuthError("permission_denied", f"workspace is not allowed: {workspace_id}", status_code=403)
    return {
        "key_id": record.get("key_id"),
        "owner_id": record.get("owner_id"),
        "workspace_id": workspace_id,
        "scopes": record.get("scopes") or [],
        "workspaces": record.get("workspaces") or [],
        "metadata": record.get("metadata") or {},
    }


def anonymous_context() -> dict[str, Any]:
    return {"key_id": "anonymous", "owner_id": None, "workspace_id": None, "scopes": [], "workspaces": []}


def build_auth_context(
    *,
    method: str,
    path: str,
    api_key: str | None,
    workspace_id: str | None,
    store: dict[str, Any],
    auth_required: bool,
) -> dict[str, Any]:
    required_scope = required_scope_for(method, path)
    if required_scope is None:
        return {**anonymous_context(), "required_scope": required_scope, "auth_required": auth_required, "public": True}
    if not auth_required and not api_key:
        return {**anonymous_context(), "required_scope": required_scope, "auth_required": False, "public": False}
    context = authorize_api_key(store, api_key, required_scope=required_scope, workspace_id=workspace_id)
    context["required_scope"] = required_scope
    context["auth_required"] = auth_required
    context["public"] = False
    return context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hash-key", default=None)
    parser.add_argument("--store", default="configs/auth/api_keys.json")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--method", default="GET")
    parser.add_argument("--path", default="/v1/health")
    parser.add_argument("--workspace-id", default=None)
    args = parser.parse_args()
    if args.hash_key:
        print(hash_api_key(args.hash_key))
        return 0
    store = load_key_store(Path(args.store))
    try:
        context = build_auth_context(
            method=args.method,
            path=args.path,
            api_key=args.api_key,
            workspace_id=args.workspace_id,
            store=store,
            auth_required=True,
        )
        print(json.dumps({"authorized": True, "context": context}, ensure_ascii=False, indent=2))
        return 0
    except AuthError as exc:
        print(json.dumps({"authorized": False, "error": exc.to_dict()}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
