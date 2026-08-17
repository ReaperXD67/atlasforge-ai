from daily_video_factory.music_video import (
    BeatMap,
    EnergyPoint,
    MusicSection,
    build_racing_storyboard,
)


def test_racing_storyboard_quantizes_cuts_and_uses_specific_shots() -> None:
    beat_map = BeatMap(
        duration_seconds=32,
        bpm=120,
        beats_seconds=[index * 0.5 for index in range(65)],
        downbeats_seconds=[index * 2 for index in range(17)],
        energy_curve=[EnergyPoint(time_seconds=index, energy=min(1, index / 20)) for index in range(33)],
        sections=[
            MusicSection(start_seconds=0, end_seconds=8, label="intro", energy=0.2),
            MusicSection(start_seconds=8, end_seconds=16, label="build", energy=0.5),
            MusicSection(start_seconds=16, end_seconds=28, label="peak", energy=1),
            MusicSection(start_seconds=28, end_seconds=32, label="outro", energy=0.4),
        ],
    )
    storyboard = build_racing_storyboard(beat_map, title="Sepang Track Experience")
    assert storyboard.total_duration_seconds == 32
    assert storyboard.scenes[0].visual_mode == "information_card"
    assert all(scene.duration_seconds >= 2 for scene in storyboard.scenes)
    assert any("race car" in scene.visual_search_query for scene in storyboard.scenes)
    assert all("no logos" in scene.video_prompt for scene in storyboard.scenes)
    assert all("go kart" in scene.visual_exclusion_terms for scene in storyboard.scenes)
