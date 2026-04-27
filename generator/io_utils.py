"""I/O helpers — load input task, write output artifacts."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TaskInput:
    """Loaded input artifacts for one task."""

    name: str
    business_requirements: str
    business_process: str
    features: Optional[str]  # may be None

    def as_context(self) -> str:
        """Compact context block for prompts."""
        parts = [
            "## БИЗНЕС-ТРЕБОВАНИЯ (БТ)",
            self.business_requirements.strip(),
            "",
            "## БИЗНЕС-ПРОЦЕСС (БП)",
            self.business_process.strip(),
        ]
        if self.features:
            parts += ["", "## ХАРАКТЕРИСТИКИ (Features)", self.features.strip()]
        return "\n".join(parts)


def load_task(input_dir: Path) -> TaskInput:
    """Load БТ + БП (+ Features if present) from input/<task>/."""
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    bt_path = input_dir / "business_requirements.md"
    bp_path = input_dir / "business_process.md"
    features_path = input_dir / "features.md"

    missing = [p for p in (bt_path, bp_path) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Required input files missing: {', '.join(str(p) for p in missing)}"
        )

    return TaskInput(
        name=input_dir.name,
        business_requirements=bt_path.read_text(encoding="utf-8"),
        business_process=bp_path.read_text(encoding="utf-8"),
        features=(
            features_path.read_text(encoding="utf-8") if features_path.exists() else None
        ),
    )


def clean_output(output_dir: Path) -> None:
    """Remove output_dir if exists, recreate empty."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    """Write text file, ensuring parent dirs exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_files(output_dir: Path, files: dict[str, str]) -> list[Path]:
    """Write a dict {relative_path: content} into output_dir."""
    written: list[Path] = []
    for rel, content in files.items():
        # Sanitize: refuse paths trying to escape output_dir
        target = (output_dir / rel).resolve()
        if not str(target).startswith(str(output_dir.resolve())):
            raise ValueError(f"Path escapes output dir: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written
