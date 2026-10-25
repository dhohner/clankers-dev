"""Decode operational responses separately from authoring documents."""

from __future__ import annotations

from typing import Any

from support import load_yaml

from toon_oracle import decode


def decode_response(text: str, output_format: str = "toon") -> dict[str, Any]:
    if not text.strip():
        raise AssertionError("expected one complete operational response")
    return decode(text) if output_format == "toon" else load_yaml(text)
