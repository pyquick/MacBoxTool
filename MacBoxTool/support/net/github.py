"""
github.py: Shared GitHub REST API helpers.

Standard library only (no Qt, no requests) so it can be imported from network
code, workers and GUI pages alike.
"""

GITHUB_API_ACCEPT = "application/vnd.github+json"
GITHUB_API_VERSION = "2022-11-28"


def github_headers(token: str = "", extra: dict | None = None) -> dict:
    """
    Build request headers for the GitHub REST API.

    The version header is pinned because GitHub rejects requests without it, and
    an authenticated token is attached as a Bearer credential when supplied.
    """
    headers = {
        "Accept": GITHUB_API_ACCEPT,
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra:
        headers.update(extra)
    return headers
