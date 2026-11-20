"""Shared fail-closed parsing for optional gateway and management switches."""


def enabled(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() == "true")
