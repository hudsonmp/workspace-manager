import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models import BundleResponse, ShelveRequest, SuggestNameRequest, TabData
from ..services.naming import suggest_name

router = APIRouter()


@router.post("/shelve", response_model=BundleResponse)
async def shelve_tabs(req: ShelveRequest):
    if not req.tabs:
        raise HTTPException(400, "No tabs provided")

    # Filter chrome:// and extension URLs
    valid_tabs = [
        t for t in req.tabs
        if t.url and not t.url.startswith(("chrome://", "chrome-extension://", "about:"))
    ]
    if not valid_tabs:
        raise HTTPException(400, "No valid tabs to shelve")

    # Dedupe check: same URLs shelved within last 60 seconds
    db = await get_db()
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        recent = await db.execute_fetchall(
            "SELECT id FROM bundles WHERE created_at > ? ORDER BY created_at DESC LIMIT 1",
            (cutoff,)
        )
        if recent:
            recent_id = recent[0]["id"]
            recent_tabs = await db.execute_fetchall(
                "SELECT url FROM tabs WHERE bundle_id = ? ORDER BY position",
                (recent_id,)
            )
            recent_urls = {r["url"] for r in recent_tabs}
            new_urls = {t.url for t in valid_tabs}
            if recent_urls == new_urls:
                # Duplicate — return existing bundle
                return await _build_bundle_response(db, recent_id)

        # Generate name
        titles = [t.title or "" for t in valid_tabs]
        urls = [t.url for t in valid_tabs]
        name = req.name or suggest_name(titles, urls)

        bundle_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        await db.execute(
            "INSERT INTO bundles (id, name, space_index, created_at) VALUES (?, ?, ?, ?)",
            (bundle_id, name, req.space_index, now),
        )

        for idx, tab in enumerate(valid_tabs):
            await db.execute(
                "INSERT INTO tabs (bundle_id, url, title, favicon_url, position) VALUES (?, ?, ?, ?, ?)",
                (bundle_id, tab.url, tab.title, tab.favicon_url, idx),
            )

        await db.commit()
        return await _build_bundle_response(db, bundle_id)
    finally:
        await db.close()


@router.get("/bundles", response_model=list[BundleResponse])
async def list_bundles():
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT id FROM bundles ORDER BY created_at DESC"
        )
        result = []
        for row in rows:
            bundle = await _build_bundle_response(db, row["id"])
            result.append(bundle)
        return result
    finally:
        await db.close()


@router.post("/restore/{bundle_id}")
async def restore_bundle(bundle_id: str):
    db = await get_db()
    try:
        bundle = await db.execute_fetchall(
            "SELECT * FROM bundles WHERE id = ?", (bundle_id,)
        )
        if not bundle:
            raise HTTPException(404, "Bundle not found")

        # Mark restored (non-destructive — bundle persists)
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE bundles SET restored_at = ? WHERE id = ?",
            (now, bundle_id),
        )
        await db.commit()

        tabs = await db.execute_fetchall(
            "SELECT url, title, favicon_url FROM tabs WHERE bundle_id = ? ORDER BY position",
            (bundle_id,),
        )
        return {
            "id": bundle_id,
            "name": bundle[0]["name"],
            "tabs": [dict(t) for t in tabs],
        }
    finally:
        await db.close()


@router.delete("/bundles/{bundle_id}")
async def delete_bundle(bundle_id: str):
    db = await get_db()
    try:
        result = await db.execute(
            "DELETE FROM bundles WHERE id = ?", (bundle_id,)
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(404, "Bundle not found")
        return {"deleted": bundle_id}
    finally:
        await db.close()


@router.post("/suggest-name")
async def suggest_bundle_name(req: SuggestNameRequest):
    name = suggest_name(req.titles, req.urls)
    return {"name": name}


async def _build_bundle_response(db, bundle_id: str) -> BundleResponse:
    row = await db.execute_fetchall(
        "SELECT * FROM bundles WHERE id = ?", (bundle_id,)
    )
    if not row:
        raise HTTPException(404, "Bundle not found")
    row = row[0]

    tabs = await db.execute_fetchall(
        "SELECT url, title, favicon_url FROM tabs WHERE bundle_id = ? ORDER BY position",
        (bundle_id,),
    )
    tab_list = [TabData(url=t["url"], title=t["title"], favicon_url=t["favicon_url"]) for t in tabs]

    return BundleResponse(
        id=row["id"],
        name=row["name"],
        space_index=row["space_index"],
        created_at=row["created_at"],
        restored_at=row["restored_at"],
        tabs=tab_list,
        tab_count=len(tab_list),
    )
