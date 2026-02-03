"""Shared constants for validation and configuration."""

# Field validation
MAX_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 2000
MAX_QUERY_TEXT_LENGTH = 10000
MIN_STRING_LENGTH = 1

# Pagination
DEFAULT_SKIP = 0
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

# HTTP error messages
ERROR_PROJECT_NOT_FOUND = "Project not found"
ERROR_BRAND_NOT_FOUND = "Brand not found"
ERROR_QUERY_NOT_FOUND = "Query not found"
ERROR_USER_NOT_FOUND = "User not found"
ERROR_UNAUTHORIZED = "Could not validate credentials"
ERROR_FORBIDDEN_INACTIVE = "Inactive user"
ERROR_FORBIDDEN_PRIVILEGES = "Not enough privileges"
