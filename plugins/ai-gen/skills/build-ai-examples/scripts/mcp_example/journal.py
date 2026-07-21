"""Pure logic for the scratchpad journal -- no `mcp`, no third-party imports.

Kept separate from server.py so tests/smoke_test.py can exercise the note
logic with a bare interpreter, the same split rag_example uses for
chunking.py/retrieval.py/settings.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Note:
    id: int
    text: str


class Journal:
    """In-memory, append-only note store. One instance backs one server."""

    def __init__(self) -> None:
        self._notes: list[Note] = []
        self._next_id = 1

    def add(self, text: str) -> Note:
        text = text.strip()
        if not text:
            raise ValueError("note text must not be empty")
        note = Note(id=self._next_id, text=text)
        self._notes.append(note)
        self._next_id += 1
        return note

    def get(self, note_id: int) -> Note | None:
        for note in self._notes:
            if note.id == note_id:
                return note
        return None

    def list_all(self) -> list[Note]:
        return list(self._notes)

    def format_all(self) -> str:
        if not self._notes:
            return "(journal is empty)"
        return "\n".join(f"[{n.id}] {n.text}" for n in self._notes)
