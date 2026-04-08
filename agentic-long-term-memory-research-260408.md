# Agentic Long-Term Memory Systems: Cross-Platform Research

**Date:** 2026-04-08
**Goal:** Build a shared memory store that plugs into Claude Code, Claude.ai, Gemini, and Cursor.

---

## 1. The Key Insight: MCP is the Integration Layer

Model Context Protocol (MCP) is the de facto standard for cross-platform AI tool integration. Any memory server implementing MCP automatically works with all target clients.

**MCP-compatible clients (confirmed):**
- Claude Code (stdio)
- Claude.ai (via Connectors)
- Cursor (stdio + SSE)
- Gemini CLI (`engram setup gemini-cli`)
- VS Code / GitHub Copilot
- ChatGPT (OpenAI announced MCP support)
- Windsurf

**Transport protocols:** stdio (local process), SSE (Server-Sent Events over HTTP), Streamable HTTP

**Architecture pattern:**
```
[Claude Code] --stdio--> [MCP Memory Server] <--stdio-- [Cursor]
[Gemini CLI]  --stdio--> [MCP Memory Server]
[Claude.ai]   --SSE----> [MCP Memory Server] (if Connectors support it)
```

All four clients connect to the same MCP memory server. The server stores memories in a local database. Every tool sees the same memory.

**URL:** https://modelcontextprotocol.io

---

## 2. Major Open-Source Memory Projects

### Mem0 (52k stars) -- Most Mature
- **URL:** https://github.com/mem0ai/mem0
- **What:** "Universal memory layer for AI agents" (Y Combinator S24)
- **Architecture:** Dual-storage: vector store (24+ backends: Qdrant, Pinecone, ChromaDB, PGVector, FAISS, etc.) + optional graph store (Neo4j, Memgraph, Kuzu, Neptune). LLM extracts structured facts from conversations, classifies as ADD/UPDATE/DELETE/NOOP vs existing memories.
- **Memory types:** User, Session, Agent, App scopes. Semantic memory (facts/preferences). Graph variant (Mem0g) adds entity-relationship modeling.
- **MCP support:** Yes -- official integration + community wrapper (`coleam00/mcp-mem0`, 668 stars)
- **Cross-platform:** Python SDK, Node.js SDK, CLI, REST API, MCP server
- **Research:** Published paper showing +26% accuracy over OpenAI Memory on LOCOMO benchmark, 91% faster, 90% fewer tokens
- **Maturity:** Most mature and widely adopted. v1.0.0 released. SOC 2 Type II certified managed platform.
- **Tradeoffs:** Requires LLM for memory extraction (cost per operation). Self-hosted requires vector DB + LLM provider config.

### Graphiti / Zep (24.6k stars) -- Best for Evolving Knowledge
- **URL:** https://github.com/getzep/graphiti
- **What:** Temporal knowledge graph engine -- tracks facts with validity windows
- **Architecture:** Neo4j backend. Bi-temporal tracking (4 timestamps per fact). Entities + Relations + Episodes + Communities. Hybrid retrieval: semantic embeddings + BM25 + graph traversal + reranking.
- **Memory types:** Episodic (raw episodes), Semantic (deduplicated entities/relationships), Temporal (validity windows on all facts)
- **MCP support:** Yes -- ships MCP server for Claude/Cursor
- **Cross-platform:** Python library + REST API (FastAPI) + MCP server
- **Maturity:** Very active. Zep is the managed enterprise version with <200ms P95 latency.
- **Tradeoffs:** Requires Neo4j -- heavier infrastructure. Most powerful for evolving/contradicting facts. Overkill for simple preference storage.

### Letta (formerly MemGPT) (21.9k stars) -- Agent Framework with Memory
- **URL:** https://github.com/letta-ai/letta
- **What:** Platform for building stateful agents with advanced memory
- **Architecture:** Three-tier: Core Memory (in-context, editable blocks), Archival Memory (vector store for long-term), Recall Memory (conversation history with search). Agent self-manages memory via tool calls.
- **Memory types:** Core (working memory blocks), Archival (long-term semantic), Recall (episodic conversation history)
- **MCP support:** Can consume MCP servers as tools. Does not expose itself as MCP server natively.
- **Cross-platform:** REST API, Python/Node SDKs, web IDE
- **Tradeoffs:** More of a complete agent framework than a pluggable memory module. Harder to use as just a memory layer.

