from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models import SpaceNameUpdate
from ..services.spaces import get_active_space_index, get_display_spaces

router = APIRouter()


@router.get("/spaces")
async def list_spaces():
    """List all Spaces with their names."""
    display_data = get_display_spaces()
    db = await get_db()
    try:
        named = await db.execute_fetchall("SELECT * FROM space_names")
        name_map = {r["space_index"]: r["name"] for r in named}

        spaces = []
        if display_data:
            for display in display_data:
                for space in display["spaces"]:
                    if space["type"] == "user":
                        idx = space["index"]
                        spaces.append({
                            "index": idx,
                            "space_id": space["space_id"],
                            "name": name_map.get(idx, f"Desktop {idx}"),
                        })
        else:
            # Fallback: return named spaces from DB
            for idx, name in name_map.items():
                spaces.append({"index": idx, "space_id": None, "name": name})

        return {"spaces": spaces}
    finally:
        await db.close()


@router.get("/active-space")
async def active_space():
    """Get the currently active Space and its name."""
    idx = get_active_space_index()
    if idx is None:
        return {"index": None, "name": "Unknown"}

    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT name FROM space_names WHERE space_index = ?", (idx,)
        )
        name = row[0]["name"] if row else f"Desktop {idx}"
        return {"index": idx, "name": name}
    finally:
        await db.close()


@router.put("/spaces/{space_index}/name")
async def set_space_name(space_index: int, req: SpaceNameUpdate):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO space_names (space_index, name) VALUES (?, ?) "
            "ON CONFLICT(space_index) DO UPDATE SET name = ?",
            (space_index, req.name, req.name),
        )
        await db.commit()
        return {"index": space_index, "name": req.name}
    finally:
        await db.close()
