"""Tiered compression: summarize resolved segments; preserve active verbatim.

Resolved segments are condensed by a single Claude call per segment using the
prompt template at `retail_context/prompts/compression_prompt.md`. The active
segment is **never** summarized — it is preserved byte-exact.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from retail_context.client import complete_with_system
from retail_context.transcript import Segment, Transcript


@dataclass
class Summary:
    issue_id: str
    text: str
    input_tokens: int
    output_tokens: int


@dataclass
class Compressed:
    summaries: dict[str, Summary]
    active_text: str
    active_issue_id: str


def _load_prompt() -> str:
    return resources.files("retail_context.prompts").joinpath(
        "compression_prompt.md"
    ).read_text()


def summarize_segment(segment: Segment, *, model: str | None = None) -> Summary:
    if segment.status != "resolved":
        raise ValueError(
            f"cannot summarize issue {segment.issue_id} with status "
            f"{segment.status!r}; only resolved segments are compressed — "
            "the active segment must be preserved byte-exact"
        )

    system = _load_prompt()

    user = (
        f"Source segment — issue_id `{segment.issue_id}`, turns "
        f"{segment.turn_range[0]}-{segment.turn_range[1]}:\n\n"
        f"{segment.text}"
    )

    text, input_tokens, output_tokens = complete_with_system(
        system,
        user,
        model=model,
        max_tokens=1024,
    )

    return Summary(
        issue_id=segment.issue_id,
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    #    It returns a (text, input_tokens, output_tokens) tuple.
    #
    # 5. Return a Summary carrying the issue_id, the response text (the
    #    structured summary), and the token counts.
    #raise NotImplementedError("Exercise 3: implement segment summarization")


def compress(transcript: Transcript, *, model: str | None = None) -> Compressed:
    summaries: dict[str, Summary] = {}
    active_text: str | None = None
    active_issue_id: str | None = None

    for segment in transcript.segments:
        if segment.status == "resolved":
            summary = summarize_segment(segment, model=model)
            summaries[segment.issue_id] = summary

        elif segment.status == "active":
            active_text = "\n\n".join(t.render() for t in segment.turns)
            active_issue_id = segment.issue_id

    if active_text is None or active_issue_id is None:
        raise RuntimeError(
            "no active segment present; assembled context requires exactly "
            "one active segment"
        )

    return Compressed(
        summaries=summaries,
        active_text=active_text,
        active_issue_id=active_issue_id,
    )
