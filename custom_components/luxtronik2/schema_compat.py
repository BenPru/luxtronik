"""The schema library the integration builds its schemas with."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Home Assistant ships probatio from 2026.9 and types flow and service schemas
# with it from 2026.10, so the schemas are built with probatio. On 2026.8 and
# older there is no probatio: falling back to voluptuous keeps the modules
# importable, so setup can refuse with the version message (`MIN_HA_VERSION`)
# and the flows can abort with it, instead of "No module named 'probatio'".
# probatio cannot be listed in manifest.json instead - hassfest rejects
# requirements that Home Assistant itself depends on.
if TYPE_CHECKING:
    import probatio as vol
else:
    try:
        import probatio as vol
    except ImportError:  # Home Assistant 2026.8 and older
        import voluptuous as vol

__all__ = ["vol"]
