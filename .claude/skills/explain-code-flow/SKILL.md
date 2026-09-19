---
name: explain-code-flow
description: Explain an existing function, method, or code block as an execution-ordered walkthrough with exact code snippets and concise line-level notes. Use when the user asks to trace code, explain important lines, or omit boilerplate; do not use for implementation, debugging, or review unless an explanation is also requested.
---

# Explain Code Flow

Explain the code in execution order while keeping the source visible beside the explanation.

## Inspect

- Read the exact source and enough callers or callees to resolve what each important operation does.
- Preserve source line numbers when available. Never invent them.
- Distinguish what the inspected code does now from what a helper or generated artifact does later.

## Select

Include lines that affect control flow or observable output:

- branches, loops, early returns, and error paths;
- state changes, constructed values, and returned values;
- calls that delegate meaningful work;
- data transformations, validation, and emitted output.

Skip blank lines, closing braces, repetitive formatting calls, and comments that merely restate the code. Include an otherwise simple line when omitting it would break the execution trace.

## Present

1. Link or name the source and summarize the function in one or two sentences.
2. Group important contiguous lines into small sections ordered exactly as they execute.
3. Give each section a short purpose-based heading followed by a fenced code snippet copied from the source.
4. Explain each important line or tight line range in one to three sentences. Start each note with its line number when known.
5. When a call crosses into a helper that needs explanation, insert the helper as a separate section immediately after that call site, then resume the caller. Do not collect helper explanations at the end.
6. End with a compact flow such as `validate → construct → delegate → return`.
7. State in one sentence what was deliberately omitted.

Use `// ...` only to mark an explicit omission; never make separated lines look contiguous. Keep helper explanations to the depth needed to understand the current function, linking to the helper rather than expanding into an unrelated walkthrough.

Write in the user's language. Prefer concrete effects over syntax paraphrases, and avoid architecture commentary unless the user asks for it.
