from ast import main
import asyncio
import os


from typing import Annotated, Dict, Any
from typing_extensions import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage

from agent import graph, State


async def main():
    print("LG-Agent running. Type 'quit' to exit.")
    config = {"configurable": {"thread_id": "1"}}

    state = {
        "messages": [
            SystemMessage(content=(
                "You are an assistant that can use tools. "
                "Only call tools when the user explicitly asks for file or OS actions "
                "(list/read/create/delete/get os info). "
                "If the user says hello or small talk, respond normally and do NOT call tools."
            ))
        ],
        "pending_action": []
    }

    while True:
        user_text = input("User: ").strip()
        if user_text.lower() in {"quit", "exit"}:
            print("Bye")
            break

        # Add the new human message to the running conversation
        state["messages"].append(HumanMessage(content=user_text))

        # send full state (system + history), not just the latest message
        result = await graph.ainvoke(
            {"messages": state["messages"], "pending_action": state["pending_action"]},
            config=config,
        )

        last = result["messages"][-1]
        print("Assistant:", getattr(last, "content", last))
        print()

        # Update the state with the new messages and pending actions for the next iteration
        state["messages"] = result["messages"]
        state["pending_action"] = result.get("pending_action", [])


if __name__ == "__main__":
    asyncio.run(main())