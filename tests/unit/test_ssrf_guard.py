import pytest
from fastapi import HTTPException

from app.utils.ssrf_guard import validate_url_async


@pytest.mark.asyncio
async def test_validate_url_async_blocks_localhost() -> None:
    with pytest.raises(HTTPException) as exc:
        await validate_url_async("http://localhost/internal")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_validate_url_async_rejects_invalid_scheme() -> None:
    with pytest.raises(HTTPException) as exc:
        await validate_url_async("ftp://example.com/file")
    assert exc.value.status_code == 400
