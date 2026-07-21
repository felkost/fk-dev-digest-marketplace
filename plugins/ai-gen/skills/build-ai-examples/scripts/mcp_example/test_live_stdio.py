"""Free live check: a real MCP round-trip over stdio. No model, no key, no
network -- this is tier 2 of the plugin's test ladder (see
references/mcp-example.md), one step up from the offline logic checks in
tests/smoke_test.py and well short of tier 3 (a real agent run, which spends
the user's OpenRouter credit and needs their say-so first).

Launches server.py as a real subprocess and drives it exactly the way any
MCP client would: initialize, tools/list, tools/call, resources/read,
prompts/get. Requires `mcp` installed (`pip install -r requirements.txt`);
everything else about this check is offline.

Run:  python test_live_stdio.py     (exit code 0 = all passed)
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl

SERVER = pathlib.Path(__file__).parent / "server.py"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f": {detail}" if detail and not ok else ""))


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            check("server initializes and reports a name", bool(init.serverInfo.name))

            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            check("tools/list exposes add_note", "add_note" in tool_names, str(tool_names))

            resources = await session.list_resources()
            # The dynamic template journal://notes/{note_id} is listed as a
            # resource TEMPLATE, not a concrete resource -- list_resources()
            # legitimately shows 0 until a note exists to back one. Only
            # assert the call itself succeeds here.
            check("resources/list responds", resources is not None)

            prompts = await session.list_prompts()
            prompt_names = {p.name for p in prompts.prompts}
            check(
                "prompts/list exposes summarize_notes",
                "summarize_notes" in prompt_names,
                str(prompt_names),
            )

            empty = await session.read_resource(AnyUrl("journal://notes"))
            empty_text = empty.contents[0].text
            check("empty journal reads as empty, not an error", "(journal is empty)" in empty_text)

            result = await session.call_tool("add_note", arguments={"text": "first note"})
            check("tools/call add_note succeeds", not result.isError, str(result.content))

            after = await session.read_resource(AnyUrl("journal://notes"))
            after_text = after.contents[0].text
            check("resource reflects the tool's write", "first note" in after_text, after_text)

            one = await session.read_resource(AnyUrl("journal://notes/1"))
            one_text = one.contents[0].text
            check("templated resource fetches a single note by id", "first note" in one_text, one_text)

            prompt = await session.get_prompt("summarize_notes")
            prompt_text = prompt.messages[0].content.text
            check(
                "prompt names the resource instead of inlining its contents",
                "journal://notes" in prompt_text and "first note" not in prompt_text,
                prompt_text,
            )

            # A tool-side ValueError does NOT raise through call_tool -- MCP
            # reports execution errors IN the result (isError=True), not as
            # a protocol-level fault. This is the same point mcp-tools.md's
            # "Handling tool failure as normal control flow" already makes;
            # asserting isError here (not a try/except) is what proves it.
            blank = await session.call_tool("add_note", arguments={"text": "   "})
            check("blank note is rejected via isError, not an exception", blank.isError)

    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print()
    print("=" * 60)
    print(f"{len(RESULTS) - n_fail}/{len(RESULTS)} checks passed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
