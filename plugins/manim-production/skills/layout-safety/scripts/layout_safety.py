"""Geometry-based layout safety helpers for Manim scenes.

Two-level detection:
  Level 1 — AABB (axis-aligned bounding box) fast pre-filter for all pairs.
  Level 2 — Boundary-point refinement using get_boundary_point() to confirm
           or reject AABB overlap reports, reducing false positives on
           circular / curved shapes.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import Enum
from importlib.util import module_from_spec, spec_from_file_location
from itertools import combinations
from pathlib import Path
from typing import Iterable

import numpy as np
from manim import DOWN, LEFT, RIGHT, UP, Mobject, Scene, config, tempconfig


@dataclass(frozen=True)
class Bounds2D:
    """Axis-aligned bounds for a mobject in scene coordinates."""

    left: float
    right: float
    bottom: float
    top: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom


@dataclass(frozen=True)
class LayoutIssue:
    """One concrete layout problem found by the audit."""

    kind: str
    message: str
    subjects: tuple[str, ...]


@dataclass(frozen=True)
class LayoutReport:
    """Summary of layout safety findings."""

    checked_count: int
    issues: tuple[LayoutIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class CheckpointAudit:
    """One audit snapshot collected from a scene run."""

    label: str
    report: LayoutReport


# ── Shape Classification ────────────────────────────────────────


class ShapeType(Enum):
    """Coarse shape category for choosing the right refinement strategy."""

    RECTANGULAR = "rectangular"
    CIRCULAR = "circular"
    GENERIC = "generic"


_CIRCULAR_NAMES = frozenset({"circle", "dot", "ellipse", "arc"})
_RECTANGULAR_NAMES = frozenset({
    "square", "rectangle", "rect", "text", "mathtex",
    "tex", "vmobject", "svgpathmobject", "polymobject",
    "line", "dashedline", "arrow", "bracket",
})


def classify_shape(mob: Mobject) -> ShapeType:
    """Classify a mobject's shape type from its class name."""
    name = type(mob).__name__.lower()
    if any(k in name for k in _CIRCULAR_NAMES):
        return ShapeType.CIRCULAR
    if any(k in name for k in _RECTANGULAR_NAMES):
        return ShapeType.RECTANGULAR
    return ShapeType.GENERIC


def _approx_radius(mob: Mobject) -> float:
    """Approximate radius for circular objects (center to RIGHT boundary)."""
    center = mob.get_center()
    bp = mob.get_boundary_point(np.array([1.0, 0.0, 0.0]))
    return float(np.linalg.norm(bp - center))


# ── Boundary Refinement ──────────────────────────────────────────


def refine_overlap_check(
    mob_a: Mobject,
    mob_b: Mobject,
    *,
    sample_dirs: int = 8,
) -> tuple[bool, float]:
    """Confirm or reject an AABB overlap using boundary-point geometry.

    Returns:
        (actually_overlaps, confidence) where confidence is 0.0–1.0.
        High confidence means the result is definitive; low confidence
        means the shapes are complex and the check is approximate.
    """
    type_a = classify_shape(mob_a)
    type_b = classify_shape(mob_b)

    # Circular + Circular: use center-distance vs sum of radii
    if type_a == ShapeType.CIRCULAR and type_b == ShapeType.CIRCULAR:
        dist = float(np.linalg.norm(mob_a.get_center() - mob_b.get_center()))
        r_a = _approx_radius(mob_a)
        r_b = _approx_radius(mob_b)
        overlaps = dist < (r_a + r_b)
        # Confidence based on how close to the threshold
        margin = (r_a + r_b) - dist
        confidence = min(1.0, max(0.3, margin / (r_a + r_b))) if overlaps else min(1.0, max(0.3, margin / (r_a + r_b)))
        return overlaps, confidence

    # Circular + Rectangular: check rect corners against circle radius
    circular = mob_a if type_a == ShapeType.CIRCULAR else mob_b
    rectangular = mob_b if type_a == ShapeType.CIRCULAR else mob_a
    if (type_a == ShapeType.CIRCULAR and type_b == ShapeType.RECTANGULAR) or (
        type_b == ShapeType.CIRCULAR and type_a == ShapeType.RECTANGULAR
    ):
        radius = _approx_radius(circular)
        center = circular.get_center()
        corners = [
            rectangular.get_corner(np.array([x, y, 0.0]))
            for x in (-1.0, 1.0) for y in (-1.0, 1.0)
        ]
        any_inside = any(
            np.linalg.norm(np.array(c) - center) < radius for c in corners
        )
        inside_count = sum(
            1 for c in corners if np.linalg.norm(np.array(c) - center) < radius
        )
        confidence = inside_count / 4.0
        return any_inside, confidence

    # Generic + anything: sample boundary points of A, test against B's AABB
    base_dirs = [
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([-1.0, 0.0, 0.0]),
        np.array([0.0, -1.0, 0.0]),
    ]
    diag_dirs = []
    for dx in (-1.0, 1.0):
        for dy in (-1.0, 1.0):
            v = np.array([dx, dy, 0.0])
            diag_dirs.append(v / np.linalg.norm(v))
    directions = base_dirs + diag_dirs

    b_left = float(mob_b.get_left()[0])
    b_right = float(mob_b.get_right()[0])
    b_bottom = float(mob_b.get_bottom()[1])
    b_top = float(mob_b.get_top()[1])

    hits = 0
    total = 0
    for d in directions[:sample_dirs]:
        try:
            pt = mob_a.get_boundary_point(d)
            total += 1
            if b_left <= pt[0] <= b_right and b_bottom <= pt[1] <= b_top:
                hits += 1
        except Exception:
            total += 1

    # Also sample B against A
    a_left = float(mob_a.get_left()[0])
    a_right = float(mob_a.get_right()[0])
    a_bottom = float(mob_a.get_bottom()[1])
    a_top = float(mob_a.get_top()[1])

    for d in directions[:sample_dirs]:
        try:
            pt = mob_b.get_boundary_point(d)
            total += 1
            if a_left <= pt[0] <= a_right and a_bottom <= pt[1] <= a_top:
                hits += 1
        except Exception:
            total += 1

    confidence = hits / max(total, 1)
    return hits > 0, confidence


