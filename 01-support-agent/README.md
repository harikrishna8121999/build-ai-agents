# Project 1: Customer Support Agent (Jupyter Notebook)

Build one AI agent, layer by layer, that uses every core agent concept: tools, the agent loop, RAG, memory, human-in-the-loop, guardrails, observability and evals.

The agent supports customers of **Pixel & Plug**, a fictional online electronics store that ships worldwide. Prices are in US dollars. New to agents? Start with `learn_support_agent.ipynb`, the step-by-step version from the video. `support_agent.ipynb` is the full reference notebook.

Video: [YouTube link coming soon](https://youtube.com/)

| Version | Adds |
|---|---|
| v0 | A bare LLM |
| v1 | Tools and the agent loop |
| v2 | Agentic RAG over the store's policy documents |
| v3 | Short-term memory (checkpointer) and long-term memory (store) |
| v4 | Refunds with human-in-the-loop approval above \$100 |
| v5 | Guardrails: input, tool scoping, indirect injection, output masking, loop limit |
| v6 | Tracing with LangSmith, and evals comparing v1 with the final agent |

## Setup

You need Python 3.11 or later.

**With uv:**

```bash
uv venv
uv pip install -r requirements.txt
```

**With pip:**

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

The first run downloads a small embedding model (`BAAI/bge-small-en-v1.5`, about 130 MB). `sentence-transformers` also installs PyTorch, which is a large download.

Then copy `.env.example` to `.env` and set your model:

| Key | Required | Example |
|---|---|---|
| `MODEL` | yes | `ollama:qwen3:8b` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | for hosted models | |
| `LANGSMITH_API_KEY` | optional | turns on tracing and LangSmith evals |
| `LANGSMITH_TRACING` | optional | `true` |
| `LANGSMITH_PROJECT` | optional | `pixel-and-plug-support-agent` |

## Models

Any model with native tool calling works. `MODEL` is a `provider:model` string for LangChain's `init_chat_model`.

| MODEL | Cost | Notes |
|---|---|---|
| `ollama:qwen3:8b` | free, local | Tested. Install [Ollama](https://ollama.com), then `ollama pull qwen3:8b`. Needs about 6 GB of GPU memory or 16 GB of RAM. Slower, and some behavior checks score below 3/3. |
| `anthropic:claude-haiku-5-5` | paid | Fast and reliable tool calling. |
| `openai:gpt-5.4-mini` | paid | Fast and reliable tool calling. |

Only the local option was tested during the build.

## Run

**The notebook:**

```bash
jupyter notebook support_agent.ipynb
```

Run the Setup section first, then the sections in order. Each section starts with a reset cell, so you can re-run any section from there.

To run it end to end without the UI:

```bash
jupyter nbconvert --to notebook --execute support_agent.ipynb --output executed.ipynb --ExecutePreprocessor.timeout=-1
```

**The deterministic tests** (no LLM, a few seconds):

```bash
pytest tests/
```

**The smoke test** (uses the LLM, several minutes on a local model):

```bash
python scripts/smoke_test.py
```

It checks two things:
- **Safety invariants**, which must always hold. The script fails if one breaks.
- **Behavior checks**, which run 3 times each and report a pass rate.

## Project layout

```
learn_support_agent.ipynb  step-by-step learner version (start here if you are new)
explainers/              short concept docs with diagrams, one per idea
support_agent.ipynb      the full reference notebook
support_agent/           helpers: config, database, business rules, tools, RAG
data/seed_db.py          creates data/store.db (dates relative to today)
data/policies/           the store's policy documents (RAG corpus)
evals/dataset.json       18 eval cases
tests/test_tools.py      deterministic tests for rules and tools
scripts/smoke_test.py    LLM-driven checks on the final agent
```

The design rule for the whole project: **business rules live in Python, never in the prompt.** Return eligibility, refund limits, approvals, duplicate prevention and customer ownership are all enforced in code and tested in `tests/`.

## Credits

- [LangChain Academy](https://academy.langchain.com)
