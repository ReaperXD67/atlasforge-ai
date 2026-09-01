import json
from pathlib import Path

from PIL import Image

from daily_video_factory.media.render import music_video_filters, select_motion_window
from daily_video_factory.music_video import (
    BeatMap,
    EnergyPoint,
    MusicSection,
    MusicSpan,
    PerformanceStemReport,
    StemSceneActivity,
    VocalBrandCue,
    apply_malaysian_duet_plan,
    build_racing_storyboard,
    build_sync_report,
    match_vocal_brand_words,
    render_pragon_outro,
)


def test_pragon_outro_uses_the_approved_script_wordmark(tmp_path: Path) -> None:
    output = render_pragon_outro(
        "PRAGON",
        tmp_path / "outro.jpg",
        960,
        540,
        title="PRA-GON · SELAMANYA",
    )
    license_data = json.loads(output.with_suffix(".license.json").read_text(encoding="utf-8"))

    assert output.exists()
    assert license_data["wordmark"].endswith("pragon-script-logo-white.png")


def test_racing_storyboard_quantizes_cuts_and_uses_specific_shots() -> None:
    beat_map = BeatMap(
        duration_seconds=32,
        bpm=120,
        beats_seconds=[index * 0.5 for index in range(65)],
        downbeats_seconds=[index * 2 for index in range(17)],
        energy_curve=[
            EnergyPoint(time_seconds=index, energy=min(1, index / 20)) for index in range(33)
        ],
        sections=[
            MusicSection(start_seconds=0, end_seconds=8, label="intro", energy=0.2),
            MusicSection(start_seconds=8, end_seconds=16, label="build", energy=0.5),
            MusicSection(start_seconds=16, end_seconds=28, label="peak", energy=1),
            MusicSection(start_seconds=28, end_seconds=32, label="outro", energy=0.4),
        ],
    )
    storyboard = build_racing_storyboard(beat_map, title="Sepang Track Experience")
    assert storyboard.total_duration_seconds == 32
    assert storyboard.scenes[0].visual_mode == "documentary_broll"
    assert all(scene.duration_seconds >= 2 for scene in storyboard.scenes)
    assert any("friends" in scene.visual_search_query for scene in storyboard.scenes)
    assert any("sports car" in scene.visual_search_query for scene in storyboard.scenes)
    assert all("no logos" in scene.video_prompt for scene in storyboard.scenes)
    assert all("go kart" in scene.visual_exclusion_terms for scene in storyboard.scenes)
    assert all(not scene.ai_generation_required for scene in storyboard.scenes)
    assert storyboard.scenes[-1].selected_video_provider == "openai_imagegen_outro"
    assert storyboard.scenes[-1].music_treatment == "ember_resolve"


def test_custom_direction_drives_retrieval_generation_and_beat_typography() -> None:
    beat_map = BeatMap(
        duration_seconds=20,
        bpm=120,
        beats_seconds=[index * 0.5 for index in range(41)],
        downbeats_seconds=[index * 2 for index in range(11)],
        energy_curve=[],
        sections=[
            MusicSection(
                start_seconds=0,
                end_seconds=8,
                label="build",
                energy=0.58,
                pacing="beat_cut",
            ),
            MusicSection(
                start_seconds=8,
                end_seconds=20,
                label="peak",
                energy=0.96,
                pacing="beat_cut",
            ),
        ],
        rhythm_confidence=0.92,
        is_rhythmic=True,
    )
    direction = (
        "Clearly adult smokers in a neon pit garage, wet asphalt, cigarette embers, "
        "handheld flash photography"
    )

    storyboard = build_racing_storyboard(
        beat_map,
        title="After Dark",
        visual_direction=direction,
        hook_words="LIGHT IT UP, REDLINE",
        edit_style="neon_strobe",
    )

    assert any(
        "adult smoking cigarette" in scene.visual_search_query for scene in storyboard.scenes
    )
    assert all(direction in scene.video_prompt for scene in storyboard.scenes)
    assert all(scene.music_edit_style == "neon_strobe" for scene in storyboard.scenes)
    assert all("children" in scene.visual_exclusion_terms for scene in storyboard.scenes)
    cues = [cue for scene in storyboard.scenes for cue in scene.motion_text_cues]
    assert cues
    assert {cue.text for cue in cues} <= {"PRAGON", "LIGHT IT UP", "REDLINE"}
    assert all(cue.style in {"split", "brand_outro"} for cue in cues)
    assert all(
        cue.style == "brand_outro" or cue.time_seconds in scene.beat_accents_seconds
        for scene in storyboard.scenes
        for cue in scene.motion_text_cues
    )

    treated_scene = next(scene for scene in storyboard.scenes if scene.motion_text_cues)
    filters = music_video_filters(
        treated_scene,
        duration=treated_scene.duration_seconds,
        width=1920,
        height=1080,
        fps=60,
    )
    assert any(value.startswith("drawtext=") for value in filters)
    assert any(value.startswith("drawbox=") for value in filters)
    assert not any(value.startswith("drawbox=x=0:y=0:w=iw:h=ih:") for value in filters)
    assert not any("0.009*sin(PI*" in value for value in filters)
    assert not any("0.018*(1-" in value for value in filters)

    pulse_filters = music_video_filters(
        treated_scene.model_copy(update={"music_camera_motion": "pulse"}),
        duration=treated_scene.duration_seconds,
        width=1920,
        height=1080,
        fps=60,
    )
    assert any("0.009*sin(PI*" in value for value in pulse_filters)

    shutter_filters = music_video_filters(
        treated_scene.model_copy(update={"music_treatment": "shutter_trail"}),
        duration=treated_scene.duration_seconds,
        width=1920,
        height=1080,
        fps=60,
    )
    assert any(value.startswith("chromashift=") for value in shutter_filters)
    assert not any(value.startswith("tmix=") for value in shutter_filters)


