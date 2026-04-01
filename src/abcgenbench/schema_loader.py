from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict[str, Any]:
    package = resources.files("abcgenbench.schemas")
    with package.joinpath(name).open("r", encoding="utf-8") as handle:
        return json.load(handle)
