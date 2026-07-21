"""MCP server: a scratchpad journal exposed via all three MCP primitives.

Corrects two things found in the book's companion repo (see
references/mcp-example.md for the sourcing and the primary-source checks):

- `chapter_03/01_complete_mcp_server.py`'s `welcome()` prompt calls the
  resource function directly (`get_greeting(name)`), bypassing the resource
  protocol entirely -- it works in-process but conflates a resource with a
  plain function. `summarize_notes()` below does not: it returns an
  instruction, and the caller fetches `journal://notes` itself, through the
  protocol.
- `chapter_03/06_mcp_time_travel_tracker.py` ends in
  `mcp.run(transport="sse")`, the transport the current spec deprecates.
  This server defaults to stdio and accepts `streamable-http`, the two
  transports the spec (revision 2025-11-25) currently defines.

Run:
  python server.py                              # stdio -- what the agent and
                                                  # the live test use
  python server.py --transport streamable-http   # http://127.0.0.1:8000/mcp
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from journal import Journal

mcp = FastMCP("Scratchpad")

# Module-level state -- private to this one process today. The moment this
# server is reached by more than one client (or one client's concurrent
# sessions), `_journal` stops meaning "this agent's notes" and starts
# meaning "everyone's notes" -- nothing in the code below changes when that
# happens, which is exactly why the shift is easy to miss. See
# references/mcp-example.md and mcp-tools.md's "state-semantics shift".
_journal = Journal()


@mcp.tool()
def add_note(text: str) -> dict:
    """Append a note to the scratchpad journal. Returns its id and text."""
    note = _journal.add(text)
    return {"id": note.id, "text": note.text}


@mcp.resource("journal://notes")
def all_notes() -> str:
    """Every note in the journal, oldest first."""
    return _journal.format_all()


@mcp.resource("journal://notes/{note_id}")
def one_note(note_id: str) -> str:
    """A single note by id."""
    note = _journal.get(int(note_id))
    return note.text if note is not None else f"(no note with id {note_id})"


@mcp.prompt()
def summarize_notes() -> str:
    """A prompt template that asks for a summary of the journal.

    Deliberately does NOT call all_notes() as a plain function the way the
    companion repo's welcome() calls get_greeting() -- that shortcut works
    only because everything happens to share one process. This prompt just
    names the resource; whoever renders the prompt fetches it separately,
    through the resource protocol, the same as a remote client would have
    to.
    """
    return (
        "Read the journal://notes resource, then summarize its contents in "
        "three bullet points or fewer."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="spec revision 2025-11-25 defines exactly these two; 'sse' alone "
        "is the deprecated HTTP+SSE transport this example does not offer",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
