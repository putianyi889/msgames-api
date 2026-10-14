"""Explicit failures instead of silently interpreting error pages as empty data."""


class MsgamesError(Exception):
    """Base package error."""


class ParseError(MsgamesError):
    """The public HTML no longer matches the supported structure."""


class RequestError(MsgamesError):
    """An HTTP transport failed; the original HTTPX exception is chained."""


class HTTPError(MsgamesError):
    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code}: {url}")


class NotFoundError(HTTPError):
    """The requested public resource was not found."""


class AccessDeniedError(MsgamesError):
    """The resource requires login or access was denied."""


class RateLimitError(HTTPError):
    def __init__(self, url: str, retry_after: str | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(429, url)


class ResponseTooLargeError(MsgamesError):
    """The decoded response exceeds the configured size limit."""


class DownloadError(MsgamesError):
    """A replay link returned a page or an empty file instead of binary data."""
