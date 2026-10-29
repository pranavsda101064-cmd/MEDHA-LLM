"""Raised when retrieval or indexing cannot proceed."""


class RagError(RuntimeError):
    """User-facing retrieval or indexing failure."""


def is_memory_error(exc: BaseException) -> bool:
    """Return True when a failure looks like memory/commit exhaustion."""
    if isinstance(exc, MemoryError):
        return True
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 1455:
        return True
    text = str(exc).lower()
    markers = (
        "paging file",
        "out of memory",
        "memory allocation",
        "defaultcpuallocator",
        "bad_alloc",
        "bad allocation",
        "failed to allocate",
    )
    return any(marker in text for marker in markers)
