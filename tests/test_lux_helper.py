"""Tests for custom_components.luxtronik2.lux_helper."""

from __future__ import annotations

import logging
import struct
from unittest.mock import MagicMock, patch

import pytest

from custom_components.luxtronik2.const import DEFAULT_MAX_DATA_LENGTH, DEFAULT_PORT
from custom_components.luxtronik2.lux_helper import (
    LUXTRONIK_DISCOVERY_MAGIC_PACKET,
    LUXTRONIK_DISCOVERY_RESPONSE_PREFIX,
    LUXTRONIK_WRITE_ACK_TIMEOUT,
    Luxtronik,
    _is_socket_closed,
    discover,
    get_firmware_download_id,
    get_manufacturer_by_model,
    get_manufacturer_firmware_url_by_model,
)

# ===========================================================================
# get_manufacturer_by_model
# ===========================================================================


class TestGetManufacturerByModel:
    def test_none_model(self):
        assert get_manufacturer_by_model(None) is None

    def test_novelan_model(self):
        assert get_manufacturer_by_model("BW something") == "Novelan"
        assert get_manufacturer_by_model("LA 12") == "Novelan"
        assert get_manufacturer_by_model("LD5") == "Novelan"
        assert get_manufacturer_by_model("LI test") == "Novelan"
        assert get_manufacturer_by_model("SI model") == "Novelan"
        assert get_manufacturer_by_model("ZLW x") == "Novelan"

    def test_alpha_innotec_model(self):
        assert get_manufacturer_by_model("LWP 10") == "Alpha Innotec"
        assert get_manufacturer_by_model("LWV x") == "Alpha Innotec"
        assert get_manufacturer_by_model("MSW 6") == "Alpha Innotec"
        assert get_manufacturer_by_model("SWC model") == "Alpha Innotec"
        assert get_manufacturer_by_model("SWP test") == "Alpha Innotec"

    def test_unknown_model(self):
        assert get_manufacturer_by_model("UNKNOWN") is None
        assert get_manufacturer_by_model("XYZ") is None


# ===========================================================================
# get_firmware_download_id
# ===========================================================================


class TestGetFirmwareDownloadId:
    def test_none_version(self):
        assert get_firmware_download_id(None) is None

    def test_v1(self):
        assert get_firmware_download_id("V1.88.3") == 0

    def test_v2(self):
        assert get_firmware_download_id("V2.88.1") == 1

    def test_v3(self):
        assert get_firmware_download_id("V3.90.1") == 2

    def test_v4(self):
        assert get_firmware_download_id("V4.0.0") == 3

    def test_f1(self):
        assert get_firmware_download_id("F1.0.0") == 4

    def test_wwb1(self):
        assert get_firmware_download_id("WWB1.0.0") == 5

    def test_smo(self):
        assert get_firmware_download_id("smo") == 6

    def test_unknown(self):
        assert get_firmware_download_id("X1.0.0") is None


# ===========================================================================
# get_manufacturer_firmware_url_by_model
# ===========================================================================


class TestGetManufacturerFirmwareUrlByModel:
    def test_none_model_uses_default(self):
        url = get_manufacturer_firmware_url_by_model(None, 42)
        assert "layout=42" in url

    def test_alpha_innotec(self):
        url = get_manufacturer_firmware_url_by_model("LWP 10", 0)
        assert "layout=1" in url

    def test_novelan(self):
        url = get_manufacturer_firmware_url_by_model("BW model", 0)
        assert "layout=2" in url

    def test_other_known(self):
        url = get_manufacturer_firmware_url_by_model("CB model", 0)
        assert "layout=3" in url

    def test_unknown_model(self):
        url = get_manufacturer_firmware_url_by_model("XYZ", 0)
        assert "layout=0" in url


# ===========================================================================
# Luxtronik class
# ===========================================================================


