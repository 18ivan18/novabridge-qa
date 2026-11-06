import pytest

from novabridge_qa.ingestion.jobs import JobRegistry


def test_new_job_is_queued() -> None:
    registry = JobRegistry()

    job = registry.create("doc")

    assert (job.doc_id, job.status, job.progress) == ("doc", "queued", 0)
    assert registry.get(job.job_id) == job


def test_update_replaces_the_stored_job() -> None:
    registry = JobRegistry()
    job = registry.create("doc")

    registry.update(job.job_id, "indexed", 100, chunks=3)

    stored = registry.get(job.job_id)
    assert stored is not None
    assert (stored.status, stored.progress, stored.chunks) == ("indexed", 100, 3)
    assert job.status == "queued"


def test_unknown_job_is_none() -> None:
    assert JobRegistry().get("nope") is None


def test_updating_an_unknown_job_fails() -> None:
    with pytest.raises(KeyError):
        JobRegistry().update("nope", "failed", 0)


def test_job_ids_are_unique() -> None:
    registry = JobRegistry()

    assert registry.create("doc").job_id != registry.create("doc").job_id
