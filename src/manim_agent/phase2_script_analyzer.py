"""Static checks for Phase 2 generated Manim scripts."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

StaticValue = float | int | str | bool | None | list[Any] | tuple[Any, ...]
_UNRESOLVED = object()

UNSTABLE_TEXT_GLYPHS = ("²", "³", "√", "≤", "≥")
RANDOM_REARRANGE_PATTERNS = (
    "offset = half_c *",
    "center+[offset",
    "center + [offset",
    "center+[-offset",
    "center + [-offset",
)


@dataclass
class Phase2ScriptAnalysis:
    """Result of static script checks."""

    scene_file: str
    scene_class: str
    expected_beat_ids: list[str]
    method_names: list[str]
    construct_calls: list[str]
    estimated_duration_seconds: float
    beat_duration_seconds: dict[str, float] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    syntax_error: dict[str, Any] | None = None

    @property
    def accepted(self) -> bool:
        return not self.issues

    def model_dump(self) -> dict[str, Any]:
        return asdict(self) | {"accepted": self.accepted}


def analyze_phase2_script(
    *,
    scene_file: str | None,
    scene_class: str | None,
    build_spec: dict[str, Any] | None,
    target_duration_seconds: int | None,
    output_dir: str,
) -> Phase2ScriptAnalysis:
    """Analyze generated Phase 2 script structure before Phase 3 review."""
    root = Path(output_dir).resolve()
    script_path = _resolve_script_path(scene_file, root)
    expected_beat_ids = _extract_expected_beat_ids(build_spec)
    scene_class_name = scene_class or "GeneratedScene"
    issues: list[str] = []
    warnings: list[str] = []

    if script_path is None or not script_path.exists():
        return Phase2ScriptAnalysis(
            scene_file=str(script_path or ""),
            scene_class=scene_class_name,
            expected_beat_ids=expected_beat_ids,
            method_names=[],
            construct_calls=[],
            estimated_duration_seconds=0.0,
            beat_duration_seconds={},
            issues=["scene_file does not point to a real script."],
        )

    source = script_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        syntax_error = _syntax_error_details(exc, source)
        location = ""
        if syntax_error.get("line") is not None:
            location = f" at line {syntax_error['line']}"
            if syntax_error.get("offset") is not None:
                location += f", column {syntax_error['offset']}"
        return Phase2ScriptAnalysis(
            scene_file=str(script_path),
            scene_class=scene_class_name,
            expected_beat_ids=expected_beat_ids,
            method_names=[],
            construct_calls=[],
            estimated_duration_seconds=0.0,
            beat_duration_seconds={},
            issues=[f"scene.py is not valid Python{location}: {exc.msg}."],
            syntax_error=syntax_error,
        )

    scene_node = _find_class(tree, scene_class_name)
    if scene_node is None:
        issues.append(f"Scene class `{scene_class_name}` is missing.")
        scene_node = _find_first_class(tree)

    method_nodes = _class_methods(scene_node) if scene_node is not None else {}
    method_names = list(method_nodes)
    construct = method_nodes.get("construct")
    construct_calls = _self_method_calls(construct) if construct is not None else []
    if construct is None:
        issues.append("construct() method is missing.")

    beat_method_names = [name for name in method_names if name.startswith("beat_")]
    if expected_beat_ids:
        missing = [beat_id for beat_id in expected_beat_ids if beat_id not in method_nodes]
        if missing:
            issues.append(
                "Missing beat-first methods for build_spec beat ids: " + ", ".join(missing)
            )
        out_of_order = _construct_order_issue(expected_beat_ids, construct_calls)
        if out_of_order:
            issues.append(out_of_order)
    elif not beat_method_names:
        issues.append("No beat_* methods found; Phase 2 must use beat-first structure.")

    if construct is not None:
        non_beat_calls = [
            call
            for call in construct_calls
            if call not in expected_beat_ids and call.startswith(("beat", "_beat"))
        ]
        if non_beat_calls:
            warnings.append(
                "construct() calls non-build_spec beat-like methods: " + ", ".join(non_beat_calls)
            )

    for beat_id in expected_beat_ids:
        method = method_nodes.get(beat_id)
        if method is not None and not _method_has_completion_hold(method):
            issues.append(f"Beat method `{beat_id}` lacks a completion hold wait >= 0.3s.")

    beat_durations = _estimate_beat_duration_seconds(
        method_nodes=method_nodes,
        expected_beat_ids=expected_beat_ids,
    )
    estimated_duration = (
        round(sum(beat_durations.values()), 3)
        if beat_durations
        else (_estimate_duration_seconds(scene_node) if scene_node is not None else 0.0)
    )
    if target_duration_seconds and target_duration_seconds > 0:
        minimum = target_duration_seconds * 0.6
        if estimated_duration < minimum:
            issues.append(
                f"Estimated script duration {estimated_duration:.1f}s is below "
                f"60% of target duration {target_duration_seconds}s."
            )

    glyph_issues = _unstable_text_glyph_issues(tree)
    warnings.extend(glyph_issues)

    if _looks_like_random_rearrangement(source):
        issues.append(
            "Script appears to use hard-coded offset-based rearrangement targets; "
            "geometry proofs must construct a clean final assembled state first."
        )

    return Phase2ScriptAnalysis(
        scene_file=str(script_path),
        scene_class=scene_class_name,
        expected_beat_ids=expected_beat_ids,
        method_names=method_names,
        construct_calls=construct_calls,
        estimated_duration_seconds=estimated_duration,
        beat_duration_seconds=beat_durations,
        issues=issues,
        warnings=warnings,
    )


def persist_phase2_script_analysis(
    analysis: Phase2ScriptAnalysis,
    *,
    output_dir: str,
    filename: str = "phase2_script_analysis.json",
) -> str:
    """Persist Phase 2 script analysis for debugging and task history."""
    path = Path(output_dir).resolve() / filename
    path.write_text(
        json.dumps(analysis.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path)


def _resolve_script_path(scene_file: str | None, root: Path) -> Path | None:
    if not scene_file:
        return None
    path = Path(scene_file)
    if path.is_absolute() or path.exists():
        return path
    return root / path


def _syntax_error_details(exc: SyntaxError, source: str) -> dict[str, Any]:
    line_text = exc.text
    if not line_text and exc.lineno is not None:
        lines = source.splitlines()
        if 1 <= exc.lineno <= len(lines):
            line_text = lines[exc.lineno - 1]
    return {
        "message": exc.msg,
        "line": exc.lineno,
        "offset": exc.offset,
        "end_line": exc.end_lineno,
        "end_offset": exc.end_offset,
        "text": line_text.rstrip("\n") if line_text else None,
    }


def _extract_expected_beat_ids(build_spec: dict[str, Any] | None) -> list[str]:
    if not build_spec:
        return []
    beats = build_spec.get("beats") or []
    beat_ids: list[str] = []
    for beat in beats:
        if isinstance(beat, dict):
            beat_id = str(beat.get("id") or "").strip()
            if beat_id:
                beat_ids.append(_safe_method_name(beat_id))
    return beat_ids


def _safe_method_name(value: str) -> str:
    normalized = re.sub(r"\W+", "_", value.strip())
    if not normalized:
        return "beat"
    if normalized[0].isdigit():
        normalized = f"beat_{normalized}"
    return normalized


def _find_class(tree: ast.AST, name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _find_first_class(tree: ast.AST) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            return node
    return None


def _class_methods(node: ast.ClassDef | None) -> dict[str, ast.FunctionDef]:
    if node is None:
        return {}
    return {item.name: item for item in node.body if isinstance(item, ast.FunctionDef)}


def _self_method_calls(node: ast.FunctionDef | None) -> list[str]:
    if node is None:
        return []
    calls: list[str] = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        func = item.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "self"
        ):
            calls.append(func.attr)
    return calls


def _construct_order_issue(expected: list[str], calls: list[str]) -> str | None:
    positions: list[int] = []
    for beat_id in expected:
        try:
            positions.append(calls.index(beat_id))
        except ValueError:
            return f"construct() does not call beat method `{beat_id}`."
    if positions != sorted(positions):
        return "construct() does not call beat methods in build_spec order."
    return None


def _method_has_completion_hold(node: ast.FunctionDef) -> bool:
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        if not _is_self_method_call(item, "wait"):
            continue
        if not item.args:
            return True
        value = _literal_number(item.args[0])
        if value is not None and value >= 0.3:
            return True
    return False


def _estimate_duration_seconds(node: ast.ClassDef | None) -> float:
    if node is None:
        return 0.0
    total = 0.0
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        if _is_self_method_call(item, "wait"):
            total += _call_wait_duration(item)
        elif _is_self_method_call(item, "play"):
            total += _call_play_duration(item)
    return round(total, 3)


def _estimate_beat_duration_seconds(
    *,
    method_nodes: dict[str, ast.FunctionDef],
    expected_beat_ids: list[str],
) -> dict[str, float]:
    beat_ids = expected_beat_ids or [name for name in method_nodes if name.startswith("beat_")]
    durations: dict[str, float] = {}
    for beat_id in beat_ids:
        method = method_nodes.get(beat_id)
        if method is None:
            continue
        durations[beat_id] = _estimate_method_duration_seconds(
            method,
            method_nodes=method_nodes,
        )
    return durations


def _estimate_method_duration_seconds(
    node: ast.FunctionDef,
    *,
    method_nodes: dict[str, ast.FunctionDef] | None = None,
    env: dict[str, StaticValue] | None = None,
    call_stack: tuple[str, ...] = (),
) -> float:
    method_nodes = method_nodes or {}
    env = dict(env or {})
    total = 0.0
    for stmt in node.body:
        total += _estimate_stmt_duration_seconds(
            stmt,
            method_nodes=method_nodes,
            env=env,
            call_stack=call_stack + (node.name,),
        )
    return round(total, 3)


def _estimate_stmt_duration_seconds(
    stmt: ast.stmt,
    *,
    method_nodes: dict[str, ast.FunctionDef],
    env: dict[str, StaticValue],
    call_stack: tuple[str, ...],
) -> float:
    if isinstance(stmt, ast.Assign):
        value = _static_value(stmt.value, env)
        if value is not _UNRESOLVED:
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    env[target.id] = value
        return 0.0
    if isinstance(stmt, ast.AnnAssign):
        value = _static_value(stmt.value, env)
        if value is not _UNRESOLVED and isinstance(stmt.target, ast.Name):
            env[stmt.target.id] = value
        return 0.0
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return _estimate_call_duration_seconds(
            stmt.value,
            method_nodes=method_nodes,
            env=env,
            call_stack=call_stack,
        )
    if isinstance(stmt, ast.For):
        iterable = _static_iterable(stmt.iter, env)
        if not isinstance(iterable, (list, tuple)):
            return 0.0
        total = 0.0
        for item in iterable:
            loop_env = dict(env)
            _bind_loop_target(stmt.target, item, loop_env)
            for child in stmt.body:
                total += _estimate_stmt_duration_seconds(
                    child,
                    method_nodes=method_nodes,
                    env=loop_env,
                    call_stack=call_stack,
                )
        return total
    if isinstance(stmt, ast.If):
        condition = _static_truth(stmt.test, env)
        if condition is True:
            branch_env = dict(env)
            return sum(
                _estimate_stmt_duration_seconds(
                    child,
                    method_nodes=method_nodes,
                    env=branch_env,
                    call_stack=call_stack,
                )
                for child in stmt.body
            )
        if condition is False:
            branch_env = dict(env)
            return sum(
                _estimate_stmt_duration_seconds(
                    child,
                    method_nodes=method_nodes,
                    env=branch_env,
                    call_stack=call_stack,
                )
                for child in stmt.orelse
            )
        body_env = dict(env)
        body_total = sum(
            _estimate_stmt_duration_seconds(
                child,
                method_nodes=method_nodes,
                env=body_env,
                call_stack=call_stack,
            )
            for child in stmt.body
        )
        else_env = dict(env)
        else_total = sum(
            _estimate_stmt_duration_seconds(
                child,
                method_nodes=method_nodes,
                env=else_env,
                call_stack=call_stack,
            )
            for child in stmt.orelse
        )
        return max(body_total, else_total)
    return 0.0


def _estimate_call_duration_seconds(
    node: ast.Call,
    *,
    method_nodes: dict[str, ast.FunctionDef],
    env: dict[str, StaticValue],
    call_stack: tuple[str, ...],
) -> float:
    if _is_self_method_call(node, "wait"):
        return _call_wait_duration(node, env)
    if _is_self_method_call(node, "play"):
        return _call_play_duration(node, env)

    func = node.func
    if not (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "self"
    ):
        return 0.0
    method = method_nodes.get(func.attr)
    if method is None or method.name in call_stack:
        return 0.0

    helper_env: dict[str, StaticValue] = {}
    params = [arg.arg for arg in method.args.args if arg.arg != "self"]
    defaults = method.args.defaults
    if defaults:
        default_params = params[-len(defaults) :]
        for param, default in zip(default_params, defaults, strict=False):
            value = _static_value(default, env)
            if value is not _UNRESOLVED:
                helper_env[param] = value
    for index, arg_node in enumerate(node.args):
        if index >= len(params):
            break
        value = _static_value(arg_node, env)
        if value is not _UNRESOLVED:
            helper_env[params[index]] = value
    for keyword in node.keywords:
        if keyword.arg is None:
            continue
        value = _static_value(keyword.value, env)
        if value is not _UNRESOLVED:
            helper_env[keyword.arg] = value

    return _estimate_method_duration_seconds(
        method,
        method_nodes=method_nodes,
        env=helper_env,
        call_stack=call_stack,
    )


def _call_wait_duration(node: ast.Call, env: dict[str, StaticValue] | None = None) -> float:
    if not node.args:
        return 1.0
    return _static_number(node.args[0], env or {}) or 0.0


def _call_play_duration(node: ast.Call, env: dict[str, StaticValue] | None = None) -> float:
    for keyword in node.keywords:
        if keyword.arg == "run_time":
            return _static_number(keyword.value, env or {}) or 0.0
    return 1.0


def _is_self_method_call(node: ast.Call, method_name: str) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == method_name
        and isinstance(func.value, ast.Name)
        and func.value.id == "self"
    )


def _literal_number(node: ast.AST) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _literal_number(node.operand)
        return -value if value is not None else None
    return None


def _static_iterable(node: ast.AST, env: dict[str, StaticValue]) -> StaticValue | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "enumerate"
        and node.args
    ):
        iterable = _static_value(node.args[0], env)
        if isinstance(iterable, (list, tuple)):
            return list(enumerate(iterable))
        return None
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "range"
        and 1 <= len(node.args) <= 3
    ):
        values = [_static_number(arg, env) for arg in node.args]
        if all(value is not None and value.is_integer() for value in values):
            int_values = [int(value) for value in values if value is not None]
            return list(range(*int_values))
        return None
    value = _static_value(node, env)
    return value if value is not _UNRESOLVED else None


def _bind_loop_target(
    target: ast.expr,
    value: StaticValue,
    env: dict[str, StaticValue],
) -> None:
    if isinstance(target, ast.Name):
        env[target.id] = value
        return
    if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (tuple, list)):
        for child_target, child_value in zip(target.elts, value, strict=False):
            _bind_loop_target(child_target, child_value, env)


def _static_number(node: ast.AST, env: dict[str, StaticValue]) -> float | None:
    value = _static_value(node, env)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _static_value(node: ast.AST | None, env: dict[str, StaticValue]) -> StaticValue | object:
    if node is None:
        return _UNRESOLVED
    if isinstance(node, ast.Constant) and (
        isinstance(node.value, (int, float, str, bool)) or node.value is None
    ):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _static_number(node.operand, env)
        return -value if value is not None else _UNRESOLVED
    if isinstance(node, ast.IfExp):
        condition = _static_truth(node.test, env)
        if condition is True:
            return _static_value(node.body, env)
        if condition is False:
            return _static_value(node.orelse, env)
        return _UNRESOLVED
    if isinstance(node, ast.Name):
        return env.get(node.id, _UNRESOLVED)
    if isinstance(node, ast.List):
        values = [_static_value(item, env) for item in node.elts]
        if all(value is not _UNRESOLVED for value in values):
            return values
    if isinstance(node, ast.Tuple):
        values = tuple(_static_value(item, env) for item in node.elts)
        if all(value is not _UNRESOLVED for value in values):
            return values
    return _UNRESOLVED


def _static_truth(node: ast.AST, env: dict[str, StaticValue]) -> bool | None:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = _static_truth(node.operand, env)
        return None if value is None else not value
    if isinstance(node, ast.Name):
        value = env.get(node.id, _UNRESOLVED)
        return None if value is _UNRESOLVED else bool(value)
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
        left = _static_value(node.left, env)
        right = _static_value(node.comparators[0], env)
        if left is _UNRESOLVED or right is _UNRESOLVED:
            return None
        op = node.ops[0]
        if isinstance(op, ast.Is):
            return left is right
        if isinstance(op, ast.IsNot):
            return left is not right
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
    value = _static_value(node, env)
    return None if value is _UNRESOLVED else bool(value)


def _unstable_text_glyph_issues(tree: ast.AST) -> list[str]:
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_name_call(node, "Text"):
            continue
        for arg in node.args[:1]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                glyphs = [glyph for glyph in UNSTABLE_TEXT_GLYPHS if glyph in arg.value]
                if glyphs:
                    issues.append(
                        "Unstable math glyph(s) inside Text(): "
                        + ", ".join(glyphs)
                        + f" in {arg.value!r}."
                    )
    return issues


def _is_name_call(node: ast.Call, name: str) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id == name


def _looks_like_random_rearrangement(source: str) -> bool:
    compact = source.replace(" ", "")
    for pattern in RANDOM_REARRANGE_PATTERNS:
        if pattern.replace(" ", "") in compact:
            return True
    return False