def _coerce_named_mobjects(
    items: Iterable[tuple[str, Mobject] | Mobject],
) -> list[tuple[str, Mobject]]:
    named: list[tuple[str, Mobject]] = []
    auto_counts: dict[str, int] = {}
    for item in items:
        if isinstance(item, tuple):
            name, mob = item
        else:
            mob = item
            base = mob.__class__.__name__
            auto_counts[base] = auto_counts.get(base, 0) + 1
            name = f"{base}[{auto_counts[base]}]"
        if not isinstance(mob, Mobject):
            raise TypeError(f"Expected Mobject, got {type(mob)!r}")
        named.append((name, mob))
    return named


def get_mobject_bounds(mobject: Mobject, *, padding: float = 0.0) -> Bounds2D:
    """Return 2D bounds using the same boundary logic Manim uses for placement."""
    left = float(mobject.get_critical_point(LEFT)[0]) - padding
    right = float(mobject.get_critical_point(RIGHT)[0]) + padding
    bottom = float(mobject.get_critical_point(DOWN)[1]) - padding
    top = float(mobject.get_critical_point(UP)[1]) + padding
    return Bounds2D(left=left, right=right, bottom=bottom, top=top)


def audit_layout(
    *items: tuple[str, Mobject] | Mobject,
    min_gap: float = 0.15,
    frame_margin: float = 0.25,
    padding: float = 0.0,
    refine: bool = True,
) -> LayoutReport:
    """Detect pairwise overlaps, crowding, and frame overflow for mobjects.

    Args:
        refine: When True (default), run boundary-point refinement on AABB
               overlaps to reduce false positives on circular / curved shapes.
    """
    named = _coerce_named_mobjects(items)
    mob_map = {name: mob for name, mob in named}
    bounds_map = {
        name: get_mobject_bounds(mob, padding=padding)
        for name, mob in named
        if len(mob.get_points_defining_boundary()) > 0
    }
    issues: list[LayoutIssue] = []

    # ── Phase 1: Frame overflow (is_off_screen + margin detail) ──
    safe_left = -float(config["frame_x_radius"]) + frame_margin
    safe_right = float(config["frame_x_radius"]) - frame_margin
    safe_bottom = -float(config["frame_y_radius"]) + frame_margin
    safe_top = float(config["frame_y_radius"]) - frame_margin

    for name, mob in named:
        if len(mob.get_points_defining_boundary()) == 0:
            continue
        is_off = mob.is_off_screen()
        bounds = bounds_map[name]

        overflow_parts: list[str] = []
        if bounds.left < safe_left:
            overflow_parts.append(f"left by {safe_left - bounds.left:.2f}")
        if bounds.right > safe_right:
            overflow_parts.append(f"right by {bounds.right - safe_right:.2f}")
        if bounds.bottom < safe_bottom:
            overflow_parts.append(f"bottom by {safe_bottom - bounds.bottom:.2f}")
        if bounds.top > safe_top:
            overflow_parts.append(f"top by {bounds.top - safe_top:.2f}")

        if is_off or overflow_parts:
            issues.append(
                LayoutIssue(
                    kind="frame-overflow",
                    subjects=(name,),
                    message=(
                        f"{name} exceeds safe frame margin ({frame_margin:.2f})"
                        + (f": " + ", ".join(overflow_parts) if overflow_parts else "")
                        + (" [OFF SCREEN]" if is_off else "")
                    ),
                )
            )

    # ── Phase 2: AABB pairwise checks ──
    aabb_overlaps: list[tuple[str, str, float, float, Mobject, Mobject]] = []

    for (left_name, left_bounds), (right_name, right_bounds) in combinations(
        bounds_map.items(), 2
    ):
        overlap_x = min(left_bounds.right, right_bounds.right) - max(
            left_bounds.left, right_bounds.left
        )
        overlap_y = min(left_bounds.top, right_bounds.top) - max(
            left_bounds.bottom, right_bounds.bottom
        )
        gap_x = max(
            left_bounds.left - right_bounds.right,
            right_bounds.left - left_bounds.right,
            0.0,
        )
        gap_y = max(
            left_bounds.bottom - right_bounds.top,
            right_bounds.bottom - left_bounds.top,
            0.0,
        )

        if overlap_x > 0 and overlap_y > 0:
            aabb_overlaps.append(
                (left_name, right_name, overlap_x, overlap_y,
                 mob_map[left_name], mob_map[right_name])
            )
            continue

        if overlap_y > 0 and 0.0 < gap_x < min_gap:
            issues.append(
                LayoutIssue(
                    kind="crowding-horizontal",
                    subjects=(left_name, right_name),
                    message=(
                        f"{left_name} and {right_name} are horizontally crowded "
                        f"(gap={gap_x:.2f} < min_gap={min_gap:.2f})"
                    ),
                )
            )
        if overlap_x > 0 and 0.0 < gap_y < min_gap:
            issues.append(
                LayoutIssue(
                    kind="crowding-vertical",
                    subjects=(left_name, right_name),
                    message=(
                        f"{left_name} and {right_name} are vertically crowded "
                        f"(gap={gap_y:.2f} < min_gap={min_gap:.2f})"
                    ),
                )
            )

    # ── Phase 3: Boundary-point refinement of AABB overlaps ──
    if aabb_overlaps:
        if refine:
            for left_name, right_name, ov_x, ov_y, mob_a, mob_b in aabb_overlaps:
                try:
                    actually_overlaps, confidence = refine_overlap_check(mob_a, mob_b)
                except Exception:
                    actually_overlaps, confidence = True, 0.5

                if actually_overlaps:
                    kind = "overlap-refined" if confidence >= 0.6 else "overlap"
                    conf_tag = f" [conf={confidence:.0%}]" if confidence < 1.0 else ""
                    issues.append(
                        LayoutIssue(
                            kind=kind,
                            subjects=(left_name, right_name),
                            message=(
                                f"{left_name} overlaps {right_name} "
                                f"(x={ov_x:.2f}, y={ov_y:.2f}, refined){conf_tag}"
                            ),
                        )
                    )
                else:
                    issues.append(
                        LayoutIssue(
                            kind="overlap-false-positive",
                            subjects=(left_name, right_name),
                            message=(
                                f"{left_name} vs {right_name}: AABB reported "
                                f"(x={ov_x:.2f}, y={ov_y:.2f}) but refinement "
                                f"cleared it [conf={confidence:.0%}]"
                            ),
                        )
                    )
        else:
            # No refine: mark as AABB-only
            for left_name, right_name, ov_x, ov_y, _, _ in aabb_overlaps:
                issues.append(
                    LayoutIssue(
                        kind="overlap",
                        subjects=(left_name, right_name),
                        message=(
                            f"{left_name} overlaps {right_name} "
                            f"(x={ov_x:.2f}, y={ov_y:.2f}) [AABB only]"
                        ),
                    )
                )

    return LayoutReport(checked_count=len(bounds_map), issues=tuple(issues))


