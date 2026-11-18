"""Display helpers for the learner notebook. Learners don't need to read this file."""

import json
import uuid
from html import escape
from inspect import getsource, getsourcefile
from pathlib import Path
from pprint import pprint

import pandas as pd
from IPython.display import Image, display
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer
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


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def show_source(obj):
    """Show a function's real source code in a boxed panel, labeled with its file."""
    func = getattr(obj, "func", obj)  # a @tool wraps the plain function in .func
    code = getsource(func)
    file = Path(getsourcefile(func)).resolve().relative_to(PROJECT_ROOT).as_posix()
    spans = highlight(code, PythonLexer(), HtmlFormatter(noclasses=True, nowrap=True, style="github-dark"))
    label = f"{escape(file)} &middot; {escape(func.__name__)}"
    html = (
        '<div style="border:1px solid #30363d; border-radius:10px; overflow:hidden; margin:6px 0;">'
        '<div style="background:#161b22; color:#8b949e; font-family:monospace; font-size:12px; '
        f'padding:7px 14px; border-bottom:1px solid #30363d;">{label}</div>'
        '<pre style="margin:0; padding:12px 14px; overflow-x:auto; border:none; border-radius:0; '
        "background:#0d1117; color:#e6edf3; font-family:Consolas, 'Cascadia Mono', monospace; "
        f'font-size:13px; line-height:1.45; white-space:pre;">{spans}</pre></div>'
    )
    display({"text/html": html, "text/plain": code}, raw=True)


def show_graph(agent):
    try:
        display(Image(agent.get_graph().draw_mermaid_png()))
    except Exception:  # the PNG renderer needs internet access
        print(agent.get_graph().draw_mermaid())