def test_racing_storyboard_accelerates_on_peak_bars_and_emits_frame_locked_sync() -> None:
    beat_map = BeatMap(
        duration_seconds=24,
        bpm=120,
        beats_seconds=[index * 0.5 for index in range(49)],
        downbeats_seconds=[index * 2 for index in range(13)],
        energy_curve=[],
        sections=[
            MusicSection(
                start_seconds=0,
                end_seconds=8,
                label="intro",
                energy=0.3,
                onset_rate=1.2,
                pacing="beat_cut",
            ),
            MusicSection(
                start_seconds=8,
                end_seconds=16,
                label="peak",
                energy=1,
                onset_rate=2.4,
                pacing="beat_cut",
            ),
            MusicSection(
                start_seconds=16,
                end_seconds=24,
                label="outro",
                energy=0.45,
                onset_rate=1,
                pacing="beat_cut",
            ),
        ],
        rhythm_confidence=0.91,
        is_rhythmic=True,
    )

    storyboard = build_racing_storyboard(beat_map, title="Grid Test", fps=60)
    intro_lengths = [
        scene.duration_seconds for scene in storyboard.scenes if scene.music_section == "intro"
    ]
    peak_lengths = [
        scene.duration_seconds for scene in storyboard.scenes if scene.music_section == "peak"
    ]
    assert peak_lengths
    assert max(peak_lengths) < max(intro_lengths)
    assert all(
        round(scene.start_seconds * 60) == scene.start_seconds * 60 for scene in storyboard.scenes
    )
    report = build_sync_report(beat_map, storyboard, fps=60)
    assert report.within_frame_tolerance
    assert report.max_error_seconds == 0


def test_sparse_track_uses_phrase_boundaries_instead_of_fictional_beats() -> None:
    beat_map = BeatMap(
        duration_seconds=24,
        bpm=120,
        beats_seconds=[index * 0.5 for index in range(49)],
        downbeats_seconds=[index * 2 for index in range(13)],
        energy_curve=[],
        sections=[
            MusicSection(
                start_seconds=0,
                end_seconds=12,
                label="intro",
                energy=0.2,
                pacing="phrase_flow",
            ),
            MusicSection(
                start_seconds=12,
                end_seconds=24,
                label="outro",
                energy=0.15,
                pacing="phrase_flow",
            ),
        ],
        rhythm_confidence=0.2,
        is_rhythmic=False,
        phrases=[
            MusicSpan(start_seconds=0, end_seconds=8, kind="phrase"),
            MusicSpan(start_seconds=8, end_seconds=16, kind="phrase"),
            MusicSpan(start_seconds=16, end_seconds=24, kind="phrase"),
        ],
    )

    storyboard = build_racing_storyboard(beat_map, title="Phrase Test", fps=60)
    assert [scene.start_seconds for scene in storyboard.scenes] == [0, 8, 12, 16]
    assert all(scene.music_pacing == "phrase_flow" for scene in storyboard.scenes)
    assert build_sync_report(beat_map, storyboard, fps=60).within_frame_tolerance


def test_motion_window_matches_source_action_to_music_energy() -> None:
    profile = [0.2] * 24 + [0.85] * 24
    calm = select_motion_window(
        profile,
        sample_fps=4,
        target_duration=3,
        target_energy=0.1,
        source_duration=12,
    )
    peak = select_motion_window(
        profile,
        sample_fps=4,
        target_duration=3,
        target_energy=1,
        source_duration=12,
    )
    assert calm < 3
    assert peak >= 5


def test_motion_window_avoids_crossing_a_source_cut() -> None:
    profile = [0.15] * 8 + [0.9] * 12 + [0.55] * 20
    selected = select_motion_window(
        profile,
        sample_fps=4,
        target_duration=3,
        target_energy=1,
        source_duration=10,
        scene_boundaries=[3.25],
    )

    assert selected >= 3.5


def test_motion_window_rejects_a_cut_near_the_window_tail() -> None:
    selected = select_motion_window(
        [0.55] * 48,
        sample_fps=8,
        target_duration=3.0,
        target_energy=0.7,
        source_duration=6.0,
        scene_boundaries=[2.94],
    )

    assert selected >= 3.0