def assert_layout_safe(
    *items: tuple[str, Mobject] | Mobject,
    min_gap: float = 0.15,
    frame_margin: float = 0.25,
    padding: float = 0.0,
    refine: bool = True,
    label: str | None = None,
) -> LayoutReport:
    """Raise with a concrete message when the layout is unsafe."""
    report = audit_layout(
        *items,
        min_gap=min_gap,
        frame_margin=frame_margin,
        padding=padding,
        refine=refine,
    )
    if report.ok:
        return report

    prefix = f"{label}: " if label else ""
    detail = "; ".join(issue.message for issue in report.issues)
    raise ValueError(f"{prefix}layout safety check failed: {detail}")


def summarize_layout_report(report: LayoutReport) -> str:
    """Return a short human-readable summary for logs or tool output."""
    if report.ok:
        return f"layout safe: checked {report.checked_count} mobjects, no issues found"
    counts: dict[str, int] = {}
    for issue in report.issues:
        counts[issue.kind] = counts.get(issue.kind, 0) + 1
    parts = ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items()))
    return (
        f"layout issues: checked {report.checked_count} mobjects, "
        f"found {len(report.issues)} issue(s) [{parts}]"
    )


def _named_scene_mobjects(scene: Scene) -> list[tuple[str, Mobject]]:
    return [
        (f"{mob.__class__.__name__}[{index}]", mob)
        for index, mob in enumerate(scene.mobjects, start=1)
    ]


