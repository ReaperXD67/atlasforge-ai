from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from daily_video_factory.story_pipeline import PipelineError, StoryPipeline, read, run_pipeline


@pytest.fixture(autouse=True)
def stable_test_toolchain(monkeypatch):
    monkeypatch.setattr("daily_video_factory.story_pipeline.toolchain_fingerprint", lambda: {"fixture": "v1"})


def project_fixture(root: Path) -> Path:
    project = root / "videos/test-story"
    project.mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "scripts/prepare.py").write_text(
        "from pathlib import Path\nimport sys\np=Path(sys.argv[1])\n"
        "(p/'result.txt').write_text((p/'input.txt').read_text().upper())\n"
        "c=p/'count.txt'\nc.write_text(str(int(c.read_text())+1) if c.exists() else '1')\n",
        encoding="utf-8",
    )
    (project / "BRIEF.md").write_text("An explicitly authored story.")
    (project / "input.txt").write_text("first")
    recipe = {"schema_version": 1, "project_id": "test-story", "stages": [
        {"id": "prepare", "executor": "python", "entrypoint": "scripts/prepare.py",
         "args": ["{project}"], "inputs": ["input.txt"], "outputs": ["result.txt"]},
    ]}
    (project / "PIPELINE.json").write_text(json.dumps(recipe))
    return project


def test_plan_does_not_execute_and_matching_resume_reuses_real_output(tmp_path: Path) -> None:
    project = project_fixture(tmp_path)
    assert run_pipeline(project, root=tmp_path)["status"] == "plan_only"
    assert not (project / "result.txt").exists()
    first = run_pipeline(project, root=tmp_path, execute=True)
    assert first["status"] == "stages_verified"
    assert first["stages"][0]["status"] == "passed"
    assert first["stages"][0]["elapsed_seconds"] >= 0
    second = run_pipeline(project, root=tmp_path, execute=True, resume=True)
    assert second["stages"][0]["status"] == "reused"
    assert (project / "count.txt").read_text() == "1"
    assert not second["creative_quality_verified"] and not second["published"]


@pytest.mark.parametrize("mutation", ["input", "output", "missing", "code", "brief"])
def test_stale_inputs_outputs_or_transitive_code_never_reuse(tmp_path: Path, mutation: str) -> None:
    project = project_fixture(tmp_path)
    run_pipeline(project, root=tmp_path, execute=True)
    if mutation == "input":
        (project / "input.txt").write_text("second")
    elif mutation == "output":
        (project / "result.txt").write_text("tampered")
    elif mutation == "missing":
        (project / "result.txt").unlink()
    elif mutation == "code":
        (tmp_path / "scripts/imported_helper.py").write_text("# A changed transitive dependency\n")
    else:
        (project / "BRIEF.md").write_text("Revised selected story")
    result = run_pipeline(project, root=tmp_path, execute=True, resume=True)
    assert result["stages"][0]["status"] == "passed"
    assert (project / "count.txt").read_text() == "2"
    assert (project / "result.txt").read_text() == (project / "input.txt").read_text().upper()


def test_nonzero_stage_keeps_failure_receipt_even_if_old_output_exists(tmp_path: Path) -> None:
    project = project_fixture(tmp_path)
    run_pipeline(project, root=tmp_path, execute=True)
    (tmp_path / "scripts/prepare.py").write_text("raise RuntimeError('do-not-leak-private-value')")
    with pytest.raises(PipelineError, match="Stage command failed"):
        run_pipeline(project, root=tmp_path, execute=True, resume=True)
    report = read(tmp_path / "output/story-pipeline/test-story/latest.json")
    assert report["status"] == "failed"
    assert report["stages"][0]["status"] == "failed"
    assert "do-not-leak-private-value" not in json.dumps(report)
    assert (project / "result.txt").read_text() == "FIRST"


def test_later_stage_cannot_silently_change_earlier_output(tmp_path: Path) -> None:
    project = project_fixture(tmp_path)
    (tmp_path / "scripts/mutate.py").write_text(
        "from pathlib import Path\nimport sys\np=Path(sys.argv[1])\n"
        "(p/'result.txt').write_text('changed')\n(p/'receipt.txt').write_text('ok')\n"
    )
    recipe = read(project / "PIPELINE.json")
    recipe["stages"].append({"id": "mutate", "executor": "python", "entrypoint": "scripts/mutate.py",
                             "args": ["{project}"], "outputs": ["receipt.txt"]})
    (project / "PIPELINE.json").write_text(json.dumps(recipe))
    with pytest.raises(PipelineError, match="later stage changed"):
        run_pipeline(project, root=tmp_path, execute=True)
    assert read(tmp_path / "output/story-pipeline/test-story/latest.json")["status"] == "failed"


