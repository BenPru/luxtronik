"""Main help module."""
import json
import os.path

from ..const import LANG_DEFAULT, LANGUAGES, LOGGER

__content_locale__ = None
__content_default__ = None

__content_sensor_locale__ = None
__content_sensor_default__ = None


def _load_lang_from_file(fname: str, log_warning=True):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    fname = os.path.join(dir_path, fname)
    if not os.path.isfile(fname):
        if log_warning:
            LOGGER.warning("_load_lang_from_file - file not found %s", fname)
        return {}
    f = open(fname)
    data = json.loads(f.read())
    f.close
    return data


def get_sensor_text(lang: LANGUAGES, key: str) -> str:
    """Get a sensor text."""
    global __content_locale__
    global __content_default__
    if __content_locale__ is None and not lang is None and lang != LANG_DEFAULT:
        __content_locale__ = _load_lang_from_file(f"../translations/texts.{lang}.json")
    if __content_default__ is None:
        __content_default__ = _load_lang_from_file(
            f"../translations/texts.{LANG_DEFAULT}.json"
        )
    if lang != LANG_DEFAULT and not __content_locale__ is None and key in __content_locale__:
        return __content_locale__[key]
    if key in __content_default__:
        return __content_default__[key]
    LOGGER.warning("get_sensor_text key %s not found in %s", key, __content_default__)
    return key.replace("_", " ").title()


def get_sensor_value_text(
    lang: LANGUAGES, key: str, value: str, platform="sensor"
) -> str:
    """Get a sensor value text."""
    global __content_sensor_locale__
    global __content_sensor_default__
    if __content_sensor_default__ is None:
        __content_sensor_default__ = _load_lang_from_file(
            f"../translations/{platform}.{LANG_DEFAULT}.json", log_warning=True
        )
    if __content_sensor_locale__ is None and lang != LANG_DEFAULT:
        __content_sensor_locale__ = _load_lang_from_file(
            f"../translations/{platform}.{lang}.json", log_warning=False
        )
    else:
        lang = LANG_DEFAULT
    content = (
        __content_sensor_default__
        if lang == LANG_DEFAULT
        else __content_sensor_locale__
    )
    if (
        "state" in content
        and key in content["state"]
        and value in content["state"][key]
    ):
        return content["state"][key][value]
    LOGGER.warning(
        "get_sensor_value_text key %s / value %s not found in %s",
        key,
        value,
        content,
    )
    return key.replace("_", " ").title()
