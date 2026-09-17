from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class VectorStore(Protocol):
    """Protocol isolating vector storage and similarity search from the engine."""
    def upsert(self, file_id: int, embedding: list[float], metadata: dict[str, Any] | None = None) -> None:
        """Inserts or updates vector representation for a file."""
        ...

    def delete(self, file_id: int) -> None:
        """Removes vectors for a given file_id."""
        ...

    def search(self, query_vector: list[float], limit: int = 10) -> list[tuple[int, float]]:
        """Returns list of (file_id, similarity_score) sorted descending."""
        ...

    def health(self) -> dict[str, Any]:
        """Returns health state: {'status': 'READY'|'UNAVAILABLE', 'count': int, 'backend': str}."""
        ...

    def version(self) -> str:
        """Returns version string for the vector store implementation."""
        ...
