from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional

from .ugatu_models import UCodeDefinition


class UCodeRegistry:
    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or Path(__file__).with_name("registry_v1.json")
        self.supplement_paths = [Path(__file__).with_name("registry_driver_v1_3.json")]
        self.version = "0"
        self.codes: Dict[str, UCodeDefinition] = {}
        self.reserved_ranges = []
        self.reload()

    @staticmethod
    def normalize(value: str) -> str:
        value = str(value or "").strip().upper()
        m = re.fullmatch(r"U[- ]?(\d{4})", value)
        return f"U-{m.group(1)}" if m else value

    def reload(self) -> None:
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        versions = [payload["registry_version"]]
        merged = list(payload.get("codes", []))
        for path in self.supplement_paths:
            if not path.exists():
                continue
            supplement = json.loads(path.read_text(encoding="utf-8"))
            versions.append(supplement.get("registry_version", "0"))
            merged.extend(supplement.get("codes", []))
        self.version = max(versions, key=lambda v: tuple(int(x) for x in str(v).split(".")))
        self.codes = {
            item["ucode"]: UCodeDefinition(**item)
            for item in merged
        }
        self.reserved_ranges = payload.get("reserved_ranges", [])

    def get(self, ucode: str) -> Optional[UCodeDefinition]:
        return self.codes.get(self.normalize(ucode))

    def list(self, role: Optional[str] = None, domain: Optional[str] = None) -> List[UCodeDefinition]:
        result = list(self.codes.values())
        if role:
            role = role.upper()
            result = [x for x in result if not x.roles or role in x.roles]
        if domain:
            domain = domain.upper()
            result = [x for x in result if x.domain.upper() == domain]
        return sorted(result, key=lambda x: x.ucode)

    def resolve(self, query: str, role: Optional[str] = None) -> Optional[UCodeDefinition]:
        normalized = self.normalize(query)
        exact = self.get(normalized)
        if exact and self._role_visible(exact, role):
            return exact

        q = str(query or "").strip().lower()
        candidates = [x for x in self.codes.values() if self._role_visible(x, role)]

        for item in candidates:
            names = [item.name, *item.aliases]
            if any(q == n.lower() for n in names):
                return item

        scored = []
        for item in candidates:
            names = [item.name, *item.aliases]
            score = max((SequenceMatcher(None, q, n.lower()).ratio() for n in names), default=0)
            if any(q in n.lower() for n in names):
                score += 0.35
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored and scored[0][0] >= 0.58 else None

    @staticmethod
    def _role_visible(item: UCodeDefinition, role: Optional[str]) -> bool:
        if not role or not item.roles:
            return True
        return role.upper() in item.roles


registry = UCodeRegistry()
