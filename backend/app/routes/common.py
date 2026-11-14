from typing import Annotated
from fastapi import Depends, Query
from app.utils.auth import identity
from app.config.database import get_db

Owner = Annotated[str, Depends(identity)]
DB = Annotated[object, Depends(get_db)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=10000)]


def ok(data, **meta):
    return {"data": data, "meta": meta}
