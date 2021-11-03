import json
import os.path

from ..const import LANG_DEFAULT, LANGUAGES, LOGGER

__content_locale__ = None
__content_default__ = None


def _load_lang_from_file(fname: str):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    fname = os.path.join(dir_path, fname)
    if not os.path.isfile(fname):
        LOGGER.warning("_load_lang_from_file - file not found %s", fname)
        return {}
    f = open(fname, "r")
    data = json.loads(f.read())
    LOGGER.info("Load from file %s - content: %s", fname, data)
    f.close
    return data


def get_sensor_text(lang: LANGUAGES, key: str) -> str:
    global __content_locale__
    global __content_default__
    if __content_locale__ is None and lang != LANG_DEFAULT:
        __content_locale__ = _load_lang_from_file(
            f"../translations/texts.{lang}.json")
    if __content_default__ is None:
        __content_default__ = _load_lang_from_file(
            f"../translations/texts.{LANG_DEFAULT}.json")
    if lang != LANG_DEFAULT and key in __content_locale__:
        return __content_locale__[key]
    if key in __content_default__:
        return __content_default__[key]
    LOGGER.warning("get_sensor_text key %s not found in %s",
                   key, __content_default__)
    return key.replace('_', ' ').title()