class TestLuxtronikClient:
    def test_init(self):
        client = Luxtronik(
            host="192.168.1.100",
            port=DEFAULT_PORT,
            socket_timeout=10.0,
            max_data_length=DEFAULT_MAX_DATA_LENGTH,
        )
        assert client._host == "192.168.1.100"
        assert client._port == DEFAULT_PORT
        assert client._socket_timeout == 10.0
        assert client._max_data_length == DEFAULT_MAX_DATA_LENGTH
        assert client._socket is None

    def test_init_safe_mode(self):
        client = Luxtronik(
            host="localhost",
            port=DEFAULT_PORT,
            socket_timeout=10.0,
            max_data_length=DEFAULT_MAX_DATA_LENGTH,
            safe=True,
        )
        # safe mode should be passed through to Parameters
        assert client.parameters is not None

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_connect_success(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client.connect()

        mock_sock.settimeout.assert_called_with(10.0)
        mock_sock.connect.assert_called_with(("192.168.1.100", DEFAULT_PORT))

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_connect_failure(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_sock.connect.side_effect = TimeoutError("timeout")
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        with pytest.raises(TimeoutError):
            client.connect()

    def test_disconnect_when_no_socket(self):
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._disconnect()  # should not raise

    @patch(
        "custom_components.luxtronik2.lux_helper._is_socket_closed", return_value=False
    )
    def test_public_disconnect_closes_socket(self, mock_is_closed):
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        client._socket = mock_sock

        client.disconnect()

        mock_sock.close.assert_called_once()
        assert client._socket is None

    @patch(
        "custom_components.luxtronik2.lux_helper._is_socket_closed", return_value=False
    )
    def test_disconnect_closes_socket(self, mock_is_closed):
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        client._socket = mock_sock

        client._disconnect()

        mock_sock.close.assert_called_once()
        assert client._socket is None

    @patch(
        "custom_components.luxtronik2.lux_helper._is_socket_closed", return_value=True
    )
    def test_disconnect_already_closed_socket(self, mock_is_closed):
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        client._socket = mock_sock

        client._disconnect()

        mock_sock.close.assert_not_called()
        assert client._socket is None

    def test_destructor(self):
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        # Just ensure __del__ doesn't raise
        client.__del__()

    def test_destructor_swallows_disconnect_errors(self):
        """M10: __del__ can run during GC/interpreter shutdown on any thread;
        a failure there must not raise, only best-effort cleanup."""
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        with patch.object(client, "_disconnect", side_effect=RuntimeError("boom")):
            client.__del__()  # must not raise


# ===========================================================================
# discover
# ===========================================================================


class TestDiscover:
    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_discover_finds_heatpump(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        response = f"{LUXTRONIK_DISCOVERY_RESPONSE_PREFIX}8889;".encode()

        # First call returns what we sent (should be skipped), second returns valid response, third times out
        call_count = 0

        def recv_side_effect(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LUXTRONIK_DISCOVERY_MAGIC_PACKET.encode(), (
                    "192.168.1.100",
                    4444,
                )
            elif call_count == 2:
                return response, ("192.168.1.100", 4444)
            raise TimeoutError

        mock_sock.recvfrom = recv_side_effect

        results = discover()
        assert ("192.168.1.100", 8889) in results

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_discover_timeout_no_results(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.side_effect = TimeoutError

        results = discover()
        assert results == []

    @patch("custom_components.luxtronik2.lux_helper.socket")
    def test_discovery_valid_port(self, mock_socket_module):
        sock_instance = MagicMock()
        mock_socket_module.socket.return_value = sock_instance
        mock_socket_module.AF_INET = 2
        mock_socket_module.SOCK_DGRAM = 2
        mock_socket_module.IPPROTO_UDP = 17
        mock_socket_module.SOL_SOCKET = 1
        mock_socket_module.SO_BROADCAST = 6

        magic_packet = "2000;111;1;\x00"
        valid_response = f"{LUXTRONIK_DISCOVERY_RESPONSE_PREFIX}8888;"
        sock_instance.recvfrom.side_effect = [
            (magic_packet.encode(), ("192.168.1.1", 4444)),
            (valid_response.encode(), ("192.168.1.200", 4444)),
            TimeoutError(),
            TimeoutError(),  # second port
        ]

        results = discover()
        assert ("192.168.1.200", 8888) in results

    @patch("custom_components.luxtronik2.lux_helper.socket")
    def test_discovery_invalid_port(self, mock_socket_module):
        sock_instance = MagicMock()
        mock_socket_module.socket.return_value = sock_instance
        mock_socket_module.AF_INET = 2
        mock_socket_module.SOCK_DGRAM = 2
        mock_socket_module.IPPROTO_UDP = 17
        mock_socket_module.SOL_SOCKET = 1
        mock_socket_module.SO_BROADCAST = 6

        valid_response = f"{LUXTRONIK_DISCOVERY_RESPONSE_PREFIX}not_a_port;"
        sock_instance.recvfrom.side_effect = [
            (valid_response.encode(), ("192.168.1.200", 4444)),
            TimeoutError(),
            TimeoutError(),
        ]

        results = discover()
        assert len([r for r in results if r[0] == "192.168.1.200"]) == 0

    @patch("custom_components.luxtronik2.lux_helper.socket")
    def test_discovery_invalid_response_prefix(self, mock_socket_module):
        sock_instance = MagicMock()
        mock_socket_module.socket.return_value = sock_instance
        mock_socket_module.AF_INET = 2
        mock_socket_module.SOCK_DGRAM = 2
        mock_socket_module.IPPROTO_UDP = 17
        mock_socket_module.SOL_SOCKET = 1
        mock_socket_module.SO_BROADCAST = 6

        invalid_response = "9999;222;garbage;"
        sock_instance.recvfrom.side_effect = [
            (invalid_response.encode(), ("192.168.1.200", 4444)),
            TimeoutError(),
            TimeoutError(),
        ]

        results = discover()
        assert ("192.168.1.200", None) not in results

    @patch("custom_components.luxtronik2.lux_helper.socket")
    def test_discover_default_uses_global_broadcast(self, mock_socket_module):
        """Without an explicit address list, sendto targets 255.255.255.255."""
        sock_instance = MagicMock()
        mock_socket_module.socket.return_value = sock_instance
        mock_socket_module.AF_INET = 2
        mock_socket_module.SOCK_DGRAM = 2
        mock_socket_module.IPPROTO_UDP = 17
        mock_socket_module.SOL_SOCKET = 1
        mock_socket_module.SO_BROADCAST = 6
        sock_instance.recvfrom.side_effect = TimeoutError

        discover()

        target_addrs = {call.args[1][0] for call in sock_instance.sendto.call_args_list}
        assert target_addrs == {"255.255.255.255"}

    @patch("custom_components.luxtronik2.lux_helper.socket")
    def test_discover_broadcasts_on_every_supplied_address(self, mock_socket_module):
        """Per-interface broadcasts: each address gets the magic packet on each port."""
        sock_instance = MagicMock()
        mock_socket_module.socket.return_value = sock_instance
        mock_socket_module.AF_INET = 2
        mock_socket_module.SOCK_DGRAM = 2
        mock_socket_module.IPPROTO_UDP = 17
        mock_socket_module.SOL_SOCKET = 1
        mock_socket_module.SO_BROADCAST = 6
        sock_instance.recvfrom.side_effect = TimeoutError

        broadcasts = ["192.168.1.255", "192.168.120.255", "10.0.0.255"]
        discover(broadcast_addresses=broadcasts)

        # Each address should appear at least once per broadcast port.
        target_addrs = [call.args[1][0] for call in sock_instance.sendto.call_args_list]
        for addr in broadcasts:
            assert target_addrs.count(addr) >= 1, (
                f"{addr} was not broadcast to; calls: {target_addrs}"
            )
        # No fallback to 255.255.255.255 when explicit list is supplied.
        assert "255.255.255.255" not in target_addrs

    @patch("custom_components.luxtronik2.lux_helper.socket")
    def test_discover_empty_address_list_falls_back_to_global(self, mock_socket_module):
        """An empty list is treated like None: fall back to 255.255.255.255."""
        sock_instance = MagicMock()
        mock_socket_module.socket.return_value = sock_instance
        mock_socket_module.AF_INET = 2
        mock_socket_module.SOCK_DGRAM = 2
        mock_socket_module.IPPROTO_UDP = 17
        mock_socket_module.SOL_SOCKET = 1
        mock_socket_module.SO_BROADCAST = 6
        sock_instance.recvfrom.side_effect = TimeoutError

        discover(broadcast_addresses=[])

        target_addrs = {call.args[1][0] for call in sock_instance.sendto.call_args_list}
        assert target_addrs == {"255.255.255.255"}


# ===========================================================================
# _is_socket_closed
# ===========================================================================


class TestIsSocketClosed:
    def test_negative_fileno(self):
        sock = MagicMock()
        sock.fileno.return_value = -1
        assert _is_socket_closed(sock) is True

    def test_fileno_exception(self):
        sock = MagicMock()
        sock.fileno.side_effect = RuntimeError("bad fd")
        assert _is_socket_closed(sock) is True

    def test_recv_empty_data_means_closed(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.recv.return_value = b""
        assert _is_socket_closed(sock) is True

    def test_recv_blocking_io_means_open(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.recv.side_effect = BlockingIOError
        assert _is_socket_closed(sock) is False

    def test_recv_connection_reset_means_closed(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.recv.side_effect = ConnectionResetError
        assert _is_socket_closed(sock) is True

    def test_recv_os_error_107_means_closed(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.recv.side_effect = OSError(107, "not connected")
        assert _is_socket_closed(sock) is True

    def test_recv_other_os_error_means_open(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.recv.side_effect = OSError(99, "other")
        assert _is_socket_closed(sock) is False

    def test_generic_exception_returns_false(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.gettimeout.return_value = 5.0
        sock.recv.side_effect = RuntimeError("unexpected")
        result = _is_socket_closed(sock)
        assert result is False
        sock.settimeout.assert_called_with(5.0)

    def test_timeout_restored_after_blocking_io_error(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.gettimeout.return_value = 10.0
        sock.recv.side_effect = BlockingIOError()
        result = _is_socket_closed(sock)
        assert result is False
        sock.settimeout.assert_called_with(10.0)

    def test_recv_returns_data_means_open(self):
        """When recv returns non-empty data, socket is open (return False after finally)."""
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.gettimeout.return_value = 5.0
        sock.recv.return_value = b"\x01\x02"
        result = _is_socket_closed(sock)
        assert result is False
        sock.settimeout.assert_called_with(5.0)


# ===========================================================================
# Luxtronik._read_write / _write
# ===========================================================================


class TestLuxtronikReadWrite:
    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_write_os_error_disconnects(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock

        # Make _read raise OSError
        with (
            patch.object(client, "_read", side_effect=OSError("socket err")),
            pytest.raises(OSError),
        ):
            client._read_write(write=False)

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_write_struct_error_disconnects(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock

        with (
            patch.object(client, "_read", side_effect=struct.error("bad data")),
            pytest.raises(struct.error),
        ):
            client._read_write(write=False)

    def test_write_does_not_read_back(self):
        """A write must not drag a full read (~1900 values) along with it: the
        coordinator refreshes straight afterwards to confirm the write, so the
        client-side read is discarded work and doubles the socket traffic of
        every write. Upstream's write() reads nothing either."""
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)

        with (
            patch.object(client, "connect"),
            patch.object(client, "_write") as mock_write,
            patch.object(client, "_read") as mock_read,
        ):
            client._read_write(write=True)

        mock_write.assert_called_once()
        mock_read.assert_not_called()

    def test_read_still_reads(self):
        """The read path must be unaffected: it reads and never writes."""
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)

        with (
            patch.object(client, "connect"),
            patch.object(client, "_write") as mock_write,
            patch.object(client, "_read") as mock_read,
        ):
            client._read_write(write=False)

        mock_read.assert_called_once()
        mock_write.assert_not_called()

    def test_write_no_socket_raises(self):
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = None
        with pytest.raises(OSError, match="Cannot write"):
            client._write()

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_reads_the_ack_under_a_short_timeout(self, mock_socket_class):
        """The ack is 8 bytes, so it must not inherit the connection timeout.

        A controller that reboots on a write (issue #761) never sends the ack
        at all. Waiting out the full connection timeout for those 8 bytes
        stalls the write for a minute and blocks Home Assistant's startup,
        where a few seconds is already far more than a healthy controller
        needs.
        """
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        effective: list[float | None] = [60.0]
        timeouts_while_reading_the_ack: list[float | None] = []
        mock_sock.settimeout.side_effect = lambda value: effective.__setitem__(0, value)

        def recv(_size):
            timeouts_while_reading_the_ack.append(effective[0])
            return struct.pack(
                ">i", 3002 if len(timeouts_while_reading_the_ack) == 1 else 1
            )

        mock_sock.recv.side_effect = recv

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 60.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {1: 42}

        client._write()

        assert timeouts_while_reading_the_ack == [
            LUXTRONIK_WRITE_ACK_TIMEOUT,
            LUXTRONIK_WRITE_ACK_TIMEOUT,
        ]

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_restores_the_connection_timeout_after_the_ack(
        self, mock_socket_class
    ):
        """The short timeout covers the ack only.

        The polling reads share this socket and move ~1900 values, so leaving
        the ack's few seconds in place would make every later read far more
        fragile than the user's configured timeout allows.
        """
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = [
            struct.pack(">i", 3002),
            struct.pack(">i", 1),
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 60.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {1: 42}

        client._write()

        assert [call[0][0] for call in mock_sock.settimeout.call_args_list] == [
            LUXTRONIK_WRITE_ACK_TIMEOUT,
            60.0,
        ]

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_never_waits_longer_for_the_ack_than_configured(
        self, mock_socket_class
    ):
        """The ack timeout is a ceiling, not a floor.

        The connection timeout is user-configurable, and someone who lowered
        it below the ack timeout asked for a shorter wait, not a longer one.
        """
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        # Seeded with a sentinel, not the expected value: seeding 2.0 would
        # let an implementation that never calls settimeout at all pass.
        effective: list[float | None] = [None]
        timeouts_while_reading_the_ack: list[float | None] = []
        mock_sock.settimeout.side_effect = lambda value: effective.__setitem__(0, value)

        def recv(_size):
            timeouts_while_reading_the_ack.append(effective[0])
            return struct.pack(
                ">i", 3002 if len(timeouts_while_reading_the_ack) == 1 else 1
            )

        mock_sock.recv.side_effect = recv

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 2.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {1: 42}

        client._write()

        assert timeouts_while_reading_the_ack == [2.0, 2.0]

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_names_the_ack_timeout_when_no_ack_arrives(self, mock_socket_class):
        """A hard-coded threshold must say when it is the one that fired.

        `_read_write` deliberately does not log, so without this the failure
        reaches the user as a bare "timed out" - indistinguishable from a poll
        or connect timeout. Since 5 s is our choice rather than the user's
        configured value, a controller that acks more slowly than we assumed
        would otherwise produce an undiagnosable regression report.
        """
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = TimeoutError("timed out")

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 60.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {1: 42}

        with pytest.raises(
            TimeoutError,
            match=r"No write acknowledgement for parameter 1 within 5\.0s",
        ):
            client._write()

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_sends_parameters(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        # The ack is the echoed command followed by the echoed parameter index.
        mock_sock.recv.side_effect = [
            struct.pack(">i", 3002),
            struct.pack(">i", 1),
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {1: 42}

        client._write()

        mock_sock.sendall.assert_called_once()
        assert client.parameters.queue == {}

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_skips_invalid_params(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {"bad_key": "bad_val"}

        client._write()

        mock_sock.sendall.assert_not_called()

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_warns_when_ack_echoes_unexpected_index(
        self, mock_socket_class, caplog
    ):
        """The controller acks a 3002 write by echoing the parameter index. An
        echo for a different index means the socket stream has desynced, so
        every following read is misaligned garbage - that must not pass
        silently."""
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = [
            struct.pack(">i", 3002),
            struct.pack(">i", 999),  # echo for a parameter we did not write
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {1: 42}

        with caplog.at_level(logging.WARNING):
            client._write()

        assert any(
            record.levelno == logging.WARNING and "999" in record.getMessage()
            for record in caplog.records
        )

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_does_not_warn_when_ack_echoes_written_index(
        self, mock_socket_class, caplog
    ):
        """A correct ack echoes back the index just written - the normal case,
        which must stay quiet."""
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = [
            struct.pack(">i", 3002),
            struct.pack(">i", 1),  # echo matches the written index
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {1: 42}

        with caplog.at_level(logging.WARNING):
            client._write()

        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_converts_float_to_int(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = [
            struct.pack(">i", 3002),
            struct.pack(">i", 5),
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {5: 21.0}

        client._write()

        mock_sock.sendall.assert_called_once()

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_clears_queue_when_the_ack_times_out(self, mock_socket_class):
        """A write that fails must not stay queued.

        Nothing retries `client.write()` - the coordinator raises to the
        caller and the entity re-syncs to the device value - so an entry left
        behind is never a pending retry, only a delayed replay.
        """
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = [
            struct.pack(">i", 3002),
            TimeoutError("timed out"),
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {1: 42}

        with pytest.raises(TimeoutError):
            client._write()

        assert client.parameters.queue == {}

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_failed_write_is_not_replayed_by_the_next_write(self, mock_socket_class):
        """A parameter whose write failed must not ride along on a later,
        unrelated write - the user was already told it was reverted."""
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = [TimeoutError("timed out")]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {2: 500}  # DHW target, write times out

        with pytest.raises(TimeoutError):
            client._write()

        # Later, an unrelated parameter is written over a healthy socket.
        # `parameters.set` mutates the existing queue dict rather than
        # replacing it, so a stale entry would still be in there.
        mock_sock.reset_mock()
        mock_sock.recv.side_effect = [
            struct.pack(">i", 3002),
            struct.pack(">i", 2),
            struct.pack(">i", 3002),
            struct.pack(">i", 108),
        ]
        client.parameters.queue[108] = 1

        client._write()

        written = [
            struct.unpack(">iii", call.args[0])[1]
            for call in mock_sock.sendall.call_args_list
        ]
        assert written == [108]

    def test_parameters_set_mutates_the_queue_in_place(self):
        """Characterisation test pinning the pinned library's contract.

        `test_failed_write_is_not_replayed_by_the_next_write` reproduces the
        replay by mutating `queue` directly, which is only a faithful model of
        `Parameters.set` while `set` writes into the existing dict rather than
        rebinding it. If a future luxtronik release rebinds, that test would
        stop reproducing anything and still pass - this one fails loudly
        instead.
        """
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        queue = client.parameters.queue

        client.parameters.set(2, 50.0)  # ID_Einst_BWS_akt, Celsius -> tenths

        assert client.parameters.queue is queue
        assert queue == {2: 500}

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_write_clears_acked_entries_when_a_later_one_fails(self, mock_socket_class):
        """Partial batch failure (e.g. a multi-row timer schedule): entries the
        controller already acked must not be written a second time."""
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = [
            struct.pack(">i", 3002),
            struct.pack(">i", 1),  # first parameter acked
            TimeoutError("timed out"),  # second never acks
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        client.parameters.queue = {1: 42, 2: 43}

        with pytest.raises(TimeoutError):
            client._write()

        assert client.parameters.queue == {}


def _fragmented_recv(payload: bytes, chunk_sizes: list[int]):
    """Build a recv() side effect that serves ``payload`` in short reads.

    Mimics a real stream socket: never returns more than the requested number
    of bytes, but may return fewer - which is exactly what happens when a TCP
    segment boundary falls inside a value.
    """
    stream = bytearray(payload)
    sizes = list(chunk_sizes)

    def recv(size):
        take = min(size, sizes.pop(0) if sizes else size, len(stream))
        chunk = bytes(stream[:take])
        del stream[:take]
        return chunk

    return recv


class TestLuxtronikReadData:
    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_oversized_length(self, mock_socket_class):
        """Data with length > max_data_length should be skipped."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            struct.pack(">i", LUXTRONIK_PARAMETERS_READ),
            struct.pack(">i", 99999),
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, 100)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            parser,
            "test",
            retries=0,
        )

        parser.parse.assert_not_called()

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_success_parameters(self, mock_socket_class):
        """Successfully reads parameter data."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        # cmd, length=2, then 2 int values
        mock_sock.recv.side_effect = [
            struct.pack(">i", LUXTRONIK_PARAMETERS_READ),  # cmd
            struct.pack(">i", 2),  # length
            struct.pack(">i", 100),  # item 1
            struct.pack(">i", 200),  # item 2
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            parser,
            "params",
            retries=0,
        )

        parser.parse.assert_called_once_with([100, 200])

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_calculations_has_stat_field(self, mock_socket_class):
        """Calculations read includes extra stat field."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_CALCULATIONS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            struct.pack(">i", LUXTRONIK_CALCULATIONS_READ),  # cmd
            struct.pack(">i", 0),  # stat (extra field for calculations)
            struct.pack(">i", 1),  # length
            struct.pack(">i", 42),  # item
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_CALCULATIONS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            parser,
            "calcs",
            retries=0,
        )

        parser.parse.assert_called_once_with([42])

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_visibilities_zero_length_disconnects(self, mock_socket_class):
        """Visibilities with length <= 0 forces disconnect."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_SOCKET_READ_SIZE_CHAR,
            LUXTRONIK_VISIBILITIES_READ,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            struct.pack(">i", LUXTRONIK_VISIBILITIES_READ),  # cmd
            struct.pack(">i", 0),  # length = 0
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_VISIBILITIES_READ,
            LUXTRONIK_SOCKET_READ_SIZE_CHAR,
            parser,
            "vis",
            retries=0,
        )

        parser.parse.assert_not_called()
        assert client._socket is None  # disconnected

    @patch("custom_components.luxtronik2.lux_helper.time.sleep")
    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_retry_on_timeout(self, mock_socket_class, mock_sleep):
        """Retries on TimeoutError."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        # First attempt times out, second succeeds
        call_count = 0

        def recv_side_effect(size):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise TimeoutError("timeout")
            if call_count == 2:
                return struct.pack(">i", LUXTRONIK_PARAMETERS_READ)
            if call_count == 3:
                return struct.pack(">i", 1)
            return struct.pack(">i", 99)

        mock_sock.recv.side_effect = recv_side_effect

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            parser,
            "params",
            retries=1,
        )

        parser.parse.assert_called_once_with([99])
        mock_sleep.assert_called_once_with(1)

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_unexpected_error_disconnects(self, mock_socket_class):
        """Unexpected errors disconnect and return."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = ValueError("unexpected")

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            parser,
            "params",
            retries=0,
        )

        parser.parse.assert_not_called()

    def test_read_exact_without_socket_raises(self):
        """Reading without a connection is an error, not a silent empty read."""
        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = None

        with pytest.raises(OSError, match="not connected"):
            client._read_exact(4)

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_short_reads_are_reassembled(self, mock_socket_class):
        """A TCP short read must not drop or misalign items (issue #723)."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        # The heatpump answers cmd, length=3 and three ints, but the stream is
        # fragmented mid-integer the way a real TCP segment boundary does it.
        payload = struct.pack(">i", LUXTRONIK_PARAMETERS_READ)
        payload += struct.pack(">i", 3)
        payload += struct.pack(">iii", 100, 200, 300)
        # Every value gets split across two recv() returns.
        mock_sock.recv.side_effect = _fragmented_recv(payload, [3, 1] * 10)

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            parser,
            "params",
            retries=0,
        )

        parser.parse.assert_called_once_with([100, 200, 300])

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_reports_fragmentation_once_per_block(
        self, mock_socket_class, caplog
    ):
        """Fragmentation is summarised per block, not logged per item."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        payload = struct.pack(">i", LUXTRONIK_PARAMETERS_READ)
        payload += struct.pack(">i", 2)
        payload += struct.pack(">ii", 100, 200)
        # cmd and length arrive whole; both items are split in two.
        mock_sock.recv.side_effect = _fragmented_recv(payload, [4, 4, 3, 1, 3, 1])

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        with caplog.at_level("DEBUG"):
            client._read_data(
                LUXTRONIK_PARAMETERS_READ,
                LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
                parser,
                "params",
                retries=0,
            )

        parser.parse.assert_called_once_with([100, 200])
        assert client._short_reads == 2
        assert len([r for r in caplog.records if "fragmented" in r.message]) == 1

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_item_timeout_does_not_parse_shifted_data(
        self, mock_socket_class
    ):
        """A timeout mid-block must abort, never parse a short/shifted list."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            struct.pack(">i", LUXTRONIK_PARAMETERS_READ),  # cmd
            struct.pack(">i", 3),  # length
            struct.pack(">i", 100),  # item 1
            TimeoutError("timeout"),  # item 2 never arrives
            struct.pack(">i", 300),  # item 3
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            parser,
            "params",
            retries=0,
        )

        parser.parse.assert_not_called()

    @patch("custom_components.luxtronik2.lux_helper.time.sleep")
    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_retry_discards_partial_data(self, mock_socket_class, mock_sleep):
        """Items read before a failed attempt must not leak into the retry."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            # Attempt 1: dies after the first item
            struct.pack(">i", LUXTRONIK_PARAMETERS_READ),
            struct.pack(">i", 2),
            struct.pack(">i", 111),
            TimeoutError("timeout"),
            # Attempt 2: full, correct answer
            struct.pack(">i", LUXTRONIK_PARAMETERS_READ),
            struct.pack(">i", 2),
            struct.pack(">i", 100),
            struct.pack(">i", 200),
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            parser,
            "params",
            retries=1,
        )

        parser.parse.assert_called_once_with([100, 200])
        mock_sleep.assert_called_once_with(1)

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_peer_close_aborts(self, mock_socket_class):
        """An empty recv() means the peer closed - abort instead of spinning."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            struct.pack(">i", LUXTRONIK_PARAMETERS_READ),
            struct.pack(">i", 2),
            struct.pack(">i", 100),
            b"",  # connection died
        ]

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            parser,
            "params",
            retries=0,
        )

        parser.parse.assert_not_called()

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_data_visibilities_short_read(self, mock_socket_class):
        """Single-byte visibility items also survive a fragmented header."""
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_SOCKET_READ_SIZE_CHAR,
            LUXTRONIK_VISIBILITIES_READ,
        )

        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        payload = struct.pack(">i", LUXTRONIK_VISIBILITIES_READ)
        payload += struct.pack(">i", 3)
        payload += struct.pack(">bbb", 1, 0, 1)
        mock_sock.recv.side_effect = _fragmented_recv(payload, [3, 1, 2] * 5)

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(
            LUXTRONIK_VISIBILITIES_READ,
            LUXTRONIK_SOCKET_READ_SIZE_CHAR,
            parser,
            "vis",
            retries=0,
        )

        parser.parse.assert_called_once_with([1, 0, 1])

    @patch("custom_components.luxtronik2.lux_helper.socket.socket")
    def test_read_calls_all_three_groups(self, mock_socket_class):
        """_read calls _read_data for parameters, calculations, visibilities."""
        mock_sock = MagicMock()
        mock_sock.fileno.return_value = -1
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", DEFAULT_PORT, 10.0, DEFAULT_MAX_DATA_LENGTH)
        client._socket = mock_sock

        with patch.object(client, "_read_data") as mock_read_data:
            client._read()
            assert mock_read_data.call_count == 3
