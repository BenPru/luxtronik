"""Helper for luxtronik heatpump module."""
# region Imports
from __future__ import annotations

import socket
import struct
import threading
import time

from async_timeout import timeout

from luxtronik.calculations import Calculations
from luxtronik.parameters import Parameters
from luxtronik.visibilities import Visibilities

from .const import (
    LOGGER,
    LUX_MODELS_ALPHA_INNOTEC,
    LUX_MODELS_NOVELAN,
    LUX_MODELS_OTHER,
)

# endregion Imports

WAIT_TIME_WRITE_PARAMETER = 1.0

# List of ports that are known to respond to discovery packets
LUXTRONIK_DISCOVERY_PORTS = [4444, 47808]

# Time (in seconds) to wait for response after sending discovery broadcast
LUXTRONIK_DISCOVERY_TIMEOUT = 2

# Content of packet that will be sent for discovering heat pumps
LUXTRONIK_DISCOVERY_MAGIC_PACKET = "2000;111;1;\x00"

# Content of response that is contained in responses to discovery broadcast
LUXTRONIK_DISCOVERY_RESPONSE_PREFIX = "2500;111;"


def discover() -> list[tuple[str, int | None]]:
    """Broadcast discovery for Luxtronik heat pumps."""

    results: list[tuple[str, int | None]] = []

    # pylint: disable=too-many-nested-blocks
    for port in LUXTRONIK_DISCOVERY_PORTS:
        LOGGER.debug("Send discovery packets to port %s", port)
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server.bind(("", port))
        server.settimeout(LUXTRONIK_DISCOVERY_TIMEOUT)

        # send AIT magic broadcast packet
        server.sendto(LUXTRONIK_DISCOVERY_MAGIC_PACKET.encode(), ("<broadcast>", port))
        LOGGER.debug(
            "Sending broadcast request %s", LUXTRONIK_DISCOVERY_MAGIC_PACKET.encode()
        )

        while True:
            try:
                recv_bytes, con = server.recvfrom(1024)
                res = recv_bytes.decode("ascii", errors="ignore")
                # if we receive what we just sent, continue
                if res == LUXTRONIK_DISCOVERY_MAGIC_PACKET:
                    continue
                ip_address = con[0]
                # if the response starts with the magic nonsense
                if res.startswith(LUXTRONIK_DISCOVERY_RESPONSE_PREFIX):
                    res_list = res.split(";")
                    LOGGER.debug(
                        "Received response from %s %s", ip_address, str(res_list)
                    )
                    try:
                        res_port: int | None = int(res_list[2])
                        if res_port is None or res_port < 1 or res_port > 65535:
                            LOGGER.debug("Response contained an invalid port, ignoring")
                            res_port = None
                    except ValueError:
                        res_port = None
                    if res_port is None:
                        LOGGER.debug(
                            "Response did not contain a valid port number,"
                            "an old Luxtronic software version might be the reason"
                        )
                    results.append((ip_address, res_port))
                LOGGER.debug(
                    "Received response from %s, but with wrong content, skipping",
                    ip_address,
                )
                continue
            # if the timeout triggers, go on an use the other broadcast port
            except socket.timeout:
                break

    return results


def get_manufacturer_by_model(model: str) -> str | None:
    """Return the manufacturer."""
    if model is None:
        return None
    if model.startswith(tuple(LUX_MODELS_NOVELAN)):
        return "Novelan"
    if model.startswith(tuple(LUX_MODELS_ALPHA_INNOTEC)):
        return "Alpha Innotec"
    return None


def get_firmware_download_id(installed_version: str | None) -> int | None:
    """Return the heatpump firmware id for the download portal."""
    if installed_version is None:
        return None
    if installed_version.startswith("V1."):
        return 0
    if installed_version.startswith("V2."):
        return 1
    if installed_version.startswith("V3."):
        return 2
    if installed_version.startswith("V4."):
        return 3
    if installed_version.startswith("F1."):
        return 4
    if installed_version.startswith("WWB1."):
        return 5
    if installed_version.startswith("smo"):
        return 6
    return None


def get_manufacturer_firmware_url_by_model(model: str) -> str:
    """Return the manufacturer firmware download url."""
    layout_id = 0

    if model is None:
        layout_id = 0
    elif model.startswith(tuple(LUX_MODELS_ALPHA_INNOTEC)):
        layout_id = 1
    elif model.startswith(tuple(LUX_MODELS_NOVELAN)):
        layout_id = 2
    elif model.startswith(tuple(LUX_MODELS_OTHER)):
        layout_id = 3
    return f"https://www.heatpump24.com/DownloadArea.php?layout={layout_id}"


def _is_socket_closed(sock: socket.socket) -> bool:
    try:
        if sock.fileno() < 0:
            return True
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception(
            "Unexpected exception when checking if a socket is closed", exc_info=err
        )
    try:
        # this will try to read bytes without blocking and also without removing them from buffer (peek only)
        last_timeout = sock.gettimeout()
        sock.settimeout(None)
        data = sock.recv(16, socket.MSG_DONTWAIT | socket.MSG_PEEK)
        if len(data) == 0:
            return True
    except BlockingIOError:
        return False  # socket is open and reading from it would block
    except ConnectionResetError:
        return True  # socket was closed for some other reason
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception(
            "Unexpected exception when checking if a socket is closed", exc_info=err
        )
        return False
    finally:
        sock.settimeout(last_timeout)
    return False