### Engram (2.3k stars) -- Simplest Cross-Platform Option
- **URL:** https://github.com/Gentleman-Programming/engram
- **What:** "Persistent memory system for AI coding agents" -- single Go binary
- **Architecture:** SQLite + FTS5 (full-text search). No vector DB, no external dependencies.
- **Memory types:** Session-based (summaries), semantic (observations), procedural (implicit via patterns)
- **MCP support:** Native MCP server via stdio. Also HTTP API and CLI.
- **Cross-platform:** Explicit setup for Claude Code, Gemini CLI, Cursor, VS Code/Copilot, Windsurf, OpenCode. **Most cross-platform-ready tool found.**
- **Tradeoffs:** No vector/semantic search -- FTS5 keyword only. Simple but may miss semantically similar memories.

---

## 3. MCP-Native Memory Servers (Purpose-Built)

### Official MCP Memory Server
- Ships in the official MCP servers repo
- JSON-file-backed knowledge graph (entities + relations + observations)
- 8 tools: `create_entities`, `create_relations`, `add_observations`, `delete_*`, `read_graph`, `search_nodes`, `open_nodes`
- No vector search, no semantic retrieval, no multi-user support
- Good starting point, limited capabilities

### Nocturne Memory (923 stars)
- **URL:** https://github.com/Dataojitori/nocturne_memory
- Graph-based with tree-style frontend. SQLite (local) or PostgreSQL (distributed).
- "One soul, any engine" -- agent identity persists across model switches
- Web dashboard with human review/audit workflow
- Native MCP server (stdio + SSE)

### ClawMem (86 stars)
- **URL:** https://github.com/yoloshii/ClawMem
- SQLite + FTS5 + sqlite-vec. Multi-signal retrieval (BM25 + vector + RRF + cross-encoder reranking)
- Local GGUF observer models for automatic memory extraction. Contradiction detection with auto-decay.
- 31 MCP tools + Claude Code hooks integration (90% automatic via hooks, 10% agent-initiated)

### LycheeMem (222 stars)
- **URL:** https://github.com/LycheeMem/LycheeMem
- SQLite FTS5 + LanceDB vector index. Three-tier: working memory (episodic), semantic memory (7 typed categories), procedural memory (skill store)
- Multi-dimensional scoring (relevance, utility, recency, evidence density)
- Most sophisticated memory taxonomy of the smaller projects

### Context Portal / ConPort (760 stars)
- **URL:** https://github.com/GreatScottyMac/context-portal
- SQLite per workspace with Alembic migrations. 25+ MCP tools.
- Full-text search + vector storage + semantic search + knowledge graph
- Tested with Roo Code, CLine, Windsurf, Cursor

### MARM Systems (257 stars)
- **URL:** https://github.com/Gentleman-Programming/MARM-Systems
- FastAPI + SQLite + vector embeddings. 18 MCP tools.
- Designed for multi-agent (Claude, Gemini, Qwen) sharing same memory

---

## 4. Specialized / Notable Projects

