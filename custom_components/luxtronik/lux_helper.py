"""Helper for luxtronik heatpump module."""
# -*- coding: utf-8 -*-
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

WAIT_TIME_WRITE_PARAMETER = 0.2


def discover():
    """Broadcast discovery for luxtronik heatpumps."""

    for search_port in (4444, 47808):
        # LOGGER.debug(f"Send discovery packets to port {search_port}")
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server.bind(("", search_port))
        server.settimeout(2)

        # send AIT magic broadcast packet
        data = "2000;111;1;\x00"
        server.sendto(data.encode(), ("<broadcast>", search_port))
        # LOGGER.debug(f'Sending broadcast request "{data.encode()}"')

        while True:
            try:
                res, con = server.recvfrom(1024)
                res = res.decode("ascii", errors="ignore")
                # if we receive what we just sent, continue
                if res == data:
                    continue
                ip = con[0]
                # if the response starts with the magic nonsense
                if res.startswith("2500;111;"):
                    res = res.split(";")
                    # LOGGER.debug(f'Received answer from {ip} "{res}"')
                    try:
                        port = int(res[2])
                    except ValueError:
                        # LOGGER.debug(
                        #     "Response did not contain a valid port number, an old Luxtronic software version might be the reason."
                        # )
                        port = None
                    return (ip, port)
                # if not, continue
                # else:
                # LOGGER.debug(
                #     f"Received answer, but with wrong magic bytes, from {ip} skip this one"
                # )
                # continue
            # if the timeout triggers, go on an use the other broadcast port
            except socket.timeout:
                break


def get_manufacturer_by_model(model: str) -> str | None:
    """Return the manufacturer."""
    if model is None:
        return None
    if model.startswith(tuple(LUX_MODELS_NOVELAN)):
        return "Novelan"
    if model.startswith(tuple(LUX_MODELS_ALPHA_INNOTEC)):
        return "Alpha Innotec"
    return None


def get_firmware_download_id(installed_version: str) -> int | None:
    """Return the heatpump firmware id for the download portal."""
    if installed_version is None:
        return None
    elif installed_version.startswith("V1."):
        return 0
    elif installed_version.startswith("V2."):
        return 1
    elif installed_version.startswith("V3."):
        return 2
    elif installed_version.startswith("V4."):
        return 3
    elif installed_version.startswith("F1."):
        return 4
    elif installed_version.startswith("WWB1."):
        return 5
    elif installed_version.startswith("smo"):
        return 6
    return None


def get_manufacturer_firmware_url_by_model(self, model: str) -> str:
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


def is_socket_closed(sock: socket.socket) -> bool:
    try:
        # this will try to read bytes without blocking and also without removing them from buffer (peek only)
        data = sock.recv(16, socket.MSG_DONTWAIT | socket.MSG_PEEK)
        if len(data) == 0:
            return True
    except BlockingIOError:
        return False  # socket is open and reading from it would block
    except ConnectionResetError:
        return True  # socket was closed for some other reason
    except Exception as err:
        LOGGER.exception(
            "Unexpected exception when checking if a socket is closed", exc_info=err
        )
        return False
    return False


class Luxtronik:
    """Main luxtronik class."""

    def __init__(self, host, port, safe=True):
        self._lock = threading.Lock()
        self._socket = None
        self._host = host
        self._port = port
        self.calculations = Calculations()
        self.parameters = Parameters(safe=safe)
        self.visibilities = Visibilities()
        self.read()

    def __del__(self):
        if self._socket is not None:
            if not is_socket_closed(self._socket):
                self._socket.close()
            self._socket = None
            LOGGER.info(
                "Disconnected from Luxtronik heatpump %s:%s", self._host, self._port
            )

    def read(self):
        """Read data from heatpump."""
        self._read_write(write=False)

    def write(self):
        """Write patameter to heatpump."""
        self._read_write(write=True)

    def _read_write(self, write=False):
        # Ensure only one socket operation at the same time
        with self._lock:
            is_none = self._socket is None
            if is_none:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if is_none or is_socket_closed(self._socket):
                self._socket.connect((self._host, self._port))
                LOGGER.info(
                    "Connected to Luxtronik heatpump %s:%s", self._host, self._port
                )
            if write:
                return self._write()
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
        # Read the new values based on our param changes:
        self._read_parameters()
        self._read_calculations()
        self._read_visibilities()

    def _read_parameters(self):
        data = []
        self._socket.sendall(struct.pack(">ii", 3003, 0))
        cmd = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Command %s", cmd)
        length = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Length %s", length)
        for _ in range(0, length):
            try:
                data.append(struct.unpack(">i", self._socket.recv(4))[0])
            except struct.error as err:
                # not logging this as error as it would be logged on every read cycle
                LOGGER.debug(err)
        LOGGER.info("Read %d parameters", length)
        self.parameters.parse(data)

    def _read_calculations(self):
        data = []
        self._socket.sendall(struct.pack(">ii", 3004, 0))
        cmd = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Command %s", cmd)
        stat = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Stat %s", stat)
        length = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Length %s", length)
        for _ in range(0, length):
            try:
                data.append(struct.unpack(">i", self._socket.recv(4))[0])
            except struct.error as err:
                # not logging this as error as it would be logged on every read cycle
                LOGGER.debug(err)
        LOGGER.info("Read %d calculations", length)
        self.calculations.parse(data)

    def _read_visibilities(self):
        data = []
        self._socket.sendall(struct.pack(">ii", 3005, 0))
        cmd = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Command %s", cmd)
        length = struct.unpack(">i", self._socket.recv(4))[0]
        LOGGER.debug("Length %s", length)
        for _ in range(0, length):
            try:
                data.append(struct.unpack(">b", self._socket.recv(1))[0])
            except struct.error as err:
                # not logging this as error as it would be logged on every read cycle
                LOGGER.debug(err)
        LOGGER.info("Read %d visibilities", length)
        self.visibilities.parse(data)