def audit_scene_mobjects(
    scene: Scene,
    *,
    min_gap: float,
    frame_margin: float,
    padding: float,
    refine: bool = True,
) -> LayoutReport:
    """Audit every top-level mobject currently present in the scene."""
    return audit_layout(
        *_named_scene_mobjects(scene),
        min_gap=min_gap,
        frame_margin=frame_margin,
        padding=padding,
        refine=refine,
    )


def _load_scene_class(scene_file: str, scene_class: str) -> type[Scene]:
    scene_path = Path(scene_file).resolve()
    spec = spec_from_file_location("layout_safety_scene_module", scene_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load scene module from {scene_path}")

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    try:
        scene_cls = getattr(module, scene_class)
    except AttributeError as exc:
        raise AttributeError(
            f"Scene class '{scene_class}' was not found in {scene_path.name}"
        ) from exc

    if not isinstance(scene_cls, type) or not issubclass(scene_cls, Scene):
        raise TypeError(f"{scene_class} is not a Manim Scene subclass")
    return scene_cls


def run_layout_audit(
    scene_file: str,
    scene_class: str,
    *,
    checkpoint_mode: str = "after-play",
    min_gap: float = 0.15,
    frame_margin: float = 0.25,
    padding: float = 0.0,
    refine: bool = True,
) -> list[CheckpointAudit]:
    """Render a scene in dry-run mode and collect one or more layout audits."""
    scene_cls = _load_scene_class(scene_file, scene_class)
    audits: list[CheckpointAudit] = []

    with tempconfig(
        {
            "dry_run": True,
            "write_to_movie": False,
            "disable_caching": True,
            "format": "png",
        }
    ):
        scene = scene_cls()

        if checkpoint_mode == "after-play":
            original_play = scene.play

            def audited_play(*args, **kwargs):
                result = original_play(*args, **kwargs)
                audits.append(
                    CheckpointAudit(
                        label=f"after-play-{len(audits) + 1}",
                        report=audit_scene_mobjects(
                            scene,
                            min_gap=min_gap,
                            frame_margin=frame_margin,
                            padding=padding,
                            refine=refine,
                        ),
                    )
                )
                return result

            scene.play = audited_play  # type: ignore[method-assign]

        scene.render()

        if checkpoint_mode == "final":
            audits.append(
                CheckpointAudit(
                    label="final",
                    report=audit_scene_mobjects(
                        scene,
                        min_gap=min_gap,
                        frame_margin=frame_margin,
                        padding=padding,
                        refine=refine,
                    ),
                )
            )

    return audits


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit a Manim scene for overlap, crowding, and frame overflow."
    )
    parser.add_argument("scene_file", help="Path to the Manim scene file, such as scene.py")
    parser.add_argument("scene_class", help="Scene class name to audit, such as GeneratedScene")
    parser.add_argument(
        "--checkpoint-mode",
        choices=("final", "after-play"),
        default="after-play",
        help="When to sample the scene layout during the dry-run render.",
    )
    parser.add_argument("--min-gap", type=float, default=0.15)
    parser.add_argument("--frame-margin", type=float, default=0.25)
    parser.add_argument("--padding", type=float, default=0.0)
    refine_group = parser.add_mutually_exclusive_group()
    refine_group.add_argument(
        "--refine", action="store_true", dest="refine", default=True,
        help="Run boundary-point refinement on AABB overlaps (default).",
    )
    refine_group.add_argument(
        "--no-refine", action="store_false", dest="refine",
        help="Skip refinement: use AABB only (faster, more false positives).",
    )
    return parser


def _print_audit_results(audits: list[CheckpointAudit]) -> bool:
    if not audits:
        print("layout audit: no checkpoints were captured")
        return True

    all_ok = True
    for audit in audits:
        print(f"[{audit.label}] {summarize_layout_report(audit.report)}")
        if audit.report.ok:
            continue
        all_ok = False
        for issue in audit.report.issues:
            print(f"  - {issue.message}")
    return all_ok


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        audits = run_layout_audit(
            args.scene_file,
            args.scene_class,
            checkpoint_mode=args.checkpoint_mode,
            min_gap=args.min_gap,
            frame_margin=args.frame_margin,
            padding=args.padding,
            refine=args.refine,
        )
    except Exception as exc:
        print(f"layout audit failed: {exc}", file=sys.stderr)
        return 2

    return 0 if _print_audit_results(audits) else 1


if __name__ == "__main__":
    raise SystemExit(main())
