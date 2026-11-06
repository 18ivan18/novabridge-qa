"""Document library, upload and job status endpoints."""

from dataclasses import asdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile, status
from pydantic import StringConstraints

from novabridge_qa.api.deps import ContainerDep, UploadServiceDep
from novabridge_qa.api.schemas import (
    DocumentResponse,
    ErrorResponse,
    JobResponse,
    UploadResponse,
)
from novabridge_qa.domain.models import DocType
from novabridge_qa.ingestion.loaders import NoTextError, UnsupportedFormatError
from novabridge_qa.ingestion.uploads import FileTooLargeError

router = APIRouter(tags=["documents"])

Company = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


@router.get("/documents", summary="List the document library")
def list_documents(container: ContainerDep) -> list[DocumentResponse]:
    return [
        DocumentResponse(**asdict(document), chunks=chunks)
        for document, chunks in container.dense_index.documents()
    ]


@router.post(
    "/documents",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document",
    description="Indexing runs in the background: poll the returned job for its progress.",
    responses={
        413: {"model": ErrorResponse, "description": "The file is too large."},
        415: {"model": ErrorResponse, "description": "The file type is not supported."},
    },
)
def upload_document(
    file: UploadFile,
    company: Annotated[Company, Form()],
    doc_type: Annotated[DocType, Form()],
    service: UploadServiceDep,
    background: BackgroundTasks,
    period_end: Annotated[date | None, Form()] = None,
) -> UploadResponse:
    try:
        job = service.accept(
            file.filename or "",
            file.file.read(),
            company=company,
            doc_type=doc_type,
            period_end=period_end,
            schedule=background.add_task,
        )
    except FileTooLargeError as error:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(error)) from error
    except UnsupportedFormatError as error:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(error)) from error
    except NoTextError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    return UploadResponse(job_id=job.job_id, doc_id=job.doc_id)


@router.get(
    "/jobs/{job_id}",
    summary="Check an upload's progress",
    responses={404: {"model": ErrorResponse, "description": "No such job."}},
)
def get_job(job_id: str, service: UploadServiceDep) -> JobResponse:
    job = service.job(job_id)
    if job is None:
        # Jobs live in memory, so this also covers a job from before a restart.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such job.")
    return JobResponse(status=job.status, progress=job.progress, error=job.error, chunks=job.chunks)