class Luxtronik:
    """Main luxtronik class."""

    def __init__(
        self,
        host: str,
        port: int,
        socket_timeout: float,
        max_data_length: int,
        safe=True,
    ) -> None:
        """Init Luxtronik helper."""
        self._lock = threading.Lock()
        self._socket = None
        self._host = host
        self._port = port
        self._socket_timeout = socket_timeout
        self._max_data_length = max_data_length
        self.calculations = Calculations()
        self.parameters = Parameters(safe=safe)
        self.visibilities = Visibilities()
        self.read()

    def __del__(self):
        """Luxtronik helper descructor."""
        self._disconnect()

    def _disconnect(self):
        if self._socket is not None:
            if not _is_socket_closed(self._socket):
                self._socket.close()
            self._socket = None
            LOGGER.info(
                "Disconnected from Luxtronik heatpump %s:%s", self._host, self._port
            )

    def read(self):
        """Read data from heatpump."""
        self._read_write(write=False)

    def write(self):
        """Write parameter to heatpump."""
        self._read_write(write=True)

    def _read_write(self, write=False):
        # Ensure only one socket operation at the same time
        with self._lock:
            is_none = self._socket is None
            if is_none:
                self._socket = socket.socket(
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                )
            if is_none or _is_socket_closed(self._socket):
                try:
                    self._socket.connect((self._host, self._port))
                except OSError as err:
                    if err.errno == 9:  # Bad file descr.
                        self._disconnect()
                        return
                    elif err.errno == 106:
                        self._socket.close()
                        self._socket.connect((self._host, self._port))
                    else:
                        raise err
                self._socket.settimeout(self._socket_timeout)
                LOGGER.info(
                    "Connected to Luxtronik heatpump %s:%s with timeout %ss",
                    self._host,
                    self._port,
                    self._socket_timeout,
                )
            if write:
                self._write()
                # Read the new values based on our param changes:
            self._read()

    def _read(self):
        self._read_parameters()
        self._read_calculations()
        self._read_visibilities()

    def _write(self):
        for index, value in self.parameters.queue.items():
            if not isinstance(index, int) or not isinstance(value, int):
                LOGGER.warning("Parameter id '%s' or value '%s' invalid!", index, value)
                continue
            LOGGER.info("Parameter '%d' set to '%s'", index, value)
            data = struct.pack(">iii", 3002, index, value)
            LOGGER.debug("Data %s", data)
            self._socket.sendall(data)
            cmd = struct.unpack(">i", self._socket.recv(4))[0]
            LOGGER.debug("Command %s", cmd)
            val = struct.unpack(">i", self._socket.recv(4))[0]
            LOGGER.debug("Value %s", val)
        # Flush queue after writing all values
        self.parameters.queue = {}
        # Give the heatpump a short time to handle the value changes/calculations:
        time.sleep(WAIT_TIME_WRITE_PARAMETER)

    def _read_parameters(self):
        data = []
        self._socket.sendall(struct.pack(">ii", 3003, 0))
        cmd = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Command %s", cmd)
        length = struct.unpack(">i", self._socket.recv(4))[0]
        if length > self._max_data_length:
            LOGGER.warning(
                "Skip reading parameters! Length oversized! %s>%s",
                length,
                self._max_data_length,
            )
            return
        LOGGER.debug("Length %s", length)
        for _ in range(0, length):
            try:
                data.append(struct.unpack(">i", self._socket.recv(4))[0])
            except struct.error as err:
                # not logging this as error as it would be logged on every read cycle
                LOGGER.debug(err)
        LOGGER.debug("Read %d parameters", length)
        self.parameters.parse(data)

    def _read_calculations(self):
        data = []
        self._socket.sendall(struct.pack(">ii", 3004, 0))
        cmd = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Command %s", cmd)
        stat = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Stat %s", stat)
        length = struct.unpack(">i", self._socket.recv(4))[0]
        if length > self._max_data_length:
            LOGGER.warning(
                "Skip reading calculations! Length oversized! %s>%s",
                length,
                self._max_data_length,
            )
            return
        LOGGER.debug("Length %s", length)
        for _ in range(0, length):
            try:
                data.append(struct.unpack(">i", self._socket.recv(4))[0])
            except struct.error as err:
                # not logging this as error as it would be logged on every read cycle
                LOGGER.debug(err)
        LOGGER.debug("Read %d calculations", length)
        self.calculations.parse(data)

    def _read_visibilities(self):
        data = []
        self._socket.sendall(struct.pack(">ii", 3005, 0))
        cmd = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Command %s", cmd)
        length = struct.unpack(">i", self._socket.recv(4))[0]
        if length > self._max_data_length:
            LOGGER.warning(
                "Skip reading visibilities! Length oversized! %s>%s",
                length,
                self._max_data_length,
            )
            return
        elif length <= 0:
            # Force reconnect for the next readout
            self._disconnect()
        LOGGER.debug("Length %s", length)
        for _ in range(0, length):
            try:
                data.append(struct.unpack(">b", self._socket.recv(1))[0])
            except struct.error as err:
                # not logging this as error as it would be logged on every read cycle
                LOGGER.debug(err)
        LOGGER.debug("Read %d visibilities", length)
        self.visibilities.parse(data)
