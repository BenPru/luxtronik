#!/usr/bin/env python3
"""Check that all entity translation keys are present in all language files."""

import ast
import json
import logging
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENTITY_DIR = REPO_ROOT / "custom_components" / "luxtronik2"
TRANS_DIR = ENTITY_DIR / "translations"
CONST_FILE = ENTITY_DIR / "const.py"

LANG_FILES = ["en.json", "de.json", "cs.json", "nl.json", "pl.json"]

ENTITY_CHECKS = [
    ("number_entities_predefined.py", "number"),
    ("binary_sensor_entities_predefined.py", "binary_sensor"),
    ("sensor_entities_predefined.py", "sensor"),
    ("date_entities_predefined.py", "date"),
    ("select_entities_predefined.py", "select"),
    ("switch_entities_predefined.py", "switch"),
]

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOG = logging.getLogger(__name__)


def load_const_mapping() -> dict[str, str]:
    """Load SensorKey enum name -> string value mapping from const.py."""
    with open(CONST_FILE, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and isinstance(target.id, str)
                    and target.id.isupper()
                    and isinstance(node.value, ast.Constant)
                ):
                    mapping[target.id] = str(node.value.value)
    return mapping


def get_entity_keys(filename: str) -> list[str]:
    """Extract SensorKey translation keys used in a predefined entities file."""
    filepath = ENTITY_DIR / filename
    if not filepath.exists():
        LOG.warning("WARNING: %s not found, skipping", filename)
        return []
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    refs: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            for kw in node.keywords:
                if kw.arg == "key":
                    v = kw.value
                    if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name):
                        refs.append(v.attr)
            self.generic_visit(node)

    Visitor().visit(tree)
    mapping = load_const_mapping()
    return sorted(set(mapping.get(r, r) for r in refs))


def load_all_languages() -> dict[str, dict]:
    """Load every translations/<lang>.json, keyed by language code."""
    data_by_lang: dict[str, dict] = {}
    for lang_file in LANG_FILES:
        with open(TRANS_DIR / lang_file, encoding="utf-8") as f:
            data_by_lang[lang_file.removesuffix(".json")] = json.load(f)
    return data_by_lang


def find_missing_entity_keys() -> list[str]:
    """Check that every SensorKey referenced in code exists as an entity in every
    language file. Returns a list of human-readable problem descriptions."""
    problems: list[str] = []
    for entity_file, section in ENTITY_CHECKS:
        keys = get_entity_keys(entity_file)
        if not keys:
            continue
        for lang_file in LANG_FILES:
            lang = lang_file.removesuffix(".json")
            with open(TRANS_DIR / lang_file, encoding="utf-8") as f:
                data = json.load(f)
            section_data = data.get("entity", {}).get(section, {})
            missing = [k for k in keys if k not in section_data]
            for k in missing:
                problems.append(
                    f"[{lang}] entity.{section}.{k} missing (referenced in {entity_file})"
                )
    return problems


def find_state_key_mismatches() -> list[str]:
    """Check that every entity's `state` dict, and every `state_attributes.<attr>.state`
    dict, has the exact same set of keys across all language files.

    This catches the class of bug found in discussion #677: a locale (en.json) that
    is missing an entire `state_attributes.cause`/`remedy` block while other locales
    (de/nl/pl/cs) have it fully populated, or a locale simply missing individual
    error codes that others have. Per-entity `state` presence alone (checked by
    find_missing_entity_keys) does not catch either of these - only the nested keys
    do.
    """
    problems: list[str] = []
    data_by_lang = load_all_languages()

    entity_paths: set[tuple[str, str]] = set()
    for data in data_by_lang.values():
        for platform, entities in data.get("entity", {}).items():
            for entity_key, entity_data in entities.items():
                if isinstance(entity_data, dict) and isinstance(
                    entity_data.get("state"), dict
                ):
                    entity_paths.add((platform, entity_key))

    for platform, entity_key in sorted(entity_paths):
        per_lang_state: dict[str, set[str]] = {}
        for lang, data in data_by_lang.items():
            state = data["entity"].get(platform, {}).get(entity_key, {}).get("state", {})
            per_lang_state[lang] = set(state.keys())
        union = set().union(*per_lang_state.values())
        for lang, keys in per_lang_state.items():
            missing = sorted(union - keys)
            if missing:
                problems.append(
                    f"[{lang}] entity.{platform}.{entity_key}.state missing keys: {missing}"
                )

        attr_names: set[str] = set()
        for data in data_by_lang.values():
            attrs = (
                data["entity"].get(platform, {}).get(entity_key, {}).get(
                    "state_attributes", {}
                )
            )
            attr_names |= set(attrs.keys())

        for attr in sorted(attr_names):
            per_lang_attr_state: dict[str, set[str]] = {}
            for lang, data in data_by_lang.items():
                state = (
                    data["entity"]
                    .get(platform, {})
                    .get(entity_key, {})
                    .get("state_attributes", {})
                    .get(attr, {})
                    .get("state", {})
                )
                per_lang_attr_state[lang] = set(state.keys())
            attr_union = set().union(*per_lang_attr_state.values())
            if not attr_union:
                continue
            for lang, keys in per_lang_attr_state.items():
                missing = sorted(attr_union - keys)
                if missing:
                    problems.append(
                        f"[{lang}] entity.{platform}.{entity_key}.state_attributes."
                        f"{attr}.state missing keys: {missing}"
                    )
    return problems


if __name__ == "__main__":
    all_problems = find_missing_entity_keys() + find_state_key_mismatches()
    if not all_problems:
        LOG.info("All translation files have complete coverage!")
        sys.exit(0)
    LOG.info("Translation coverage problems found:")
    for problem in all_problems:
        LOG.info("  - %s", problem)
    sys.exit(1)
