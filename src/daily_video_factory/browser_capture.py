from __future__ import annotations

import re
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
import yaml
from pydantic import BaseModel, Field, HttpUrl

from .artifacts import atomic_write


class BrowserAction(BaseModel):
    type: Literal["goto", "reload", "click", "fill", "select", "check", "press", "scroll", "wait"]
    target: str = ""
    value: str = ""
    wait_after_ms: int = Field(default=1200, ge=0, le=30000)
    state_changing: bool = False


class BrowserCaptureStep(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    filename: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(png|jpg|jpeg|webp)$")
    url: HttpUrl | None = None
    expected_text: list[str] = Field(default_factory=list)
    actions: list[BrowserAction] = Field(default_factory=list)
    full_page: bool = False
    fallback_url: HttpUrl | None = None


class BrowserCaptureRecipe(BaseModel):
    name: str
    start_url: HttpUrl
    session: str = Field(default="atlasforge-capture", pattern=r"^[A-Za-z0-9_-]+$")
    viewport_width: int = Field(default=1440, ge=800, le=3840)
    viewport_height: int = Field(default=900, ge=600, le=2160)
    settle_ms: int = Field(default=1000, ge=0, le=10000)
    retry_count: int = Field(default=1, ge=0, le=3)
    allowed_state_changing_actions: list[str] = Field(default_factory=list)
    forbidden_click_text: list[str] = Field(default_factory=list)
    steps: list[BrowserCaptureStep]

    @classmethod
    def from_yaml(cls, path: Path) -> BrowserCaptureRecipe:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


class PlaywrightCliCaptureRunner:
    """Execute a declarative capture recipe through the isolated Playwright CLI session."""

    # Playwright uses both e9 and frame-prefixed refs such as f1e9.
    REF_PATTERN = re.compile(r"\[ref=([A-Za-z0-9]+)\]")

    def __init__(self, recipe: BrowserCaptureRecipe, output_dir: Path) -> None:
        self.recipe = recipe
        self.output_dir = output_dir.resolve()
        self.npx = shutil.which("npx") or shutil.which("npx.cmd")
        if not self.npx:
            raise RuntimeError("npx is required for browser capture")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, str]] = []
        self._validate_actions()

    def _validate_actions(self) -> None:
        allowed = {item.casefold() for item in self.recipe.allowed_state_changing_actions}
        forbidden = {item.casefold() for item in self.recipe.forbidden_click_text}
        for step in self.recipe.steps:
            for action in step.actions:
                target = action.target.strip().casefold()
                if action.type == "click" and target in forbidden:
                    raise ValueError(f"Capture recipe attempts forbidden click: {action.target}")
                if action.state_changing and target not in allowed:
                    raise ValueError(
                        f"State-changing action is not allowlisted: {action.target}"
                    )

    def _command(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        command = [
            self.npx,
            "--yes",
            "@playwright/cli",
            f"-s={self.recipe.session}",
            *args,
        ]
        return subprocess.run(
            command,
            cwd=self.output_dir,
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def _find_ref(self, target: str, preferred_roles: tuple[str, ...] = ()) -> str:
        result = self._command("find", target, check=False)
        output = result.stdout + result.stderr
        if preferred_roles:
            target_key = target.casefold()
            for line in output.splitlines():
                line_key = line.casefold()
                if target_key in line_key and any(role in line_key for role in preferred_roles):
                    match = self.REF_PATTERN.search(line)
                    if match:
                        return match.group(1)
        matches = self.REF_PATTERN.findall(output)
        if not matches:
            raise RuntimeError(f"Could not find browser target: {target}")
        return matches[0]

    def _wait_for_text(self, text: str, timeout_seconds: float = 25.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                self._find_ref(text)
                return
            except RuntimeError as exc:
                last_error = exc
                time.sleep(0.6)
        raise RuntimeError(f"Timed out waiting for browser text: {text}") from last_error

    def _run_action(self, action: BrowserAction) -> None:
        if action.type == "goto":
            self._command("goto", action.value or action.target)
        elif action.type == "reload":
            self._command("reload")
        elif action.type in {"click", "fill", "select", "check"}:
            roles = {
                "click": ("button", "link"),
                "fill": ("textbox", "spinbutton", "combobox"),
                "select": ("combobox",),
                "check": ("checkbox",),
            }[action.type]
            ref = self._find_ref(action.target, roles)
            args = [action.type, ref]
            if action.type in {"fill", "select"}:
                args.append(action.value)
            self._command(*args)
        elif action.type == "press":
            self._command("press", action.value or action.target)
        elif action.type == "scroll":
            self._command("mousewheel", "0", action.value or "650")
        elif action.type == "wait":
            pass
        time.sleep(action.wait_after_ms / 1000)

    def _capture_live(self, step: BrowserCaptureStep) -> Path:
        if step.url:
            self._command("goto", str(step.url))
            time.sleep(self.recipe.settle_ms / 1000)
        for action in step.actions:
            self._run_action(action)
        for expected in step.expected_text:
            self._wait_for_text(expected)
        output = self.output_dir / step.filename
        args = ["screenshot", "--filename", output.name]
        if step.full_page:
            args.append("--full-page")
        self._command(*args)
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError(f"Playwright did not create {output}")
        return output

    def _capture_fallback(self, step: BrowserCaptureStep) -> tuple[Path, str]:
        output = self.output_dir / step.filename
        source = "live evidence unavailable"
        if step.fallback_url:
            source = "repository fallback"
            suffix = Path(urlparse(str(step.fallback_url)).path).suffix.casefold()
            if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                response = httpx.get(str(step.fallback_url), follow_redirects=True, timeout=60)
                response.raise_for_status()
                output.write_bytes(response.content)
                return output, source
            self._command("goto", str(step.fallback_url))
            time.sleep(self.recipe.settle_ms / 1000)
        args = ["screenshot", "--filename", output.name]
        if step.full_page:
            args.append("--full-page")
        self._command(*args)
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError(f"Playwright did not create fallback capture {output}")
        return output, source

    def run(self) -> Path:
        self._command("open", str(self.recipe.start_url))
        self._command(
            "resize",
            str(self.recipe.viewport_width),
            str(self.recipe.viewport_height),
        )
        time.sleep(self.recipe.settle_ms / 1000)
        try:
            for step in self.recipe.steps:
                error = ""
                source = "live app"
                captured: Path | None = None
                for attempt in range(self.recipe.retry_count + 1):
                    try:
                        captured = self._capture_live(step)
                        break
                    except Exception as exc:
                        error = str(exc)
                        if attempt < self.recipe.retry_count:
                            self._command("reload", check=False)
                            time.sleep(self.recipe.settle_ms / 1000)
                if captured is None:
                    captured, source = self._capture_fallback(step)
                self.records.append(
                    {
                        "id": step.id,
                        "file": captured.name,
                        "source": source,
                        "url": str(step.url or self.recipe.start_url),
                        "captured_at": datetime.now(UTC).isoformat(),
                        "verified": "; ".join(step.expected_text) or "visual state",
                        "note": error if source != "live app" else "",
                    }
                )
        finally:
            self._command("close", check=False)
        manifest = self.output_dir / "capture-manifest.md"
        lines = [
            f"# Capture manifest — {self.recipe.name}",
            "",
            "| Capture | File | Source | URL | UTC timestamp | Verified state | Note |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for record in self.records:
            lines.append(
                "| {id} | `{file}` | {source} | {url} | {captured_at} | {verified} | {note} |".format(
                    **record
                )
            )
        atomic_write(manifest, "\n".join(lines) + "\n")
        return manifest
