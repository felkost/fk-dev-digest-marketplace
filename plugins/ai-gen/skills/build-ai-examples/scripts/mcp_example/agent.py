"""Serving: a LangGraph agent that reaches the scratchpad journal over MCP.

Spends the user's OpenRouter credit when run -- this is tier 3 of the
plugin's test ladder (see references/mcp-example.md). server.py and
test_live_stdio.py are free; this is not, and needs the user's explicit
say-so before you run it against a real key.

Run:  python agent.py "jot down that the meeting moved to 3pm"
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# Anchored to this file's directory, not CWD, so `python agent.py` works
# from anywhere. Must run before the os.environ reads below.
load_dotenv(pathlib.Path(__file__).parent / ".env")

SERVER = pathlib.Path(__file__).parent / "server.py"

SYSTEM_PROMPT = """You manage a scratchpad journal through MCP tools.

Rules:
- Use add_note to record anything the user asks you to remember.
- Read the journal://notes resource before answering what has already been
  recorded -- do not guess from earlier turns in the conversation.
"""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in; "
            "never commit the filled-in file."
        )
    return value


async def build_agent():
    # langchain_mcp_adapters launches the server as a subprocess over stdio,
    # the same transport test_live_stdio.py drives directly -- the agent
    # gets the same three tools/resources/prompts, just through LangGraph
    # instead of a raw ClientSession.
    client = MultiServerMCPClient(
        {
            "scratchpad": {
                "command": sys.executable,
                "args": [str(SERVER)],
                "transport": "stdio",
            }
        }
    )
    tools = await client.get_tools()

    # langgraph.prebuilt.create_react_agent is deprecated as of LangGraph
    # V1.0 in favor of langchain.agents.create_agent (rag-example.md found
    # and live-verified the same thing). Kept here for consistency with
    # that already-shipped example; if you hit a removal, verify the
    # replacement's signature before swapping it in -- don't assume it is a
    # drop-in.
    model = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=_require("OPENROUTER_API_KEY"),
        model=os.environ.get("CHAT_MODEL", "openai/gpt-4o-mini"),
        temperature=0,
        timeout=30,
    )
    return create_react_agent(model, tools, prompt=SYSTEM_PROMPT)


async def main(message: str) -> None:
    agent = await build_agent()
    result = await agent.ainvoke(
        {"messages": [("user", message)]},
        # Cap the loop -- an agent that can call a tool can loop forever
        # calling it.
        config={"recursion_limit": 8},
    )
    print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "What is in the journal?"))
