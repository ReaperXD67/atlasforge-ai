from pathlib import Path

import pytest

from daily_video_factory.browser_capture import BrowserCaptureRecipe, PlaywrightCliCaptureRunner
from daily_video_factory.media.subtitles import _merge_short_cues
from daily_video_factory.models import SubtitleCue
from daily_video_factory.presenter import PresenterExpressionLibrary


def test_nexa_manifest_has_twenty_static_expressions() -> None:
    library = PresenterExpressionLibrary(
        Path("assets/biznex/nexa-expressions/manifest.json")
    )
    assert len(library.names()) == 20
    assert library.choose("Why did this payment fail?") == "questioning"
    assert library.choose("The runtime implementation is exact") == "focused"
    assert library.resolve("closing").is_file()


def test_expression_plan_enforces_five_second_hold() -> None:
    library = PresenterExpressionLibrary(
        Path("assets/biznex/nexa-expressions/manifest.json")
    )
    cues = library.plan_cues(
        [(0, "concerned"), (2, "idea"), (11, "confident")],
        total_duration_seconds=18,
    )
    assert [(cue.start_seconds, cue.expression) for cue in cues] == [
        (0, "concerned"),
        (5.0, "idea"),
        (11, "confident"),
    ]
    assert all(cue.end_seconds - cue.start_seconds >= 5 for cue in cues)


def test_browser_recipe_rejects_unapproved_state_change(tmp_path: Path) -> None:
    recipe_file = tmp_path / "capture.yaml"
    recipe_file.write_text(
        """
name: safety test
start_url: https://example.com
allowed_state_changing_actions: [Start simulation]
steps:
  - id: unsafe
    filename: unsafe.png
    actions:
      - {type: click, target: Approve action, state_changing: true}
""".strip(),
        encoding="utf-8",
    )
    recipe = BrowserCaptureRecipe.from_yaml(recipe_file)
    with pytest.raises(ValueError, match="not allowlisted"):
        PlaywrightCliCaptureRunner(recipe, tmp_path / "captures")


def test_browser_refs_support_frame_prefixes() -> None:
    assert PlaywrightCliCaptureRunner.REF_PATTERN.findall(
        'button "Command center" [ref=f1e9]'
    ) == ["f1e9"]


def test_short_captions_merge_to_readable_holds() -> None:
    cues = [
        SubtitleCue(index=1, start_seconds=0, end_seconds=2, text="One"),
        SubtitleCue(index=2, start_seconds=2, end_seconds=4, text="two"),
        SubtitleCue(index=3, start_seconds=4, end_seconds=7, text="three"),
        SubtitleCue(index=4, start_seconds=7, end_seconds=9, text="four"),
    ]
    merged = _merge_short_cues(cues, 5)
    assert len(merged) == 1
    assert merged[0].text == "One two three four"
    assert merged[0].end_seconds - merged[0].start_seconds == 9
