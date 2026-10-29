from .exceptions import Conflict


def check_and_bump_version(locked, client_version):
    """Optimistic locking. `locked` must be re-read with select_for_update().

    Raises 409 stale_version if the client edited an out-of-date copy, otherwise
    adds 1 to `locked.version` (the caller saves). The client's number is only
    compared, never stored.
    """
    if client_version != locked.version:
        raise Conflict(
            "This record was changed by someone else. Reload it.",
            code="stale_version",
        )
    locked.version += 1
