"""Regression tests for translation completeness across locales.

These wrap .github/scripts/check_translation_coverage.py so drift is caught by a
routine `pytest` run, not only by the dedicated translation-coverage.yml CI job.

Context: BenPru/luxtronik discussion #677 reported that sensor.luxtronik_error_reason's
`cause`/`remedy` attributes just echoed the raw error code in English. The actual bug
was that en.json was entirely missing the `state_attributes.cause`/`remedy` translation
blocks that de/nl/pl/cs already had - existing coverage tooling only checked that each
entity *key* (e.g. "error_reason") existed per locale, not that its nested `state` /
`state_attributes.<attr>.state` code tables matched across locales. That same blind spot
also hid a second, unrelated bug in switchoff_reason (missing Dutch codes, stray
unreachable "-1" entries in a couple of locales).
"""

import importlib.util
from pathlib import Path
import sys

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / ".github"
    / "scripts"
    / "check_translation_coverage.py"
)
_spec = importlib.util.spec_from_file_location(
    "check_translation_coverage", _SCRIPT_PATH
)
assert _spec and _spec.loader
check_translation_coverage = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = check_translation_coverage
_spec.loader.exec_module(check_translation_coverage)


def test_all_referenced_entity_keys_have_translations() -> None:
    """Every SensorKey referenced in a *_entities_predefined.py file must exist as
    an entity in every language file."""
    problems = check_translation_coverage.find_missing_entity_keys()
    assert not problems, "\n" + "\n".join(problems)


def test_state_and_state_attribute_codes_match_across_locales() -> None:
    """Every entity's `state` dict, and every `state_attributes.<attr>.state` dict,
    must have the same set of keys in every language file - no locale may be missing
    codes (or have stray/unreachable ones) that others don't."""
    problems = check_translation_coverage.find_state_key_mismatches()
    assert not problems, "\n" + "\n".join(problems)
