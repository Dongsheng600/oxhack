from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    AutocompleteResponse,
    EnhanceRequest,
    EnhanceResponse,
    MultipleChoiceResponse,
    validate_enhancement,
)
from app.utf16 import utf16_length, utf16_to_python_index

ADAPTER = TypeAdapter(EnhanceResponse)


def response(edits: list[dict[str, object]]) -> MultipleChoiceResponse:
    return ADAPTER.validate_python({
        "schema_version": 1, "request_id": "req_1", "prompt_revision": 2,
        "type": "multiple_choice", "question": "Which format?",
        "options": [
            {"id": "a", "label": "A", "edits": edits},
            {"id": "b", "label": "B", "edits": [{"start": 0, "end": 0, "text": "B"}]},
        ],
    })


def test_utf16_boundaries_and_astral_characters() -> None:
    prompt = "A😀e\u0301中"
    assert utf16_length(prompt) == 6
    assert utf16_to_python_index(prompt, 3) == 2
    with pytest.raises(ValueError, match="surrogate"):
        utf16_to_python_index(prompt, 2)
    valid = response([{"start": 3, "end": 5, "text": "é"}])
    validate_enhancement(valid, prompt)
    with pytest.raises(ValueError, match="surrogate"):
        validate_enhancement(response([{"start": 2, "end": 3, "text": "x"}]), prompt)
    with pytest.raises(ValidationError):
        EnhanceRequest(request_id="r", prompt=prompt, prompt_revision=0, cursor_position=2)


@pytest.mark.parametrize("edits", [
    [{"start": 0, "end": 1, "text": "x"}, {"start": 0, "end": 0, "text": "y"}],
    [{"start": 1, "end": 1, "text": "x"}, {"start": 1, "end": 1, "text": "y"}],
    [{"start": 0, "end": 2, "text": "x"}, {"start": 1, "end": 3, "text": "y"}],
    [{"start": 0, "end": 2, "text": "x"}, {"start": 2, "end": 2, "text": "y"}],
    [{"start": 4, "end": 4, "text": "x"}],
])
def test_ambiguous_or_invalid_edits_rejected(edits: list[dict[str, object]]) -> None:
    with pytest.raises(ValueError):
        validate_enhancement(response(edits), "abc")


def test_adjacent_replacements_allowed() -> None:
    validate_enhancement(response([
        {"start": 0, "end": 1, "text": "x"},
        {"start": 1, "end": 2, "text": "y"},
    ]), "abc")


def test_exact_union_rejects_extra_fields_and_versions() -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"schema_version": 2, "request_id": "r", "prompt_revision": 0, "type": "none"})
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({"schema_version": 1, "request_id": "r", "prompt_revision": 0, "type": "none", "text": "leak"})
    with pytest.raises(ValidationError):
        ADAPTER.validate_python({
            "schema_version": 1, "request_id": "r", "prompt_revision": 0,
            "type": "multiple_choice", "question": "Q", "options": [
                {"id": "a", "label": "A", "edits": [{"start": 0, "end": 0, "text": "x"}]},
                {"id": "a", "label": "B", "edits": [{"start": 0, "end": 0, "text": "y"}]},
            ],
        })


def test_autocomplete_only_at_end() -> None:
    result = AutocompleteResponse(schema_version=1, request_id="r", prompt_revision=0,
                                  type="autocomplete", insert_at=2, text=" more")
    with pytest.raises(ValueError, match="end"):
        validate_enhancement(result, "A😀")
    validate_enhancement(result.model_copy(update={"insert_at": 3}), "A😀")
    assert result.text == " more"