| Project | Stars | Key Innovation |
|---------|-------|---------------|
| Memvid | 14.7k | Single `.mv2` file with video-encoding-inspired structure, BM25 + HNSW vector |
| Wax | 695 | Apple Silicon optimized, Metal-accelerated HNSW + SQLite FTS5, 6.1ms recall on M-series |
| Vestige | 471 | FSRS-6 spaced repetition (Anki algorithm), 29 brain modules, single Rust binary |
| TeleMem | 454 | Drop-in Mem0 replacement with LLM-based semantic clustering dedup (86% vs Mem0's 70% on Chinese benchmarks) |
| Moltis | 2.5k | Full agent server in Rust, SQLite + FTS + vectors, MCP built-in, encryption-at-rest |
| MCP Knowledge Graph | 838 | Fork of official MCP memory with dual project-local + global storage |
| Memory Bank MCP | 892 | Inspired by Cursor's memory bank pattern |

---

## 5. Storage Architecture Comparison

| Approach | Pros | Cons | Examples |
|----------|------|------|----------|
| **Vector DB** | Semantic similarity search, scales well | Loses structural relationships, retrieval can be noisy | Mem0, Memvid |
| **Graph DB** | Rich relationships, temporal tracking, multi-hop reasoning | Heavier infrastructure (Neo4j), more complex | Graphiti/Zep, Nocturne |
| **Hybrid (Vector + Graph)** | Best of both worlds | Most complex to operate | Mem0g, Graphiti |
| **SQLite + FTS5** | Zero dependencies, fast, portable | No semantic search (keyword only) | Engram, ConPort |
| **SQLite + FTS5 + Vector** | Portable with semantic capabilities | Vector quality depends on embedding model | ClawMem, LycheeMem, Moltis |
| **JSON/JSONL files** | Simplest, human-readable | No search, doesn't scale | Official MCP Memory |

---

## 6. Memory Type Taxonomy

Research (2025-2026) converges on three core types from cognitive science:

1. **Episodic Memory** -- What happened (conversation history, session logs, event records). Temporal ordering matters.
2. **Semantic Memory** -- What is known (facts, preferences, entities, relationships). Structure and accuracy matter.
3. **Procedural Memory** -- How to do things (skills, workflows, tool usage patterns). Least implemented in current tools.

Most tools implement episodic + semantic. Only LangMem and LycheeMem explicitly address procedural memory.

---

## 7. Platform-Native Memory Features

### Claude Code
- **CLAUDE.md files:** Hierarchical markdown files persisting across sessions
- **Auto-memory:** `~/.claude/projects/{hash}/memory/MEMORY.md`
- **MCP support:** Full MCP client (stdio). Any MCP memory server plugs in directly.
- No memory API -- file-based only. MCP is the extension mechanism.

### Claude.ai
- Built-in memory feature (2025) -- proactively saves facts from conversations
- Users can view/edit/delete in settings
- **No API access** -- closed product feature, not available programmatically
- MCP via Connectors (limited compared to Claude Code)

### Gemini
- Saved Info / Gems for persistent preferences
- Context Caching API for cost optimization (not true memory)
- 1M+ token context window (large context approach vs external memory)
- **Gemini CLI:** Supports MCP, so any MCP memory server works
- **No memory API** for built-in memory

### Cursor
- `.cursorrules` / Rules for persistent project instructions
- Automatic codebase semantic indexing
- **Full MCP client** (stdio + SSE)
- No built-in memory persistence API beyond rules files

---

## 8. Key Research Papers (2025-2026)

- **"Memory in the Age of AI Agents"** (Dec 2025) -- Comprehensive taxonomy of forms, functions, and dynamics
- **"Beyond the Context Window: Cost-Performance Analysis"** (Mar 2026) -- Long-context models vs external memory
- **"Modular Memory is the Key to Continual Learning Agents"** (Mar 2026) -- Architecture integrating in-context and weight-based learning
- **"Poison Once, Exploit Forever"** (Apr 2026) -- Security vulnerabilities in agent memory systems
- **"LightThinker++: From Reasoning Compression to Memory Management"** (Apr 2026) -- Adaptive memory using behavioral primitives
- **Mem0 paper** -- +26% accuracy vs OpenAI Memory on LOCOMO benchmark

**Curated collections:**
- Awesome-AI-Memory: 300+ papers, 89+ projects
- Awesome-Agent-Memory: focused on agent-specific memory research

---

## 9. Recommendations

### Option A: Engram (Simplest, broadest platform support)
- Single Go binary, zero dependencies, SQLite
- Explicit setup for Claude Code, Gemini CLI, Cursor, VS Code
- No semantic search (FTS5 only)
- **Best for:** Getting something working in 5 minutes

### Option B: Mem0 + MCP (Most capable, most mature)
- Use `coleam00/mcp-mem0` or official MCP integration
- Vector + optional graph, LLM-powered extraction
- Requires PostgreSQL/Supabase + LLM API keys
- **Best for:** Production-grade semantic memory

### Option C: Graphiti MCP (Best for evolving knowledge)
- Temporal knowledge graph with fact invalidation
- Requires Neo4j
- **Best for:** Facts that change over time (trading signals, market regimes, system state)

### Option D: Custom MCP Server (Most control)
- Start from official MCP memory server
- Swap JSON for SQLite + vector embeddings
- 200-500 lines of code for a basic implementation
- **Best for:** Exact feature set needed, no bloat

### Limitation: Claude.ai
Claude.ai's memory is a closed product feature with no API. The only cross-platform path is an external MCP server. Claude.ai's MCP support (via Connectors) is more limited than Claude Code's stdio-based integration.

---

## 10. Recommended Architecture for Our Use Case

Given the Alpha Engine ecosystem (multiple repos, evolving system knowledge, cross-tool workflow):

```
Storage:  SQLite + FTS5 + vector embeddings (portable, zero-dep)
Protocol: MCP server (stdio for local, SSE for remote)
Clients:  Claude Code, Cursor, Gemini CLI (all via MCP)
Memory:   Episodic (session summaries) + Semantic (facts, preferences, decisions)
```

**Start with Engram** for immediate cross-platform coverage, then evaluate Mem0 if semantic search becomes important. A custom MCP server is viable if neither fits -- the protocol is simple and well-documented.
