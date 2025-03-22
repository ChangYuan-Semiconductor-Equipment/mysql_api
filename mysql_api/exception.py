"""mysql_api exception module."""

class MySQLAPIError(Exception):
    """Base class for mysql_api exceptions."""


class MySQLAPIConnectionError(MySQLAPIError):
    """Exception raised when there is a connection error."""


class MySQLAPIQueryError(MySQLAPIError):
    """Exception raised when there is a query error."""


class MySQLAPIAddError(MySQLAPIError):
    """Exception raised when there is an add error."""


class MySQLAPIUpdateError(MySQLAPIError):
    """Exception raised when there is an upload error."""


class MySQLAPIDeleteError(MySQLAPIError):
    """Exception raised when there is a delete error."""
