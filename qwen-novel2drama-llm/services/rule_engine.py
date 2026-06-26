from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_scalar(value: str) -> Any:
    text = value.strip()
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "null":
        return None
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text.strip('"')


def minimal_yaml_load(path: Path) -> dict[str, Any]:
    """Small YAML loader for the limited default_rules.yaml shape.

    This avoids requiring PyYAML while keeping the rules file human-readable.
    It supports the current ruleset format only.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    root: dict[str, Any] = {"rules": []}
    current_rule: dict[str, Any] | None = None
    current_conditions: list[dict[str, Any]] | None = None
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if raw.startswith("ruleset_name:"):
            root["ruleset_name"] = raw.split(":", 1)[1].strip()
        elif raw.startswith("default_decision:"):
            root["default_decision"] = raw.split(":", 1)[1].strip()
        elif stripped.startswith("- id:"):
            current_rule = {"id": stripped.split(":", 1)[1].strip(), "when": {"all": []}}
            root["rules"].append(current_rule)
            current_conditions = current_rule["when"]["all"]
        elif current_rule is not None and stripped.startswith("description:"):
            current_rule["description"] = stripped.split(":", 1)[1].strip()
        elif current_rule is not None and stripped.startswith("priority:"):
            current_rule["priority"] = int(stripped.split(":", 1)[1].strip())
        elif current_rule is not None and stripped.startswith("effect:"):
            current_rule["effect"] = stripped.split(":", 1)[1].strip()
        elif current_rule is not None and stripped.startswith("reason:"):
            current_rule["reason"] = stripped.split(":", 1)[1].strip()
        elif current_rule is not None and stripped.startswith("- field:"):
            condition = {"field": stripped.split(":", 1)[1].strip()}
            current_conditions.append(condition)
        elif current_conditions and stripped.startswith("op:"):
            current_conditions[-1]["op"] = stripped.split(":", 1)[1].strip()
        elif current_conditions and stripped.startswith("value_from:"):
            current_conditions[-1]["value_from"] = stripped.split(":", 1)[1].strip()
        elif current_conditions and stripped.startswith("value:"):
            current_conditions[-1]["value"] = parse_scalar(stripped.split(":", 1)[1])
        i += 1
    return root


def load_rules(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return minimal_yaml_load(path)


def dotted_get(data: dict[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def condition_matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    left = dotted_get(context, condition.get("field", ""))
    op = condition.get("op")
    if "value_from" in condition:
        right = dotted_get(context, condition["value_from"])
    else:
        right = condition.get("value")
    if op == "exists":
        return left is not None
    if op == "missing":
        return left is None
    if op == "equals":
        return left == right
    if op == "not_equals":
        return left != right
    if op == "contains":
        return isinstance(left, list) and right in left
    if op == "not_contains":
        return not (isinstance(left, list) and right in left)
    if op == "greater_than":
        try:
            return float(left) > float(right)
        except (TypeError, ValueError):
            return False
    if op == "less_than":
        try:
            return float(left) < float(right)
        except (TypeError, ValueError):
            return False
    raise ValueError(f"unsupported rule operator: {op}")


def rule_matches(rule: dict[str, Any], context: dict[str, Any]) -> bool:
    conditions = rule.get("when", {}).get("all", [])
    return all(condition_matches(condition, context) for condition in conditions)


def decision_rank(effect: str) -> int:
    return {"allow": 0, "review": 1, "deny": 2}.get(effect, 0)


def evaluate_rules(ruleset: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    matches = []
    for rule in sorted(ruleset.get("rules", []), key=lambda item: int(item.get("priority", 0)), reverse=True):
        if rule_matches(rule, context):
            matches.append({
                "id": rule.get("id"),
                "effect": rule.get("effect", "allow"),
                "priority": rule.get("priority", 0),
                "reason": rule.get("reason"),
                "description": rule.get("description"),
            })
    if matches:
        final = max(matches, key=lambda item: decision_rank(item["effect"]))["effect"]
    else:
        final = ruleset.get("default_decision", "allow")
    return {
        "decision": final,
        "matched_rules": matches,
        "ruleset_name": ruleset.get("ruleset_name"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", default="configs/rules/default_rules.yaml")
    parser.add_argument("--context", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    ruleset = load_rules(Path(args.rules))
    context = json.loads(Path(args.context).read_text(encoding="utf-8"))
    result = evaluate_rules(ruleset, context)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["decision"] != "deny" else 2


if __name__ == "__main__":
    raise SystemExit(main())
