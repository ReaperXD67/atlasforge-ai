from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest
from test_social_campaign import CHANNEL, NOW, FakeMeta, FakeYouTube

from daily_video_factory import social_campaign, story_publication
from daily_video_factory.exceptions import ConfigurationError
from daily_video_factory.social_campaign import CampaignPost, _post_payload


@pytest.fixture
def story_queue(tmp_path, settings, monkeypatch):
    monkeypatch.setattr(social_campaign, "_clock", lambda value=None: value or NOW)
    project = tmp_path / "videos/story"
    for name, content in {
        "renders/final.mp4": "mock verified media",
        "renders/final.report.json": "{}",
        "qa/audio/encoded-audio-verification.json": "{}",
        "qa/frames/frame-review.json": "{}",
        "UPLOAD_COPY.md": "Prepared fictional story copy.",
        "script.txt": "One thoughtful choice.",
        "assets/audio/narration.srt": "1\n00:00:00,000 --> 00:00:01,000\nOne thoughtful choice.\n",
    }.items():
        file = project / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)
    digest = hashlib.sha256((project / "renders/final.mp4").read_bytes()).hexdigest()
    (project / "DELIVERY_REVIEW.json").write_text(json.dumps({
        "video_sha256": digest, "sampled_visual_review_passed": True, "blocking_findings": [],
        "frame_review_sha256": hashlib.sha256((project / "qa/frames/frame-review.json").read_bytes()).hexdigest(),
    }))
    def verify(path):
        assert path == project
        return {"video": project / "renders/final.mp4", "video_sha256": digest,
                "snapshot": {"index.html": "verified-source-hash"},
                "plan": {"width": 1080, "height": 1920, "fps": 30, "duration_seconds": 25}}
    monkeypatch.setattr(story_publication, "verify_current_render", verify)
    monkeypatch.setattr(story_publication, "verify_story_qa", lambda *args: {})
    manager = social_campaign.SocialCampaignManager(settings, tmp_path)
    manager.meta.close()
    manager.meta, manager.youtube = FakeMeta(), FakeYouTube()
    yield manager, project, digest
    manager.close()


def enqueue_story(fixture, *, platform="instagram", transport="browser", campaign_id="story"):
    manager, project, digest = fixture
    post = {"id": "post", "episode_id": "story", "platform": platform,
            "account_id": CHANNEL if platform == "youtube" else "@biznex.stories",
            "publish_at": NOW.isoformat(), "caption": "A fictional story with synthetic narration.",
            "title": "One thoughtful choice", "privacy": "public", "transport": transport,
            "subtitles": "videos/story/assets/audio/narration.srt"}
    path = manager.root / (campaign_id + ".json")
    path.write_text(json.dumps({"campaign_id": campaign_id, "story_project": "videos/story", "posts": [post]}))
    return manager.enqueue(path)[0], path


def observation(fixture, **changes):
    manager, project, digest = fixture
    proof = manager.root / "proof.txt"
    proof.write_text("Observed exact profile, local upload and successful public post.")
    data = {"platform": "instagram", "account_id": "@biznex.stories", "video_sha256": digest,
            "title": "One thoughtful choice", "remote_id": "Abcd1234", "url": "https://www.instagram.com/p/Abcd1234/",
            "privacy": "public", "verified_at": NOW.isoformat(), "method": "browser_observation",
            "evidence_file": "proof.txt", "evidence_sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
            "confirmed_published": True}
    data.update(changes)
    path = manager.root / "observation.json"
    path.write_text(json.dumps(data))
    return path


def test_story_browser_worker_never_calls_api_and_claim_cannot_replay(story_queue):
    manager, _, _ = story_queue
    row, _ = enqueue_story(story_queue)
    assert manager.run_due(execute=True)[0]["readiness"] == "browser_action_required"
    assert manager.meta.calls == manager.youtube.uploads == 0
    assert manager.claim_browser(row["post_key"])["state"] == "browser_claimed"
    assert manager.run_due(execute=True) == []
    with pytest.raises(ConfigurationError, match="Only a due pending"):
        manager.claim_browser(row["post_key"])


