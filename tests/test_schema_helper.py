"""Tests for custom_components.luxtronik2.schema_helper."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.const import CONF_HOST, CONF_PORT
import pytest
import voluptuous as vol

from custom_components.luxtronik2.const import (
    DEFAULT_PORT,
)
from custom_components.luxtronik2.schema_helper import (
    build_options_schema,
    build_user_data_schema,
)


class TestBuildUserDataSchema:
    def test_default_schema(self):
        schema = build_user_data_schema()
        assert isinstance(schema, vol.Schema)

    def test_custom_values(self):
        schema = build_user_data_schema(
            host="10.0.0.1",
            port=8888,
            timeout=30.0,
            max_data_length=5000,
        )
        assert isinstance(schema, vol.Schema)

    def test_schema_validates_valid_data(self):
        schema = build_user_data_schema()
        result = cast(
            dict[str, Any],
            schema(
                {
                    CONF_HOST: "192.168.1.100",
                    CONF_PORT: DEFAULT_PORT,
                }
            ),
        )
        assert result[CONF_HOST] == "192.168.1.100"
        assert result[CONF_PORT] == DEFAULT_PORT

    def test_schema_coerces_string_inputs_from_ui(self):
        schema = build_user_data_schema()
        result = cast(
            dict[str, Any],
            schema(
                {
                    CONF_HOST: "192.168.1.100",
                    CONF_PORT: "8889",
                    "timeout": "30.5",
                    "max_data_length": "5000",
                }
            ),
        )
        assert result[CONF_HOST] == "192.168.1.100"
        assert result[CONF_PORT] == 8889
        assert result["timeout"] == 30.5
        assert result["max_data_length"] == 5000

    def test_schema_uses_defaults(self):
        schema = build_user_data_schema()
        result = cast(dict[str, Any], schema({}))
        # Both host and port have defaults, so empty dict is valid
        assert CONF_HOST in result
        assert CONF_PORT in result

    def test_schema_rejects_invalid_port_type(self):
        schema = build_user_data_schema()
        with pytest.raises(vol.MultipleInvalid):
            schema({CONF_HOST: "192.168.1.100", CONF_PORT: "not_a_number"})


class TestBuildOptionsSchema:
    def test_default_schema(self):
        schema = build_options_schema()
        assert isinstance(schema, vol.Schema)

    def test_with_indoor_temperature_sensor(self):
        schema = build_options_schema(
            current_indoor_temp="sensor.indoor_temp",
        )
        assert isinstance(schema, vol.Schema)

    def test_with_update_interval(self):
        schema = build_options_schema(
            current_interval="1 minute",
        )
        assert isinstance(schema, vol.Schema)
