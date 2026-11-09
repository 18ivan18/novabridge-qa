"""Document library, upload and job status endpoints."""

from dataclasses import asdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from fastapi import Path as PathParam
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


@router.get(
    "/documents",
    summary="List the document library",
    description="Returns every indexed document, in title order.",
)
def list_documents(container: ContainerDep) -> list[DocumentResponse]:
    return [
        DocumentResponse(**asdict(document), chunks=chunks)
        for document, chunks in container.dense_index.documents()
    ]


@router.post(
    "/documents",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document",
    description=(
        "Accepts one file of a type that `GET /api/config` lists, up to its size limit. "
        "Indexing runs in the background: poll the returned job "
        "for its progress. A file already in the library gets a job that is already `indexed`, "
        "and its original tags are kept."
    ),
    responses={
        413: {"model": ErrorResponse, "description": "The file is too large."},
        415: {"model": ErrorResponse, "description": "The file type is not supported."},
        422: {"description": "A field is invalid, or the file has no text (`detail` is a string)."},
    },
)
def upload_document(
    file: Annotated[UploadFile, File(description="The document to index.")],
    company: Annotated[Company, Form(description="The company the document is about.")],
    doc_type: Annotated[DocType, Form(description="The kind of document.")],
    service: UploadServiceDep,
    background: BackgroundTasks,
    period_end: Annotated[
        date | None, Form(description="The last day of the period it covers.")
    ] = None,
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
    description="Jobs live in memory, so a job from before a server restart returns 404.",
    responses={404: {"model": ErrorResponse, "description": "No such job."}},
)
def get_job(
    job_id: Annotated[str, PathParam(description="The `job_id` from the upload.")],
    service: UploadServiceDep,
) -> JobResponse:
    job = service.job(job_id)
    if job is None:
        # Jobs live in memory, so this also covers a job from before a restart.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such job.")
    return JobResponse(status=job.status, progress=job.progress, error=job.error, chunks=job.chunks)
