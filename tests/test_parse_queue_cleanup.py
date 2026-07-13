from pathlib import Path

import pytest

import backend.app.knowledge as knowledge


def install_task(monkeypatch, queue_file: Path, visual_status: str = "completed") -> dict[str, object]:
    state: dict[str, object] = {"id": "task", "queuedFile": str(queue_file), "fileName": "manual.pdf"}

    def update(_task_id: str, **updates):
        state.update(updates)
        return dict(state)

    monkeypatch.setattr(knowledge, "update_parse_task", update)
    monkeypatch.setattr(
        knowledge,
        "ingest_knowledge_document_bytes",
        lambda **_kwargs: {"id": "doc", "visualAnalysisStatus": visual_status},
    )
    return state


@pytest.mark.parametrize("visual_status", ["completed", "completed_with_warnings"])
def test_queue_file_is_removed_after_success(tmp_path: Path, monkeypatch, visual_status: str) -> None:
    root = tmp_path / "knowledge"
    queue_file = root / "parse-queue" / "task.pdf"
    queue_file.parent.mkdir(parents=True)
    queue_file.write_bytes(b"pdf")
    monkeypatch.setattr(knowledge, "knowledge_dir", lambda: root)
    state = install_task(monkeypatch, queue_file, visual_status)
    knowledge.process_knowledge_parse_task("task")
    assert not queue_file.exists()
    assert state["status"] == visual_status


def test_queue_file_is_removed_after_failure_or_when_missing(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "knowledge"
    queue_file = root / "parse-queue" / "task.pdf"
    queue_file.parent.mkdir(parents=True)
    queue_file.write_bytes(b"pdf")
    monkeypatch.setattr(knowledge, "knowledge_dir", lambda: root)
    state = install_task(monkeypatch, queue_file)
    monkeypatch.setattr(
        knowledge,
        "ingest_knowledge_document_bytes",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("parse failed")),
    )
    knowledge.process_knowledge_parse_task("task")
    assert not queue_file.exists()
    assert state["status"] == "failed"
    knowledge.process_knowledge_parse_task("task")
    assert state["status"] == "failed"


def test_external_queue_path_is_never_deleted(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "knowledge"
    external = tmp_path / "outside.pdf"
    external.write_bytes(b"pdf")
    monkeypatch.setattr(knowledge, "knowledge_dir", lambda: root)
    install_task(monkeypatch, external)
    knowledge.process_knowledge_parse_task("task")
    assert external.exists()