def test_observed_success_is_idempotent_and_dedupes_new_campaign(story_queue):
    manager, _, _ = story_queue
    row, _ = enqueue_story(story_queue)
    evidence = observation(story_queue)
    result = manager.record_observed(row["post_key"], evidence)
    assert result["state"] == "published" and result["verification"] == "browser_observation"
    assert manager.record_observed(row["post_key"], evidence) == result
    duplicate, _ = enqueue_story(story_queue, campaign_id="again")
    assert duplicate["deduplicated"] is True and duplicate["post_key"] == row["post_key"]
    assert manager.run_due(execute=True) == []
    assert manager.meta.calls == manager.youtube.uploads == 0


def test_handle_case_cannot_bypass_dedupe_or_mismatch_an_observation(story_queue):
    manager, _, _ = story_queue
    first, campaign = enqueue_story(story_queue)
    changed = json.loads(campaign.read_text())
    changed["campaign_id"] = "mixed-case"
    changed["posts"][0]["account_id"] = "@BizNex.Stories"
    campaign.write_text(json.dumps(changed))
    repeated = manager.enqueue(campaign)[0]
    assert repeated["deduplicated"] is True
    assert repeated["post_key"] == first["post_key"]
    assert len(manager.list_posts()) == 1
    observed = manager.record_observed(first["post_key"], observation(story_queue, account_id="@BIZNEX.STORIES"))
    assert observed["state"] == "published"
    assert observed["account_id"] == "@biznex.stories"


@pytest.mark.parametrize("change", [
    {"account_id": "@someone.else"}, {"video_sha256": "f" * 64}, {"title": "Other title"},
    {"privacy": "private"}, {"url": "https://evil.example/p/Abcd1234/"},
    {"url": "https://www.instagram.com/p/Abcd1234/?token=secret"},
    {"url": "https://www.instagram.com/p/OtherID/"}, {"evidence_sha256": "0" * 64},
])
def test_observation_rejects_wrong_identity_content_url_or_evidence(story_queue, change):
    manager, _, _ = story_queue
    row, _ = enqueue_story(story_queue)
    with pytest.raises(ConfigurationError):
        manager.record_observed(row["post_key"], observation(story_queue, **change))
    assert manager.list_posts()[0]["state"] == "pending"


def test_held_story_cannot_be_claimed_or_adopted(story_queue):
    manager, _, _ = story_queue
    row, _ = enqueue_story(story_queue)
    manager.hold_posts([row["post_key"]])
    with pytest.raises(ConfigurationError):
        manager.claim_browser(row["post_key"])
    with pytest.raises(ConfigurationError, match="held jobs stay held"):
        manager.record_observed(row["post_key"], observation(story_queue))
    assert manager.list_posts()[0]["state"] == "held"


def test_changed_story_copy_blocks_worker_and_reconciliation(story_queue):
    manager, project, _ = story_queue
    row, _ = enqueue_story(story_queue)
    (project / "UPLOAD_COPY.md").write_text("Changed after approval")
    with pytest.raises(ConfigurationError, match="inputs changed"):
        manager.record_observed(row["post_key"], observation(story_queue))
    assert manager.run_due(execute=True)[0]["state"] == "blocked"


def test_missing_visual_review_blocks_atomic_enqueue(story_queue):
    manager, project, _ = story_queue
    (project / "DELIVERY_REVIEW.json").write_text("{}")
    with pytest.raises(ConfigurationError, match="sampled visual review"):
        enqueue_story(story_queue)
    assert manager.list_posts() == []


def test_story_api_reuses_existing_durable_youtube_upload(story_queue):
    manager, _, _ = story_queue
    enqueue_story(story_queue, platform="youtube", transport="api")
    assert manager.run_due(execute=True)[0]["state"] == "published"
    assert manager.youtube.uploads == 1
    assert manager.run_due(execute=True) == []


def test_legacy_post_payload_retains_old_fingerprint_shape():
    old = {"id": "one", "episode_id": "legacy", "platform": "youtube", "account_id": CHANNEL,
           "publish_at": NOW.isoformat().replace("+00:00", "Z"), "caption": "A useful question.",
           "video_url": None, "privacy": "private", "subtitles": None}
    post = CampaignPost.model_validate(deepcopy(old))
    assert _post_payload(post) == old
