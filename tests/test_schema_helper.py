"""Tests for custom_components.luxtronik2.schema_helper."""

from __future__ import annotations

import json
from typing import Any, cast

from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
import pytest
import voluptuous as vol
import voluptuous_serialize

from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION,
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_UPDATE_INTERVAL_OPTION,
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

    def test_empty_submission_omits_unset_entity_sensors(self):
        """Regression test for PR #743.

        Submitting the options form with the optional entity fields left empty
        must validate. Giving them ``default=None`` makes voluptuous force the
        keys into the validated output as ``None``, which ``EntitySelector``
        rejects with "Entity None is neither a valid entity ID nor a valid
        UUID" - failing the whole form, so even the update interval can't be
        saved.
        """
        schema = build_options_schema()
        result = cast(dict[str, Any], schema({}))
        assert result == {CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_OPTION}

    def test_one_entity_sensor_set_does_not_require_the_other(self):
        """Picking only one of the two sensors must not fail on the other."""
        schema = build_options_schema()
        result = cast(
            dict[str, Any],
            schema(
                {
                    CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: "sensor.power",
                    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_OPTION,
                }
            ),
        )
        assert result[CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION] == "sensor.power"
        assert CONF_HA_SENSOR_INDOOR_TEMPERATURE not in result

    @pytest.mark.parametrize(
        "cleared_key",
        [CONF_HA_SENSOR_INDOOR_TEMPERATURE, CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION],
    )
    def test_clearing_a_previously_set_sensor_drops_the_key(self, cleared_key: str):
        """A cleared field must not be resurrected by a stale default.

        The frontend omits emptied optional keys from the submission. With
        ``default=current_value`` voluptuous re-inserts the *previous* sensor,
        so clearing silently did nothing. The key must stay absent instead, so
        the options flow can store an explicit ``None`` and shadow any value
        left over in ``config_entry.data``.
        """
        keys = {
            CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.indoor_temp",
            CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION: "sensor.power",
        }
        schema = build_options_schema(
            current_indoor_temp=keys[CONF_HA_SENSOR_INDOOR_TEMPERATURE],
            current_power_consumption_sensor=keys[
                CONF_HA_SENSOR_CURRENT_POWER_CONSUMPTION
            ],
        )
        submitted = {
            key: value for key, value in keys.items() if key != cleared_key
        } | {CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_OPTION}

        result = cast(dict[str, Any], schema(submitted))

        assert cleared_key not in result
        for key, value in keys.items():
            if key != cleared_key:
                assert result[key] == value

    def test_default_schema_is_json_serializable(self):
        """Regression test for issue #656.

        A config entry that has never saved options before (current_interval=None,
        the common case) must not fall back to the raw DEFAULT_UPDATE_INTERVAL
        timedelta - the frontend serializes this schema to JSON to render the
        "Configure" form, and a timedelta default/suggested_value crashes that
        with a 500 (TypeError: Object of type timedelta is not JSON serializable).
        """
        schema = build_options_schema()
        converted = voluptuous_serialize.convert(
            schema, custom_serializer=cv.custom_serializer
        )
        json.dumps(converted)  # must not raise
