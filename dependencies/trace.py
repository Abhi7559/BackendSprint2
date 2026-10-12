import uuid

from core.logger import get_request_id, set_request_id


def get_trace_id() -> str:
    """
    Dependency returning an auto-generated unique trace ID (UUID4) for each request.
    Synchronizes with the logger request_id context.
    """
    existing_ctx_id = get_request_id()
    if existing_ctx_id:
        return existing_ctx_id

    req_id = str(uuid.uuid4())
    set_request_id(req_id)
    return req_id
