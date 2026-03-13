"""
macOS Space detection via CGS private APIs (SkyLight framework).

Uses ctypes to call undocumented CoreGraphics Server functions.
These APIs have been stable since macOS 10.6 through macOS 15.
"""

import ctypes
import ctypes.util
from ctypes import c_int, c_uint32, c_void_p


def _load_skylight():
    try:
        return ctypes.cdll.LoadLibrary(
            "/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight"
        )
    except OSError:
        return None


_skylight = _load_skylight()


def get_active_space_id() -> int | None:
    """Get the CGS space ID of the currently active Space."""
    if not _skylight:
        return None
    try:
        conn = _skylight.CGSMainConnectionID()
        space_id = _skylight.CGSGetActiveSpace(conn)
        return space_id if space_id > 0 else None
    except Exception:
        return None


def get_display_spaces() -> list[dict] | None:
    """
    Get all spaces across all displays via CGSCopyManagedDisplaySpaces.
    Returns a list of {display_id, spaces: [{space_id, type, index}]}.

    The space index (ordinal position left-to-right) is more stable than
    the CGS space ID across reboots.
    """
    if not _skylight:
        return None

    try:
        from Quartz import (
            CGSCopyManagedDisplaySpaces,
            CGMainDisplayID,
        )

        conn = _skylight.CGSMainConnectionID()
        display_spaces = CGSCopyManagedDisplaySpaces(conn)

        if not display_spaces:
            return None

        result = []
        for display_info in display_spaces:
            display_id = display_info.get("Display Identifier", "")
            spaces_list = display_info.get("Spaces", [])
            spaces = []
            for idx, space in enumerate(spaces_list):
                space_id = space.get("ManagedSpaceID", 0)
                space_type = space.get("type64", 0)
                # type64: 0 = user space, 4 = fullscreen app space
                spaces.append({
                    "space_id": space_id,
                    "type": "user" if space_type == 0 else "fullscreen",
                    "index": idx + 1,
                })
            result.append({"display_id": display_id, "spaces": spaces})

        return result
    except (ImportError, Exception):
        return None


def get_space_index_for_id(space_id: int) -> int | None:
    """Convert a CGS space ID to its ordinal index (1-based)."""
    displays = get_display_spaces()
    if not displays:
        return None
    for display in displays:
        for space in display["spaces"]:
            if space["space_id"] == space_id:
                return space["index"]
    return None


def get_active_space_index() -> int | None:
    """Get the ordinal index (1-based) of the currently active Space."""
    space_id = get_active_space_id()
    if space_id is None:
        return None
    return get_space_index_for_id(space_id)
