import uuid
from typing import Annotated
from fastapi import Header

from core.logger import get_request_id, set_request_id


def get_trace_id(
    x_trace_id: Annotated[str | None, Header(description="Optional request trace identifier")] = None,
) -> str:
    """
    Dependency extracting or generating a unique trace ID (UUID4) for each request.
    Synchronizes with the logger request_id context.
    """
    existing_ctx_id = get_request_id()
    if existing_ctx_id:
        return existing_ctx_id

    req_id = x_trace_id.strip() if x_trace_id and x_trace_id.strip() else str(uuid.uuid4())
    set_request_id(req_id)
    return req_id
