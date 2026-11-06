"""Wires settings to the application's long-lived objects."""

from dataclasses import dataclass

from novabridge_qa.config import Settings
from novabridge_qa.retrieval.dense import DenseIndex


@dataclass(frozen=True)
class Container:
    settings: Settings
    dense_index: DenseIndex


def build_dense_index(settings: Settings) -> DenseIndex:
    return DenseIndex(settings.data_dir / "index" / "chroma", settings.embedding_model)


def build_container(settings: Settings) -> Container:
    return Container(settings=settings, dense_index=build_dense_index(settings))
