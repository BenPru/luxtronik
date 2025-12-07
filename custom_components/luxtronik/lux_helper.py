"""Helper for luxtronik heatpump module."""

# region Imports
from __future__ import annotations

import socket
import struct
import threading
import time

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

LUXTRONIK_SOCKET_READ_SIZE_INTEGER = 4
LUXTRONIK_SOCKET_READ_SIZE_CHAR = 1

LUXTRONIK_PARAMETERS_WRITE = 3002
LUXTRONIK_PARAMETERS_READ = 3003
LUXTRONIK_CALCULATIONS_READ = 3004
LUXTRONIK_VISIBILITIES_READ = 3005


def discover() -> list[tuple[str, int | None]]:
    """Broadcast discovery for Luxtronik heat pumps."""

    results: list[tuple[str, int | None]] = []

    # pylint: disable=too-many-nested-blocks
    for port in LUXTRONIK_DISCOVERY_PORTS:
        LOGGER.info("Send discovery packets to port %s", port)
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server.bind(("", port))
        server.settimeout(LUXTRONIK_DISCOVERY_TIMEOUT)

        # send AIT magic broadcast packet
        magic_bytes = LUXTRONIK_DISCOVERY_MAGIC_PACKET.encode()
        server.sendto(magic_bytes, ("255.255.255.255", port))
        LOGGER.debug("Sending broadcast request %s", magic_bytes)

        while True:
            try:
                recv_bytes, con = server.recvfrom(1024)
                res = recv_bytes.decode("ascii", errors="ignore")
                # if we receive what we just sent, continue
                if res == LUXTRONIK_DISCOVERY_MAGIC_PACKET:
                    continue
                ip_address = con[0]
                res_list = res.split(";")
                # if the response starts with the magic nonsense
                if res.startswith(LUXTRONIK_DISCOVERY_RESPONSE_PREFIX):
                    LOGGER.debug(
                        f"Received valid Luxtronik response from {ip_address}: {str(res_list)}"
                    )
                    try:
                        res_port: int | None = int(res_list[2])
                    except (ValueError, IndexError):
                        res_port = None

                    if res_port is None or res_port < 1 or res_port > 65535:
                        LOGGER.info(
                            f"Response contains [port={res_port}] which is not a valid port number,"
                            "an old Luxtronic software version might be the reason. "
                            "Skipping this port."
                        )
                    elif (ip_address, res_port) not in results:
                        LOGGER.info(
                            f"Discovered Luxtronik heatpump at {ip_address}:{res_port}"
                        )
                        results.append((ip_address, res_port))

                else:
                    LOGGER.debug(
                        f"Skipping invalid response from {ip_address}: {str(res_list)}"
                    )

            # if the timeout triggers, go on and use the other broadcast port
            except socket.timeout:
                break
        server.close()
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


