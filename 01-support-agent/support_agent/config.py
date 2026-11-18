"""Load .env and build the chat model and the embeddings."""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# Providers whose bind_tools() accepts parallel_tool_calls=False.
PARALLEL_FLAG_PROVIDERS = {"anthropic", "openai"}


def load_env():
    load_dotenv(PROJECT_ROOT / ".env")


def model_name():
    """The MODEL env var, as a 'provider:model' string."""
    load_env()
    name = os.getenv("MODEL")
    if not name:
        raise RuntimeError("Set MODEL in .env, for example MODEL=ollama:qwen3:8b")
    return name


def provider():
    return model_name().split(":", 1)[0]


def build_chat_model():
    """Chat model from MODEL, always at temperature 0."""
    kwargs = {"temperature": 0}
    if provider() == "ollama":
        kwargs["reasoning"] = False  # no hidden "thinking" text in answers
        kwargs["num_ctx"] = 8192  # room for the system prompt, tools and policy chunks
    return init_chat_model(model_name(), **kwargs)


def bind_tools(model, tools):
    """Bind tools. Disable parallel tool calls where the provider supports it."""
    if provider() in PARALLEL_FLAG_PROVIDERS:
        return model.bind_tools(tools, parallel_tool_calls=False)
    return model.bind_tools(tools)


def build_embeddings():
    """Small local embedding model. Free, no API key."""
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL, encode_kwargs={"normalize_embeddings": True}
    )
