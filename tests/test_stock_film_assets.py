import hashlib

import httpx
import pytest
import respx

from daily_video_factory.stock_film_assets import StockAssetError, stage_assets

URL = "https://videos.pexels.com/video-files/1/1-hd.mp4"
CONTENTS = b"locked footage"
ASSET = {
    "url": URL,
    "sha256": hashlib.sha256(CONTENTS).hexdigest(),
    "file": "night-street.mp4",
    "creator": "Example creator",
}


def test_rebuild_uses_verified_cache_and_replaces_corruption(tmp_path):
    expected = tmp_path / ASSET["file"]
    expected.write_bytes(b"corrupt cache")
    with respx.mock as router:
        route = router.get(URL).mock(return_value=httpx.Response(200, content=CONTENTS))
        assert stage_assets({"street": ASSET}, tmp_path) == {"street": expected}
        assert expected.read_bytes() == CONTENTS
        assert stage_assets({"street": ASSET}, tmp_path) == {"street": expected}
        assert route.call_count == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("url", "http://videos.pexels.com/clip.mp4", "HTTPS stock CDN"),
        ("url", "https://videos.pexels.com.evil.test/clip.mp4", "HTTPS stock CDN"),
        ("url", "https://username@videos.pexels.com/clip.mp4", "HTTPS stock CDN"),
        ("url", "https://videos.pexels.com:1234/clip.mp4", "HTTPS stock CDN"),
        ("sha256", "bad", "64-character SHA-256"),
        ("file", "../escaped.mp4", "safe local filename"),
        ("file", "nested\\escaped.mp4", "safe local filename"),
        ("file", "NUL.backup.mp4", "safe local filename"),
    ],
)
def test_validates_entire_manifest_before_creating_cache(tmp_path, field, value, message):
    cache = tmp_path / "cache"
    with pytest.raises(StockAssetError, match=f"bad: .*{message}"):
        stage_assets({"street": ASSET, "bad": {**ASSET, field: value}}, cache)
    assert not cache.exists()


def test_rejects_case_insensitive_filename_collisions(tmp_path):
    with pytest.raises(StockAssetError, match="duplicate local filename"):
        stage_assets(
            {"street": ASSET, "duplicate": {**ASSET, "file": ASSET["file"].upper()}}, tmp_path
        )


@pytest.mark.parametrize(
    ("make_response", "max_bytes", "message"),
    [
        (lambda: httpx.Response(200, content=b"bad digest"), 32, "SHA-256"),
        (lambda: httpx.Response(200, content=CONTENTS), 4, "exceeds 4 bytes"),
        (
            lambda: httpx.Response(200, stream=httpx.ByteStream(CONTENTS)),
            4,
            "exceeds 4 bytes",
        ),
        (
            lambda: httpx.Response(302, headers={"Location": "https://unapproved.test/clip"}),
            32,
            "HTTP 302",
        ),
    ],
)
def test_failed_fetch_preserves_existing_file_and_removes_temp(
    tmp_path, make_response, max_bytes, message
):
    expected = tmp_path / ASSET["file"]
    expected.write_bytes(b"old")
    with respx.mock as router:
        router.get(URL).mock(return_value=make_response())
        with pytest.raises(StockAssetError, match=f"street: .*{message}"):
            stage_assets({"street": ASSET}, tmp_path, max_bytes=max_bytes)
    assert expected.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [expected]
