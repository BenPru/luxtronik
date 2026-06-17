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


def check_translations() -> bool:
    """Check all entity files against all language files. Returns True if OK."""
    all_ok = True

    for entity_file, section in ENTITY_CHECKS:
        keys = get_entity_keys(entity_file)
        if not keys:
            continue
        LOG.info("\n%s", "=" * 60)
        LOG.info("%s -> entity.%s (%d keys)", entity_file, section, len(keys))
        for lang_file in LANG_FILES:
            lang = lang_file.replace(".json", "")
            path = TRANS_DIR / lang_file
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            section_data = data.get("entity", {}).get(section, {})
            missing = [k for k in keys if k not in section_data]
            if missing:
                all_ok = False
                LOG.info("  %s: MISSING %d", lang, len(missing))
                for k in missing:
                    LOG.info("    - %s", k)
            else:
                LOG.info("  %s: OK", lang)

    return all_ok


if __name__ == "__main__":
    ok = check_translations()
    if ok:
        LOG.info("\nAll translation files have complete coverage!")
        sys.exit(0)
    else:
        LOG.info("\nSome translations are missing!")
        sys.exit(1)
