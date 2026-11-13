"""Stage pinned stock footage locally for a repeatable film edit."""

from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx

_CDN_HOSTS = {"videos.pexels.com", "cdn.pixabay.com", "assets.mixkit.co"}
_SAFE_FILENAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,125}\.[a-zA-Z0-9]{1,8}")
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}
_CHUNK_BYTES = 1024 * 1024
DEFAULT_MAX_BYTES = 256 * _CHUNK_BYTES


class StockAssetError(ValueError):
    """A stock asset could not be validated or staged."""


def _approved_url(url: str) -> bool:
    if any(char.isspace() or ord(char) < 32 for char in url):
        return False
    if "\\" in url:
        return False
    try:
        parts = urlsplit(url)
        return (
            parts.scheme == "https"
            and parts.hostname in _CDN_HOSTS
            and parts.port in (None, 443)
            and parts.username is None
            and parts.password is None
            and bool(parts.path.strip("/"))
            and not parts.fragment
        )
    except ValueError:
        return False


def _download(client: httpx.Client, url: str, path: Path, checksum: str, max_bytes: int) -> None:
    temporary: Path | None = None
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            length = response.headers.get("Content-Length")
            if length is not None and length.isdecimal() and int(length) > max_bytes:
                raise StockAssetError(f"download exceeds {max_bytes} bytes")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise StockAssetError("CDN did not return an unencoded file")

            digest = hashlib.sha256()
            size = 0
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as file:
                temporary = Path(file.name)
                for chunk in response.iter_bytes(chunk_size=_CHUNK_BYTES):
                    size += len(chunk)
                    if size > max_bytes:
                        raise StockAssetError(f"download exceeds {max_bytes} bytes")
                    digest.update(chunk)
                    file.write(chunk)

        if temporary is None or not size or digest.hexdigest() != checksum:
            raise StockAssetError("download SHA-256 did not match the manifest")
        temporary.replace(path)
    except httpx.HTTPStatusError as exc:
        raise StockAssetError(f"CDN returned HTTP {exc.response.status_code}") from None
    except httpx.HTTPError as exc:
        raise StockAssetError(f"CDN request failed ({type(exc).__name__})") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def stage_assets(
    assets: dict[str, dict], directory: Path, *, max_bytes: int = DEFAULT_MAX_BYTES
) -> dict[str, Path]:
    """Verify or fetch each manifest entry's ``url``, ``sha256``, and local ``file``.

    Additional metadata belongs to the film's source ledger. Files are published
    to the cache only after checksum validation, and downloads never follow redirects.
    ``max_bytes`` limits the size of each individual source.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    entries: dict[str, tuple[str, str, Path]] = {}
    filenames: set[str] = set()
    for asset_id, entry in assets.items():
        if not isinstance(entry, dict):
            raise StockAssetError(f"{asset_id}: expected a manifest object")
        url, checksum, name = (entry.get(field) for field in ("url", "sha256", "file"))
        if not isinstance(url, str) or not _approved_url(url):
            raise StockAssetError(f"{asset_id}: expected a direct HTTPS stock CDN URL")
        if not isinstance(checksum, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", checksum):
            raise StockAssetError(f"{asset_id}: expected a 64-character SHA-256 digest")
        if (
            not isinstance(name, str)
            or not _SAFE_FILENAME.fullmatch(name)
            or name.split(".", 1)[0].upper() in _RESERVED_NAMES
        ):
            raise StockAssetError(f"{asset_id}: expected a safe local filename")
        if name.lower() in filenames:
            raise StockAssetError(f"{asset_id}: duplicate local filename {name}")
        filenames.add(name.lower())
        entries[asset_id] = (url, checksum.lower(), directory / name)

    directory.mkdir(parents=True, exist_ok=True)
    staged: dict[str, Path] = {}
    with httpx.Client(
        timeout=30.0, follow_redirects=False, headers={"Accept-Encoding": "identity"}
    ) as client:
        for asset_id, (url, checksum, path) in entries.items():
            try:
                if path.is_symlink() or (path.exists() and not path.is_file()):
                    raise StockAssetError("destination must be a regular file")
                if path.is_file() and 0 < path.stat().st_size <= max_bytes:
                    with path.open("rb") as file:
                        if hashlib.file_digest(file, "sha256").hexdigest() == checksum:
                            staged[asset_id] = path
                            continue
                _download(client, url, path, checksum, max_bytes)
                staged[asset_id] = path
            except (OSError, StockAssetError) as exc:
                raise StockAssetError(f"{asset_id}: {exc}") from exc
    return staged
