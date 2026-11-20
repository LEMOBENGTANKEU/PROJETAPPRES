class P2PError(Exception):
    """Base error for local peer-to-peer transfers."""


class ManifestError(P2PError):
    """The resource manifest is invalid."""


class ProtocolError(P2PError):
    """A peer sent an invalid or unsupported protocol message."""


class IntegrityError(P2PError):
    """A piece or completed resource failed its SHA-256 check."""


class StorageError(P2PError):
    """The local partial-transfer state could not be safely used."""
