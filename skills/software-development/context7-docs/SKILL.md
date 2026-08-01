---
name: context7-docs
description: "Pull up-to-date, version-specific library documentation and code examples from Context7 — either via the built-in MCP server, the ctx7 CLI, or the REST API. Use this whenever you're unsure about a library's API, need version-specific docs, or want to avoid hallucinated APIs."
version: 1.0.0
author: Hermes Agent
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [context7, documentation, mcp, api-reference, libraries, code-examples]
    related_toolsets: [terminal, skills]
---

# Context7 Documentation Skill

Pull up-to-date, version-specific documentation and code examples for any library straight into Hermes's context using Context7 (by Upstash).

**Why Context7?** LLMs hallucinate APIs when trained on stale data. Context7 fetches **live, version-specific** docs from the source so you get real API signatures, real parameters, and real code examples — not something the model guessed.

## Setup

Choose **one** of the three integration methods below.

### Option 1: MCP Server (Recommended)

Context7 provides an MCP server that exposes `resolve-library-id` and `query-docs` tools directly to Hermes. This is the cleanest integration — no shell tricks.

**Step 1 — Get an API key:**
Go to https://context7.com/dashboard and create a free API key.

**Step 2 — Add the MCP server to Hermes:**
```bash
hermes mcp add context7 \
  --url https://mcp.context7.com/mcp \
  --header "CONTEXT7_API_KEY: your-api-key-here"
```

**Step 3 — Verify it works:**
```
hermes mcp list          # should show context7
hermes mcp test context7 # should return OK
```

After this, the `resolve-library-id` and `query-docs` MCP tools become available in any new Hermes session. Load them with the `mcp` toolset.

> **Note:** MCP tools appear after `/reset` (new session). If you add the server mid-session, run `/reset` or start a new session.

---

### Option 2: CLI (ctx7)

The CLI works without any MCP setup. Requires Node.js 18+.

```bash
# Setup (OAuth + generates API key automatically)
npx ctx7 setup

# Or install globally for repeated use
npm install -g ctx7
ctx7 setup
```

Then use from terminal:
```bash
# Search for a library
ctx7 library "next.js" "middleware authentication"

# Get docs for a specific library
ctx7 docs /vercel/next.js "how to create API routes"
```

---

### Option 3: REST API (Direct HTTP)

For environments where neither MCP nor the CLI is available, use the Context7 REST API directly:

```bash
# Search for a library
curl -s "https://api.context7.com/v1/search?q=next.js" \
  -H "Authorization: Bearer $CONTEXT7_API_KEY"

# Get documentation context
curl -s -X POST "https://api.context7.com/v1/context" \
  -H "Authorization: Bearer $CONTEXT7_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"libraryId": "/vercel/next.js", "query": "how to create API routes"}'
```

## When to Use Context7 (for the Agent)

Trigger Context7 when any of these conditions are true:

| Condition | Example |
|-----------|---------|
| You need to use a library but aren't sure of its exact API | "Create a Supabase auth signup form" |
| You need **version-specific** documentation | "Next.js 14 app directory routing" |
| The user mentions a library name + a framework | "Prisma with PostgreSQL connection pooling" |
| You'd normally guess at API parameters or method names | "How do I use the Stripe checkout session API?" |
| The library has changed significantly since your training cutoff | Any of the hundreds of fast-moving npm/pip packages |
| The user explicitly asks for current/real docs | "Show me the actual API docs for X" |

**Good indicators in the user's request:**
- They name a specific library + version (e.g. "Next.js 15", "React 19", "Tailwind v4")
- They ask for "actual" or "real" or "current" documentation
- They say "use context7" (Context7's own convention)
- The task involves a library you don't have installed / can't import / can't inspect

## Workflow (for the Agent)

### With MCP (primary path)

```python
# Step 1: Resolve the library to a Context7 ID
library_result = (call MCP tool: resolve-library-id)
# Input: libraryName="next.js", query="how to create API routes with app router"
# Returns: libraryId="/vercel/next.js", displayName="Next.js", confidence=0.95

# Step 2: Fetch docs for the resolved library
docs_result = (call MCP tool: query-docs)
# Input: libraryId="/vercel/next.js", query="how to create API routes with app router"
# Returns: markdown documentation with code examples
```

### With CLI (fallback)

```python
# Step 1: Search for library
result = terminal(command="ctx7 library "next.js" "app router API routes"", timeout=30)

# Step 2: Get documentation
result = terminal(command="ctx7 docs /vercel/next.js "app router API routes"", timeout=30)
```

### With REST API (last resort)

```python
# Step 1: Search
result = terminal(command='curl -s "https://api.context7.com/v1/search?q=next.js" -H "Authorization: Bearer $CONTEXT7_API_KEY"', timeout=15)

# Step 2: Get context
result = terminal(command='curl -s -X POST "https://api.context7.com/v1/context" -H "Authorization: Bearer $CONTEXT7_API_KEY" -H "Content-Type: application/json" -d '\''{"libraryId": "/vercel/next.js", "query": "app router API routes"}'\'', timeout=15)
```

## Context7 MCP Tool Reference

When MCP is configured, two tools become available:

### `resolve-library-id`
Resolves a general library name into a Context7-compatible library ID used by `query-docs`.
- **libraryName** (required): The name of the library (e.g., "next.js", "supabase", "prisma")
- **query** (required): What the user is trying to do — used for relevance ranking

### `query-docs`
Retrieves up-to-date documentation snippets for a library.
- **libraryId** (required): The exact Context7-compatible ID (e.g., `/vercel/next.js`, `/supabase/supabase`)
- **query** (required): What you need documentation for — Context7 returns the most relevant snippets

## Common Library IDs

| Library | Context7 ID |
|---------|-------------|
| Next.js | `/vercel/next.js` |
| React | `/facebook/react` |
| Vue | `/vuejs/core` |
| Svelte | `/sveltejs/svelte` |
| Tailwind CSS | `/tailwind/tailwindcss` |
| Prisma | `/prisma/prisma` |
| Supabase | `/supabase/supabase` |
| Clerk | `/clerk/javascript` |
| shadcn/ui | `/shadcn/ui` |
| LangChain | `/langchain/langchainjs` |

For the full list, use `resolve-library-id` with an empty query.

## Do NOT

- ❌ Make up API signatures, parameters, or return types for any library — use Context7 instead
- ❌ Assume a library works the same way across major versions — use version-specific queries
- ❌ Recommend deprecated APIs when a newer API exists — Context7 returns current docs
- ❌ Confuse similarly named libraries (e.g., `mongoose` vs `mongodb`) — use `resolve-library-id` first
- ❌ Skip Context7 when the user explicitly asks for real/current/actual docs — that's exactly when to use it
