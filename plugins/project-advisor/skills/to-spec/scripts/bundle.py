"""Filesystem bundle generation for rendered specs."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .manifest_types import NormalizedManifest
from .output_validation import validate_generated_bundle
from .paths import ASSET_DIR
from .render import render_document
from .styles import compile_stylesheet
from .yaml_manifest import dumps

BUNDLE_PREFIX = "SPEC-"


def bundle_dir_name(slug: str) -> str:
    return f"{BUNDLE_PREFIX}{slug}"


def generate_bundle(manifest: NormalizedManifest, output_root: Path, force: bool = False) -> Path:
    output_root = output_root.resolve()
    bundle_name = bundle_dir_name(manifest["slug"])
    target = output_root / bundle_name
    if (target.exists() or target.is_symlink()) and not force:
        raise FileExistsError(
            f"{target} already exists; pass --force to replace the generated bundle"
        )

    output_root.mkdir(parents=True, exist_ok=True)
    temp_path = Path(tempfile.mkdtemp(prefix=f".{bundle_name}-", dir=output_root))
    backup_root: Path | None = None
    backup_path: Path | None = None
    try:
        (temp_path / "index.html").write_text(
            render_document(manifest),
            encoding="utf-8",
        )
        (temp_path / "spec.yaml").write_text(
            dumps(manifest),
            encoding="utf-8",
        )
        assets = temp_path / "assets"
        assets.mkdir()
        (assets / "styles.css").write_text(
            compile_stylesheet(ASSET_DIR / "styles.css", ASSET_DIR), encoding="utf-8"
        )
        for name in ("app.js", "favicon.svg"):
            shutil.copy2(ASSET_DIR / name, assets / name)
        shutil.copytree(ASSET_DIR / "fonts", assets / "fonts")
        validate_generated_bundle(temp_path)
        if target.exists() or target.is_symlink():
            backup_root = Path(tempfile.mkdtemp(prefix=f".{bundle_name}-backup-", dir=output_root))
            backup_path = backup_root / "previous"
            target.rename(backup_path)
        try:
            temp_path.rename(target)
        except Exception:
            if (
                backup_path is not None
                and (backup_path.exists() or backup_path.is_symlink())
                and not target.exists()
                and not target.is_symlink()
            ):
                backup_path.rename(target)
            raise
        if backup_root is not None:
            shutil.rmtree(backup_root)
    except Exception:
        if temp_path.exists():
            shutil.rmtree(temp_path)
        if (
            backup_root is not None
            and backup_root.exists()
            and backup_path is not None
            and not backup_path.exists()
            and not backup_path.is_symlink()
        ):
            shutil.rmtree(backup_root)
        raise
    return target


__all__ = ["BUNDLE_PREFIX", "bundle_dir_name", "generate_bundle"]
