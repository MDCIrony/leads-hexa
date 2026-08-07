"""Root conftest: makes the `tests` package importable without relying on the
editable install's .pth file, which encodes an absolute path of the machine
that ran `uv sync`."""