@pytest.mark.parametrize("mutation", ["traversal", "private_arg", "duplicate_output", "self_overwrite", "future_input"])
def test_schema_rejects_unsafe_or_ambiguous_stage_contracts(tmp_path: Path, mutation: str) -> None:
    project = project_fixture(tmp_path)
    recipe = read(project / "PIPELINE.json")
    stage = recipe["stages"][0]
    if mutation == "traversal":
        stage["inputs"] = ["../other-project/secret"]
    elif mutation == "private_arg":
        stage["args"] = ["--password=do-not-leak"]
    elif mutation == "self_overwrite":
        stage["outputs"] = ["input.txt"]
    else:
        recipe["stages"].append({**stage, "id": "second", "outputs": ["next.txt"]})
        if mutation == "duplicate_output":
            recipe["stages"][1]["outputs"] = stage["outputs"]
        else:
            stage["inputs"] = ["next.txt"]
    with pytest.raises(ValidationError):
        StoryPipeline.model_validate(recipe)


def test_changed_input_during_execution_cannot_receive_a_cache_receipt(tmp_path: Path) -> None:
    project = project_fixture(tmp_path)
    (tmp_path / "scripts/prepare.py").write_text(
        "from pathlib import Path\nimport sys\np=Path(sys.argv[1])\n"
        "(p/'input.txt').write_text('new')\n(p/'result.txt').write_text('old')\n"
    )
    with pytest.raises(PipelineError, match="inputs changed"):
        run_pipeline(project, root=tmp_path, execute=True)
    assert not (tmp_path / "output/story-pipeline/test-story/state.json").exists()


def test_changed_runtime_version_invalidates_successful_cache(tmp_path: Path, monkeypatch) -> None:
    project = project_fixture(tmp_path)
    run_pipeline(project, root=tmp_path, execute=True)
    monkeypatch.setattr("daily_video_factory.story_pipeline.toolchain_fingerprint", lambda: {"fixture": "v2"})
    result = run_pipeline(project, root=tmp_path, execute=True, resume=True)
    assert result["stages"][0]["status"] == "passed"
    assert (project / "count.txt").read_text() == "2"


@pytest.mark.parametrize("mutation", ["delete", "modify", "add"])
def test_output_tree_change_reruns_the_stage(tmp_path: Path, mutation: str) -> None:
    project = project_fixture(tmp_path)
    script = tmp_path / "scripts/prepare.py"
    script.write_text(script.read_text() + "\n(p/'qa').mkdir(exist_ok=True)\n(p/'qa/frame.png').write_bytes(b'pixels')\n")
    recipe = read(project / "PIPELINE.json")
    recipe["stages"][0]["output_trees"] = ["qa"]
    (project / "PIPELINE.json").write_text(json.dumps(recipe))
    run_pipeline(project, root=tmp_path, execute=True)
    target = project / "qa/frame.png"
    if mutation == "delete":
        target.unlink()
    elif mutation == "modify":
        target.write_bytes(b"different pixels")
    else:
        (project / "qa/another.png").write_bytes(b"extra pixels")
    result = run_pipeline(project, root=tmp_path, execute=True, resume=True)
    assert result["stages"][0]["status"] == "passed"
    assert target.read_bytes() == b"pixels"


def test_two_stages_cannot_claim_the_same_output_tree(tmp_path: Path) -> None:
    project = project_fixture(tmp_path)
    recipe = read(project / "PIPELINE.json")
    recipe["stages"][0]["output_trees"] = ["qa"]
    recipe["stages"].append({"id": "next", "executor": "python", "entrypoint": "scripts/prepare.py",
                             "outputs": ["qa/nested/report.json"]})
    with pytest.raises(ValidationError, match="distinct ownership"):
        StoryPipeline.model_validate(recipe)


def test_toolchain_setup_failure_replaces_old_success_status(tmp_path: Path, monkeypatch) -> None:
    project = project_fixture(tmp_path)
    run_pipeline(project, root=tmp_path, execute=True)
    def unavailable():
        raise OSError("private tool path must not enter public receipt")
    monkeypatch.setattr("daily_video_factory.story_pipeline.toolchain_fingerprint", unavailable)
    with pytest.raises(OSError):
        run_pipeline(project, root=tmp_path, execute=True, resume=True)
    report = read(tmp_path / "output/story-pipeline/test-story/latest.json")
    assert report["status"] == "failed" and report["stages"] == []
    assert "private tool path" not in json.dumps(report)
