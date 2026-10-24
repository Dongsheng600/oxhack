from __future__ import annotations

from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .utf16 import has_surrogates, is_utf16_boundary, utf16_length

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OpaqueId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,128}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnhanceRequest(StrictModel):
    request_id: OpaqueId
    prompt: str = Field(min_length=1, max_length=20_000)
    prompt_revision: int = Field(ge=0, strict=True)
    cursor_position: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_cursor(self) -> EnhanceRequest:
        if not is_utf16_boundary(self.prompt, self.cursor_position):
            raise ValueError("cursor_position must be a UTF-16 boundary within prompt")
        return self


class Edit(StrictModel):
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=0, strict=True)
    text: str

    @model_validator(mode="after")
    def ordered(self) -> Edit:
        if self.start > self.end:
            raise ValueError("edit start must not exceed end")
        if has_surrogates(self.text):
            raise ValueError("edit text contains an unpaired surrogate")
        return self


class ChoiceOption(StrictModel):
    id: NonEmpty = Field(max_length=80)
    label: NonEmpty = Field(max_length=500)
    edits: list[Edit] = Field(min_length=1, max_length=20)


class EnhanceBase(StrictModel):
    schema_version: Literal[1]
    request_id: str
    prompt_revision: int


class AutocompleteResponse(EnhanceBase):
    type: Literal["autocomplete"]
    insert_at: int = Field(ge=0, strict=True)
    text: str = Field(min_length=1)


class MultipleChoiceResponse(EnhanceBase):
    type: Literal["multiple_choice"]
    question: NonEmpty = Field(max_length=1000)
    options: list[ChoiceOption] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def unique_options(self) -> MultipleChoiceResponse:
        ids = [option.id for option in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError("option ids must be unique")
        return self


class NoneResponse(EnhanceBase):
    type: Literal["none"]


EnhanceResponse = Annotated[
    AutocompleteResponse | MultipleChoiceResponse | NoneResponse,
    Field(discriminator="type"),
]


def validate_enhancement(response: EnhanceResponse, prompt: str) -> None:
    if isinstance(response, AutocompleteResponse):
        if has_surrogates(response.text):
            raise ValueError("autocomplete text contains an unpaired surrogate")
        if response.insert_at != utf16_length(prompt):
            raise ValueError("autocomplete must insert at the end of the prompt")
        if not is_utf16_boundary(prompt, response.insert_at):
            raise ValueError("invalid autocomplete offset")
        return
    if not isinstance(response, MultipleChoiceResponse):
        return
    for option in response.options:
        edits = sorted(option.edits, key=lambda edit: (edit.start, edit.end))
        for edit in edits:
            if not is_utf16_boundary(prompt, edit.start) or not is_utf16_boundary(prompt, edit.end):
                raise ValueError("edit offset is outside prompt or splits a surrogate pair")
        for previous, current in pairwise(edits):
            if previous.start == previous.end and current.start == current.end and previous.start == current.start:
                raise ValueError("duplicate insertions at one offset")
            if current.start < previous.end:
                raise ValueError("overlapping edits")
            if previous.start == previous.end and current.start == previous.start:
                raise ValueError("insertion at replacement boundary")
            if current.start == current.end and current.start == previous.end:
                raise ValueError("insertion at replacement boundary")


class OutcomeRequest(StrictModel):
    event_id: OpaqueId
    request_id: OpaqueId
    event_type: Literal["displayed", "accepted", "declined", "stale", "failed", "observed"]
    observed_result: Literal["helpful", "unhelpful", "unknown"] | None = None

    @model_validator(mode="after")
    def observed_only(self) -> OutcomeRequest:
        if self.event_type != "observed" and self.observed_result is not None:
            raise ValueError("observed_result is only valid for observed events")
        if self.event_type == "observed" and self.observed_result is None:
            raise ValueError("observed_result is required for observed events")
        return self


class PreviewRequest(StrictModel):
    title: NonEmpty = Field(max_length=300)
    kind: Literal["skill", "prompt", "graph"]
    content: str = Field(min_length=1, max_length=100_000)

    @model_validator(mode="after")
    def valid_unicode(self) -> PreviewRequest:
        if not self.content.strip():
            raise ValueError("source content must not be blank")
        if has_surrogates(self.title) or has_surrogates(self.content):
            raise ValueError("source contains an unpaired surrogate")
        return self


class SaveKnowledgeRequest(StrictModel):
    preview_id: OpaqueId
    idempotency_key: OpaqueId


class ModelPatch(StrictModel):
    extraction: str | None = None
    relevance: str | None = None
    generation: str | None = None
    summary: str | None = None


class SettingsPatch(StrictModel):
    models: ModelPatch | None = None
