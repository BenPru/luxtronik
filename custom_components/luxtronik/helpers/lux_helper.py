"""Helper for luxtronik heatpump module."""
import socket

from ..const import LOGGER


def discover():
    """Broadcast discovery for luxtronik heatpumps."""

    for p in (4444, 47808):
        LOGGER.debug(f"Send discovery packets to port {p}")
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server.bind(("", p))
        server.settimeout(2)

        # send AIT magic broadcast packet
        data = "2000;111;1;\x00"
        server.sendto(data.encode(), ("<broadcast>", p))
        LOGGER.debug(f'Sending broadcast request "{data.encode()}"')

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
                    LOGGER.debug(f'Received answer from {ip} "{res}"')
                    try:
                        port = int(res[2])
                    except ValueError:
                        LOGGER.debug(
                            "Response did not contain a valid port number, an old Luxtronic software version might be the reason."
                        )
                        port = None
                    return (ip, port)
                # if not, continue
                else:
                    LOGGER.debug(
                        f"Received answer, but with wrong magic bytes, from {ip} skip this one"
                    )
                    continue
            # if the timeout triggers, go on an use the other broadcast port
            except socket.timeout:
                break


def get_manufacturer_by_model(model: str) -> str:
    """Return the manufacturer."""
    models_AlphaInnotec = ['LWP','LWV','MSW','SWC','SWP']
    models_Novelan      = ['BW','LA','LD','LI','SI','ZLW']

    if model is None:
        return None
    if model.startswith(tuple(models_Novelan)):
        return "Novelan"
    if model.startswith(tuple(models_AlphaInnotec)):
        return "Alpha Innotec"
    return None
