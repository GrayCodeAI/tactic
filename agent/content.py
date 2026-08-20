from __future__ import annotations


def messages_have_images(messages: list) -> bool:
    return False


def text_and_images(content) -> tuple[str, list]:
    if isinstance(content, str):
        return content, []
    return str(content), []
