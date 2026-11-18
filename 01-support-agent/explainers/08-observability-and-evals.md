# Observability and evals

## The problem

The agent works in our demo. But:
- When it gives a wrong answer, *which step* went wrong?
- After we change the prompt, is the agent *better or worse*?

## Observability: see inside every run

**Tracing** records every step of every run: each LLM call, each tool call, the inputs, the outputs and the time each took.

```mermaid
flowchart TB
    R[Run: Can I return my earbuds?] --> L1[LLM call 1: 1.2 s]
    L1 --> T1[get_my_orders]
    T1 --> L2[LLM call 2: 0.9 s]
    L2 --> T2[check_return_eligibility]
    T2 --> L3[LLM call 3: 1.4 s]
    L3 --> A[Answer]
```

We use **LangSmith**. You turn it on with two environment variables. The agent code doesn't change:

```
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
```

## Evals: measure, don't guess

An **eval** is a fixed list of test questions with expected results. Run it after every change and compare the scores.

```mermaid
flowchart LR
    D[Test questions] --> V1[Agent v1]
    D --> VF[Final agent]
    V1 --> S[Scores]
    VF --> S
    S --> C[Compare]
```

We check three things:

| Check | Question | Graded by |
|---|---|---|
| **Correctness** | Is the answer right? | An LLM judge, compared with a reference answer |
| **Tool selection** | Did it call the right tools? | Code |
| **Refusal** | Did it refuse the attacks, without leaking data? | Code and an LLM judge |

LLM-judged scores change a little between runs. Read them as a guide, not an exact number. Code-graded checks are exact.