def test_motion_window_prefers_continuous_action_over_jitter() -> None:
    smooth_action = [0.50, 0.52, 0.48, 0.51] * 3
    jitter = [0.10, 0.90] * 6
    selected = select_motion_window(
        smooth_action + jitter,
        sample_fps=4,
        target_duration=3,
        target_energy=0.7,
        source_duration=6,
    )

    assert selected < 2.0


def test_unprompted_vocal_matching_accepts_pragon_misrecognition_but_rejects_noise() -> None:
    cues = match_vocal_brand_words(
        [
            ("Brango!", 0.0, 1.2, 0.378),
            ("PRAGON", 24.0, 24.7, 0.94),
            ("PRAGON", 25.0, 25.5, 0.07),
            ("dragonfly", 30.0, 31.0, 0.99),
        ],
        "PRAGON",
    )

    assert [cue.time_seconds for cue in cues] == [0.0, 24.0]
    assert cues[0].raw_word == "Brango!"


def test_brand_vocal_cue_and_owned_outro_are_injected_into_storyboard() -> None:
    beat_map = BeatMap(
        duration_seconds=12,
        bpm=120,
        beats_seconds=[index * 0.5 for index in range(25)],
        downbeats_seconds=[index * 2 for index in range(7)],
        energy_curve=[],
        sections=[
            MusicSection(start_seconds=0, end_seconds=8, label="drive", energy=0.8),
            MusicSection(start_seconds=8, end_seconds=12, label="outro", energy=0.3),
        ],
    )
    storyboard = build_racing_storyboard(
        beat_map,
        title="Sepang After Dark",
        brand="PRAGON",
        edit_style="pragon_neon",
        vocal_brand_cues=[
            VocalBrandCue(
                time_seconds=0,
                end_seconds=1.2,
                raw_word="Brango",
                confidence=0.378,
                match_score=0.667,
            )
        ],
    )

    assert all(
        cue.style != "brand_neon"
        for scene in storyboard.scenes[:-1]
        for cue in scene.motion_text_cues
    )
    assert storyboard.scenes[-1].visual_mode == "information_card"
    assert storyboard.scenes[-1].selected_video_provider == "openai_imagegen_outro"
    assert storyboard.scenes[-1].motion_text_cues[0].style == "brand_outro"


def test_malaysian_duet_plan_locks_two_recurring_identities_and_bans_stock_faces(
    tmp_path: Path,
) -> None:
    beat_map = BeatMap(
        duration_seconds=32,
        bpm=120,
        beats_seconds=[index * 0.5 for index in range(65)],
        downbeats_seconds=[index * 2 for index in range(17)],
        energy_curve=[],
        sections=[
            MusicSection(start_seconds=0, end_seconds=8, label="intro", energy=0.3),
            MusicSection(start_seconds=8, end_seconds=16, label="build", energy=0.6),
            MusicSection(start_seconds=16, end_seconds=28, label="peak", energy=0.95),
            MusicSection(start_seconds=28, end_seconds=32, label="outro", energy=0.3),
        ],
    )
    storyboard = build_racing_storyboard(
        beat_map,
        title="Sepang After Dark",
        visual_direction="adult Malaysian leads, neon pit garage, smoke and racing",
    )
    male = tmp_path / "male.png"
    female = tmp_path / "female.png"
    Image.new("RGB", (512, 768), "#183744").save(male)
    Image.new("RGB", (512, 768), "#4a1d28").save(female)
    report = PerformanceStemReport(
        analysis_backend="demucs_htdemucs_6s",
        scenes=[
            StemSceneActivity(
                scene_index=scene.index,
                start_seconds=scene.start_seconds,
                end_seconds=scene.start_seconds + scene.duration_seconds,
                vocal_energy=(scene.index % 5) / 4,
                guitar_energy=((scene.index + 2) % 5) / 4,
            )
            for scene in storyboard.scenes
        ],
    )

    plan = apply_malaysian_duet_plan(
        storyboard,
        beat_map,
        male,
        female,
        report,
        mix_ratio=0.3,
        max_scenes=8,
    )

    assert plan.cast_region == "Malaysia"
    assert plan.stock_people_allowed is False
    assert len(plan.entries) >= 6
    assert {entry.role for entry in plan.entries} >= {"male_lead", "female_lead", "duet"}
    assert {entry.action for entry in plan.entries} >= {
        "lip_sync",
        "guitar",
        "dance",
        "smoking_closeup",
        "duet_performance",
    }
    performer_scenes = [scene for scene in storyboard.scenes if scene.performer_generation_required]
    assert len(performer_scenes) == len(plan.entries)
    assert all(scene.visual_mode == "performer_ai" for scene in performer_scenes)
    assert all(
        "exact same" in scene.video_prompt and "adult Malaysian" in scene.video_prompt
        for scene in performer_scenes
    )
    support_scenes = [
        scene for scene in storyboard.scenes[1:-1] if not scene.performer_generation_required
    ]
    assert all(scene.performance_action == "car_action" for scene in support_scenes)
    assert all("recognizable face" in scene.visual_exclusion_terms for scene in support_scenes)
