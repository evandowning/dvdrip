"""Error types for dvdrip."""


class UserError(Exception):
    """An error caused by invalid user input or configuration."""

    def __init__(self, message: str) -> None:
        """Initialize with an error message.

        Args:
            message: Human-readable error description.
        """
        super().__init__(message)
        self.message = message