def get_manufacturer_firmware_url_by_model(model: str, default_id: int) -> str:
    """Return the manufacturer firmware download url."""
    layout_id = 0

    if model is None:
        layout_id = default_id
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
    except OSError as err:
        if err.errno == 107:  # Socket not connected
            return True
        LOGGER.exception(
            "Unexpected exception when checking if a socket is closed", exc_info=err
        )
        return False
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
        safe: bool = True,
    ) -> None:
        self._lock = threading.Lock()
        self._socket = None
        self._host = host
        self._port = port
        self._socket_timeout = socket_timeout
        self._max_data_length = max_data_length
        self.calculations = Calculations()
        self.parameters = Parameters(safe=safe)
        self.visibilities = Visibilities()

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

    def connect(self) -> None:
        """Establish connection to the heatpump."""
        with self._lock:
            if self._socket is None or _is_socket_closed(self._socket):
                self._disconnect()  # Ensure clean state
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self._socket_timeout)
                try:
                    self._socket.connect((self._host, self._port))
                    LOGGER.info(
                        "Connected to Luxtronik heatpump %s:%s with timeout %.1fs",
                        self._host,
                        self._port,
                        self._socket_timeout,
                    )
                except (socket.timeout, OSError) as err:
                    LOGGER.error("Failed to connect: %s", err)
                    self._disconnect()
                    raise

    def read(self):
        """Read data from heatpump."""
        self._read_write(write=False)

    def write(self):
        """Write parameter to heatpump."""
        self._read_write(write=True)

    def _read_write(self, write=False):
        try:
            self.connect()
        except Exception as err:
            LOGGER.error("Connection failed during read/write: %s", err)
            return

        if write:
            self._write()

        self._read()

    def _read(self):
        self._read_data(
            LUXTRONIK_PARAMETERS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            self.parameters,
            "parameters",
        )
        self._read_data(
            LUXTRONIK_CALCULATIONS_READ,
            LUXTRONIK_SOCKET_READ_SIZE_INTEGER,
            self.calculations,
            "calculations",
        )
        self._read_data(
            LUXTRONIK_VISIBILITIES_READ,
            LUXTRONIK_SOCKET_READ_SIZE_CHAR,
            self.visibilities,
            "visibilities",
        )

    def _write(self):
        for index, value in self.parameters.queue.items():
            if isinstance(value, float):
                value = int(value)

            if not isinstance(index, int) or not isinstance(value, int):
                LOGGER.warning("Parameter id '%s' or value '%s' invalid!", index, value)
                continue
            LOGGER.info("Parameter '%d' set to '%s'", index, value)
            data = struct.pack(">iii", LUXTRONIK_PARAMETERS_WRITE, index, value)
            LOGGER.debug("Data %s", data)
            self._socket.sendall(data)
            cmd = struct.unpack(">i", self._socket.recv(4))[0]
            LOGGER.debug("Command %s", cmd)
            val = struct.unpack(">i", self._socket.recv(4))[0]
            LOGGER.debug("Value %s", val)
        # Flush queue after writing all values
        self.parameters.queue = {}
        # Give the heatpump a short time to handle the value changes/calculations:
        # Todo: Change methods to async
        # await asyncio.sleep(WAIT_TIME_WRITE_PARAMETER)

    def _read_data(
        self, command: int, item_size: int, parser, label: str, retries: int = 4
    ) -> None:
        """Generic method to read data from the socket with timeout and retry handling."""
        data = []

        for attempt in range(retries + 1):
            try:
                # check if connection still exists before reading
                if self._socket is None or _is_socket_closed(self._socket):
                    LOGGER.warning(
                        "Socket is not connected. Attempting to reconnect..."
                    )
                    self.connect()

                self._socket.sendall(struct.pack(">ii", command, 0))
                cmd = struct.unpack(">i", self._socket.recv(4))[0]
                LOGGER.debug("Command %s (%s)", cmd, label)

                # Optional status field for calculations
                if command == LUXTRONIK_CALCULATIONS_READ:
                    stat = struct.unpack(">i", self._socket.recv(4))[0]
                    LOGGER.debug("Stat %s", stat)

                length = struct.unpack(">i", self._socket.recv(4))[0]
                if length > self._max_data_length:
                    LOGGER.warning(
                        "Skip reading %s! Length oversized! %s > %s",
                        label,
                        length,
                        self._max_data_length,
                    )
                    return
                elif length <= 0 and command == LUXTRONIK_VISIBILITIES_READ:
                    LOGGER.warning(
                        "Invalid length for %s (%s), forcing disconnect", label, length
                    )
                    self._disconnect()
                    return

                LOGGER.debug("Length %s (%s)", length, label)

                fmt = ">i" if item_size == LUXTRONIK_SOCKET_READ_SIZE_INTEGER else ">b"

                for _ in range(length):
                    try:
                        raw = self._socket.recv(item_size)
                        data.append(struct.unpack(fmt, raw)[0])
                    except (struct.error, socket.timeout) as err:
                        LOGGER.debug("Error reading %s item: %s", label, err)

                LOGGER.debug("Read %d %s items", length, label)
                parser.parse(data)
                return  # Success, exit after first successful attempt

            except (socket.timeout, ConnectionResetError, OSError) as err:
                LOGGER.warning(
                    "Error while reading %s (attempt %d/%d): %s",
                    label,
                    attempt + 1,
                    retries + 1,
                    err,
                )
                self._disconnect()

                if attempt < retries:
                    delay = 1  # min(30, 10 * attempt)  # cap delay to avoid long waits
                    LOGGER.warning("Waiting %s seconds before retrying...", delay)
                    time.sleep(delay)
                else:
                    LOGGER.error("All attempts to read %s failed.", label)
                    return

            except Exception as err:
                LOGGER.error(
                    "Unexpected error during read of %s: %s", label, err, exc_info=True
                )
                self._disconnect()
                return
