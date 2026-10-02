from chassis.web import request_id_var


def current_correlation_id() -> str | None:
    """The id of the request in flight, or None outside one.

    "-" is the ContextVar's default, not an id: storing it would make every
    background write look like it belonged to the same request."""
    request_id = request_id_var.get()
    return None if request_id == "-" else request_id
