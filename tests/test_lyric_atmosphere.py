import pytest
from pydantic import ValidationError

from daily_video_factory.lyric_atmosphere import Snowfall, camera_crop, snow_frame
from daily_video_factory.lyric_film import Shot

PANE = [[(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]]


def test_snowfall_stays_in_the_cropped_pane_and_uses_absolute_time() -> None:
    shot = Shot(
        at=0,
        image="window.jpg",
        enter={"zoom": 1.0, "x": 0.0, "y": 0.0},
        leave={"zoom": 1.25, "x": 1.0, "y": 1.0},
        snow_windows=PANE,
        snow_intensity=1.0,
    )
    layer = shot.snowfall()
    assert layer is not None
    assert camera_crop(layer.enter, layer.leave, 10, 21) == pytest.approx((1.125, 0.5, 0.5))
    alpha = snow_frame(Snowfall(), layer, None, 20, 21, 3.0, 0).getchannel("A")
    repeated = snow_frame(Snowfall(), layer, None, 20, 21, 3.0, 0).getchannel("A")
    later = snow_frame(Snowfall(), layer, None, 20, 21, 3.1, 0).getchannel("A")
    bounds = alpha.getbbox()

    assert alpha.tobytes() == repeated.tobytes()
    assert alpha.tobytes() != later.tobytes()
    assert bounds is not None
    # Final crop maps the pane into x=40..440, y=22.5..247.5 at overlay resolution.
    left, top, right, bottom = bounds
    assert 40 <= left < right <= 440
    assert 23 <= top < bottom <= 248


def test_snowfall_fades_with_an_outgoing_window() -> None:
    layer = Shot(at=0, image="window.jpg", snow_windows=PANE, snow_intensity=1).snowfall()
    assert layer is not None
    particles = Snowfall()
    first = snow_frame(particles, None, layer, 0, 21, 3.0, 8).getchannel("A")
    middle = snow_frame(particles, None, layer, 4, 21, 3.0, 8).getchannel("A")
    last = snow_frame(particles, None, layer, 8, 21, 3.0, 8).getchannel("A")

    assert 0 < middle.getextrema()[1] < first.getextrema()[1]
    assert last.getbbox() is None
    assert Shot(at=0, image="window.jpg").snowfall() is None


def test_snowfall_rejects_offscreen_polygon_points() -> None:
    with pytest.raises(ValidationError, match="snow_windows"):
        Shot(at=0, image="window.jpg", snow_windows=[[(1.1, 0), (0.3, 0), (0.3, 0.6)]])
