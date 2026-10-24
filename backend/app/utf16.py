from __future__ import annotations


def utf16_length(text: str) -> int:
    if has_surrogates(text):
        raise ValueError("text contains an unpaired surrogate")
    return len(text.encode("utf-16-le")) // 2


def has_surrogates(text: str) -> bool:
    return any(0xD800 <= ord(char) <= 0xDFFF for char in text)


def is_utf16_boundary(text: str, offset: int) -> bool:
    if offset < 0 or has_surrogates(text):
        return False
    position = 0
    for char in text:
        if position == offset:
            return True
        position += 2 if ord(char) > 0xFFFF else 1
    return position == offset


def utf16_to_python_index(text: str, offset: int) -> int:
    if offset < 0:
        raise ValueError("negative UTF-16 offset")
    position = 0
    for index, char in enumerate(text):
        if position == offset:
            return index
        position += 2 if ord(char) > 0xFFFF else 1
        if position > offset:
            raise ValueError("UTF-16 offset splits a surrogate pair")
    if position == offset:
        return len(text)
    raise ValueError("UTF-16 offset is outside the text")
