"""Display helpers for the learner notebook. Learners don't need to read this file."""

import json
import uuid
from inspect import getsource
from pprint import pprint

import pandas as pd
from IPython.display import Image, Markdown, display
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from . import db
from .tools import SessionContext

RECURSION_LIMIT = 25  # max graph steps per turn


def print_message(m):
    if isinstance(m, HumanMessage):
        print(f"CUSTOMER: {m.content}")
    elif isinstance(m, ToolMessage):
        print(f"TOOL RESULT ({m.name}):\n  " + m.text.replace("\n", "\n  "))
    elif isinstance(m, AIMessage):
        for call in m.tool_calls:
            print(f"TOOL CALL: {call['name']}({json.dumps(call['args'], ensure_ascii=False)})")
        if m.text:
            print(f"{'GUARDRAIL' if m.name == 'input_guardrail' else 'AGENT'}: {m.text}")
    print()


def chat(agent, message=None, thread_id=None, customer_id="CUST-001", resume=None, show=True):
    """Send one message to the agent as customer_id and print what happens.

    resume: a manager's decision, to continue a paused agent.
    Returns the new messages of this turn.
    """
    thread_id = thread_id or f"chat-{uuid.uuid4().hex[:8]}"
    run_config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    has_memory = agent.checkpointer is not None
    seen = len(agent.get_state(run_config).values.get("messages", [])) if has_memory else 0

    if resume is not None:
        graph_input = Command(resume=resume)
        if show:
            print(f"MANAGER DECISION: {resume}\n")
    else:
        graph_input = {"messages": [HumanMessage(message)]}
    result = agent.invoke(graph_input, run_config, context=SessionContext(customer_id))

    new_messages = result["messages"][seen:]
    if show:
        for m in new_messages:
            print_message(m)
        if result.get("__interrupt__"):
            print("PAUSED: waiting for a manager. The agent sent this for approval:")
            pprint(result["__interrupt__"][0].value)
    return new_messages


def tool_calls(messages):
    """Names of the tools called in these messages, in order."""
    return [c["name"] for m in messages if isinstance(m, AIMessage) for c in m.tool_calls]


def is_paused(agent, thread_id):
    state = agent.get_state({"configurable": {"thread_id": thread_id}})
    return bool(state.interrupts)


def show_refunds(order_id=None):
    rows = db.get_refunds(order_id)
    if rows:
        display(pd.DataFrame(rows)[["order_id", "amount_usd", "refund_type", "status", "approval"]])
    else:
        print(f"No refunds for {order_id or 'any order'}.")


def show_source(obj):
    display(Markdown(f"```python\n{getsource(getattr(obj, 'func', obj))}\n```"))


def show_graph(agent):
    try:
        display(Image(agent.get_graph().draw_mermaid_png()))
    except Exception:  # the PNG renderer needs internet access
        print(agent.get_graph().draw_mermaid())
