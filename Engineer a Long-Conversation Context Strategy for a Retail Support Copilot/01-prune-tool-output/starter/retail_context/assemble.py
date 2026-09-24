"""Position-aware context assembly.

Layout (top → bottom):
  # Case Facts                       — top boundary, structured (≤ 600 tokens)
  # Resolved: Refund inquiry         — middle, compressible zone (≤ 500 tokens)
  # Resolved: Subscription cancellation — middle, compressible zone (≤ 500 tokens)
  # Active issue: Payment-method update — bottom boundary, byte-exact verbatim

This places key findings at both context boundaries (Case Facts at top, the
active turn-by-turn at bottom against the new user turn) and lets the resolved
narrative occupy the lower-attention middle. Sections are exclusive — no
interleaving.
"""
from __future__ import annotations

from dataclasses import dataclass

from retail_context.case_facts import CaseFacts
from retail_context.compressor import Compressed
from retail_context.tokens import count

# TODO: Define the exact-text header contract.
# RESOLVED_TITLES maps `issue_id` ("refund", "subscription") to the literal
# Markdown header string that must appear above that section in the assembled
# context. ACTIVE_TITLES does the same for the active segment.
# The AST audit (test_antipatterns.py) regex-matches against these exact strings,
# so they are part of the contract — change them and the
# audit fails. Use level-1 headings (# ...), not ##.
RESOLVED_TITLES: dict[str, str] = {
    "refund": "# Resolved: Refund inquiry",
    "subscription": "# Resolved: Subscription cancellation",
}

ACTIVE_TITLES: dict[str, str] = {
    "payment_update": "# Active issue: Payment-method update",
}


@dataclass
class AssembledContext:
    markdown: str
    case_facts_block: str
    resolved_blocks: dict[str, str]
    active_block: str
    active_raw_text: str  # byte-exact verbatim source for the active segment

    def section_tokens(self) -> dict[str, int]:
        sections = {"case_facts": count(self.case_facts_block)}
        for issue_id, block in self.resolved_blocks.items():
            sections[f"resolved_{issue_id}"] = count(block)
        sections["active"] = count(self.active_block)
        return sections

    def total_tokens(self) -> int:
        return count(self.markdown)


def build(case_facts: CaseFacts, compressed: Compressed) -> AssembledContext:
    # 1. Top boundary — case facts.
    case_facts_block = case_facts.to_markdown().rstrip() + "\n"

    # 2. Middle — resolved issues in the required order.
    resolved_blocks: dict[str, str] = {}

    for issue_id in ("refund", "subscription"):
        if issue_id not in compressed.summaries:
            raise KeyError(f"missing resolved issue: {issue_id}")

        summary_text = compressed.summaries[issue_id].text.strip()

        resolved_blocks[issue_id] = (
            f"{RESOLVED_TITLES[issue_id]}\n\n"
            f"{summary_text}\n"
        )

    # 3. Bottom boundary — active issue.
    active_title = ACTIVE_TITLES.get(
        compressed.active_issue_id,
        f"# Active issue: {compressed.active_issue_id}",
    )

    # Keep active_text completely unchanged.
    active_block = f"{active_title}\n\n{compressed.active_text}"

    # 4. Exact section order.
    markdown = (
        case_facts_block
        + "\n"
        + resolved_blocks["refund"]
        + "\n"
        + resolved_blocks["subscription"]
        + "\n"
        + active_block
    )

    # 5. Return the assembled context.
    return AssembledContext(
        markdown=markdown,
        case_facts_block=case_facts_block,
        resolved_blocks=resolved_blocks,
        active_block=active_block,
        active_raw_text=compressed.active_text,
    )