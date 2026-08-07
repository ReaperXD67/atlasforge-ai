from typer.testing import CliRunner

from daily_video_factory.cli import app


def test_cli_help_loads() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AtlasForge AI" in result.output
    assert "doctor" in result.output
    assert "youtube-auth" in result.output


def test_run_rejects_bad_date_before_pipeline() -> None:
    result = CliRunner().invoke(app, ["run", "--date", "07/08/2026", "--no-upload"])
    assert result.exit_code != 0
    assert "YYYY-MM-DD" in result.output
