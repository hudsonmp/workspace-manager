from pydantic import BaseModel


class TabData(BaseModel):
    url: str
    title: str | None = None
    favicon_url: str | None = None


class ShelveRequest(BaseModel):
    tabs: list[TabData]
    space_index: int | None = None
    name: str | None = None


class BundleResponse(BaseModel):
    id: str
    name: str
    space_index: int | None
    created_at: str
    restored_at: str | None
    tabs: list[TabData]
    tab_count: int


class SuggestNameRequest(BaseModel):
    titles: list[str]
    urls: list[str] | None = None


class SpaceNameUpdate(BaseModel):
    name: str
