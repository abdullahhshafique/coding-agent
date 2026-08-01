# Coding Agent

An autonomous CLI agent that takes a **natural-language bug report + a GitHub
repo** and produces a **reviewable unified diff** — without you pointing it at
the right file.

It runs the loop every engineer runs by hand: read the report → find the
relevant files → read them → write a patch that applies. Unlike a naive
"paste-one-file" LLM demo, it locates the relevant code structurally (AST),
respects a hard tool-call budget, and explicitly tells you when it *can't*
patch confidently instead of guessing.

---

## Why

The slow part of fixing a bug in an unfamiliar codebase isn't writing the fix —
it's **finding where to look**. This agent automates the search → read →
generate loop with real tool use (GitHub API + AST parsing), honest failure
handling, and a full trace of every decision so the loop itself can be debugged.

Phase 3 measured it against **16 real closed GitHub issues** (see
*Reproducibility*). It is a portfolio/learning artifact: current task-completion
is low and reported honestly, because the point was to *find* where the loop
breaks, not to claim it works.

---

## Agent Flow

&lt;p align="center"&gt;
&lt;svg viewBox="0 0 900 520" xmlns="http://www.w3.org/2000/svg"&gt;
  &lt;defs&gt;
    &lt;linearGradient id="grad-cli" x1="0" y1="0" x2="1" y2="1"&gt;
      &lt;stop offset="0%" stop-color="#6366f1" /&gt;
      &lt;stop offset="100%" stop-color="#8b5cf6" /&gt;
    &lt;/linearGradient&gt;
    &lt;linearGradient id="grad-orch" x1="0" y1="0" x2="1" y2="1"&gt;
      &lt;stop offset="0%" stop-color="#0ea5e9" /&gt;
      &lt;stop offset="100%" stop-color="#06b6d4" /&gt;
    &lt;/linearGradient&gt;
    &lt;linearGradient id="grad-gh" x1="0" y1="0" x2="1" y2="1"&gt;
      &lt;stop offset="0%" stop-color="#f59e0b" /&gt;
      &lt;stop offset="100%" stop-color="#ef4444" /&gt;
    &lt;/linearGradient&gt;
    &lt;linearGradient id="grad-ast" x1="0" y1="0" x2="1" y2="1"&gt;
      &lt;stop offset="0%" stop-color="#10b981" /&gt;
      &lt;stop offset="100%" stop-color="#34d399" /&gt;
    &lt;/linearGradient&gt;
    &lt;linearGradient id="grad-llm" x1="0" y1="0" x2="1" y2="1"&gt;
      &lt;stop offset="0%" stop-color="#ec4899" /&gt;
      &lt;stop offset="100%" stop-color="#f43f5e" /&gt;
    &lt;/linearGradient&gt;
    &lt;linearGradient id="grad-val" x1="0" y1="0" x2="1" y2="1"&gt;
      &lt;stop offset="0%" stop-color="#8b5cf6" /&gt;
      &lt;stop offset="100%" stop-color="#a78bfa" /&gt;
    &lt;/linearGradient&gt;
    &lt;linearGradient id="grad-out" x1="0" y1="0" x2="1" y2="1"&gt;
      &lt;stop offset="0%" stop-color="#14b8a6" /&gt;
      &lt;stop offset="100%" stop-color="#2dd4bf" /&gt;
    &lt;/linearGradient&gt;
    &lt;linearGradient id="grad-fail" x1="0" y1="0" x2="1" y2="1"&gt;
      &lt;stop offset="0%" stop-color="#64748b" /&gt;
      &lt;stop offset="100%" stop-color="#94a3b8" /&gt;
    &lt;/linearGradient&gt;
    &lt;filter id="glow" x="-20%" y="-20%" width="140%" height="140%"&gt;
      &lt;feGaussianBlur stdDeviation="3" result="blur" /&gt;
      &lt;feComposite in="SourceGraphic" in2="blur" operator="over" /&gt;
    &lt;/filter&gt;
    &lt;marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"&gt;
      &lt;path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" /&gt;
    &lt;/marker&gt;
    &lt;marker id="arrow-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"&gt;
      &lt;path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" /&gt;
    &lt;/marker&gt;
  &lt;/defs&gt;

  &lt;rect width="900" height="520" fill="#0f172a" rx="12" /&gt;
  
  &lt;text x="450" y="32" text-anchor="middle" fill="#e2e8f0" font-family="system-ui, -apple-system, sans-serif" font-size="18" font-weight="700" letter-spacing="0.5"&gt;Coding Agent — Orchestrator Loop&lt;/text&gt;
  &lt;text x="450" y="52" text-anchor="middle" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="11"&gt;prompt → tool call → result → repeat&lt;/text&gt;

  &lt;text x="80" y="85" text-anchor="middle" fill="#475569" font-family="system-ui, -apple-system, sans-serif" font-size="10" font-weight="600" letter-spacing="1"&gt;INPUT&lt;/text&gt;
  &lt;text x="280" y="85" text-anchor="middle" fill="#475569" font-family="system-ui, -apple-system, sans-serif" font-size="10" font-weight="600" letter-spacing="1"&gt;SEARCH&lt;/text&gt;
  &lt;text x="480" y="85" text-anchor="middle" fill="#475569" font-family="system-ui, -apple-system, sans-serif" font-size="10" font-weight="600" letter-spacing="1"&gt;READ &amp; PARSE&lt;/text&gt;
  &lt;text x="680" y="85" text-anchor="middle" fill="#475569" font-family="system-ui, -apple-system, sans-serif" font-size="10" font-weight="600" letter-spacing="1"&gt;GENERATE&lt;/text&gt;
  &lt;text x="820" y="85" text-anchor="middle" fill="#475569" font-family="system-ui, -apple-system, sans-serif" font-size="10" font-weight="600" letter-spacing="1"&gt;OUTPUT&lt;/text&gt;

  &lt;rect id="node-cli" x="25" y="100" width="110" height="50" rx="10" fill="url(#grad-cli)" opacity="0.9" /&gt;
  &lt;text x="80" y="122" text-anchor="middle" fill="white" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600"&gt;CLI Entry&lt;/text&gt;
  &lt;text x="80" y="138" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;--repo --issue&lt;/text&gt;

  &lt;rect id="node-orch" x="215" y="100" width="130" height="50" rx="10" fill="url(#grad-orch)" opacity="0.9" /&gt;
  &lt;text x="280" y="122" text-anchor="middle" fill="white" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600"&gt;Orchestrator&lt;/text&gt;
  &lt;text x="280" y="138" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;RunState + Budget&lt;/text&gt;

  &lt;rect id="node-gh" x="215" y="190" width="130" height="50" rx="10" fill="url(#grad-gh)" opacity="0.9" /&gt;
  &lt;text x="280" y="212" text-anchor="middle" fill="white" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600"&gt;GitHub Tool&lt;/text&gt;
  &lt;text x="280" y="228" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;search_code / get_file&lt;/text&gt;

  &lt;rect id="node-ast" x="415" y="190" width="130" height="50" rx="10" fill="url(#grad-ast)" opacity="0.9" /&gt;
  &lt;text x="480" y="212" text-anchor="middle" fill="white" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600"&gt;AST Tool&lt;/text&gt;
  &lt;text x="480" y="228" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;ast → tree-sitter&lt;/text&gt;

  &lt;rect id="node-llm" x="615" y="190" width="130" height="50" rx="10" fill="url(#grad-llm)" opacity="0.9" /&gt;
  &lt;text x="680" y="212" text-anchor="middle" fill="white" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600"&gt;LLM Tool&lt;/text&gt;
  &lt;text x="680" y="228" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;Groq: generate / explain&lt;/text&gt;

  &lt;rect id="node-val" x="615" y="280" width="130" height="50" rx="10" fill="url(#grad-val)" opacity="0.9" /&gt;
  &lt;text x="680" y="302" text-anchor="middle" fill="white" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600"&gt;Validator&lt;/text&gt;
  &lt;text x="680" y="318" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;lenient parse / strict apply&lt;/text&gt;

  &lt;rect id="node-out" x="765" y="100" width="110" height="50" rx="10" fill="url(#grad-out)" opacity="0.9" /&gt;
  &lt;text x="820" y="122" text-anchor="middle" fill="white" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600"&gt;Output&lt;/text&gt;
  &lt;text x="820" y="138" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;.patch + .trace.json&lt;/text&gt;

  &lt;rect id="node-fail" x="615" y="370" width="130" height="50" rx="10" fill="url(#grad-fail)" opacity="0.9" /&gt;
  &lt;text x="680" y="392" text-anchor="middle" fill="white" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600"&gt;Can't Patch&lt;/text&gt;
  &lt;text x="680" y="408" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;insufficient_context&lt;/text&gt;

  &lt;line x1="135" y1="125" x2="215" y2="125" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" /&gt;
  &lt;line x1="280" y1="150" x2="280" y2="190" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" /&gt;
  &lt;line x1="265" y1="190" x2="265" y2="150" stroke="#334155" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#arrow)" /&gt;
  &lt;path d="M 345 125 Q 380 125 380 160 Q 380 215 415 215" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" /&gt;
  &lt;path d="M 415 205 Q 380 205 380 160 Q 380 135 345 135" fill="none" stroke="#334155" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#arrow)" /&gt;
  &lt;path d="M 345 125 Q 500 125 500 160 Q 500 215 615 215" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" /&gt;
  &lt;line x1="680" y1="240" x2="680" y2="280" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" /&gt;
  &lt;path d="M 615 305 Q 500 305 500 160 Q 500 135 345 135" fill="none" stroke="#334155" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#arrow)" /&gt;
  &lt;line x1="345" y1="125" x2="765" y2="125" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" /&gt;
  &lt;line x1="680" y1="330" x2="680" y2="370" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" /&gt;

  &lt;path d="M 345 115 Q 400 80 280 80 Q 160 80 215 115" fill="none" stroke="#334155" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#arrow)" /&gt;
  &lt;text x="280" y="75" text-anchor="middle" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;loop until budget exhausted or patch valid&lt;/text&gt;

  &lt;circle id="packet" r="5" fill="#38bdf8" filter="url(#glow)"&gt;
    &lt;animateMotion dur="8s" repeatCount="indefinite" path="M 80 125 L 215 125 L 280 150 L 280 190 L 265 190 L 265 150 L 345 125 L 380 125 L 380 160 L 380 215 L 415 215 L 415 205 L 380 205 L 380 160 L 380 135 L 345 135 L 345 125 L 500 125 L 500 160 L 500 215 L 615 215 L 680 240 L 680 280 L 615 305 L 500 305 L 500 160 L 500 135 L 345 135 L 345 125 L 765 125" /&gt;
  &lt;/circle&gt;

  &lt;circle r="3" fill="#34d399" opacity="0.7"&gt;
    &lt;animateMotion dur="8s" begin="2s" repeatCount="indefinite" path="M 265 190 L 265 150" /&gt;
  &lt;/circle&gt;
  &lt;circle r="3" fill="#34d399" opacity="0.7"&gt;
    &lt;animateMotion dur="8s" begin="3.5s" repeatCount="indefinite" path="M 415 205 L 380 205 L 380 160 L 380 135 L 345 135" /&gt;
  &lt;/circle&gt;
  &lt;circle r="3" fill="#34d399" opacity="0.7"&gt;
    &lt;animateMotion dur="8s" begin="6s" repeatCount="indefinite" path="M 615 305 L 500 305 L 500 160 L 500 135 L 345 135" /&gt;
  &lt;/circle&gt;

  &lt;rect x="215" y="430" width="530" height="70" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1" /&gt;
  &lt;text x="230" y="455" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600"&gt;Tool-Call Budget&lt;/text&gt;
  &lt;text x="230" y="472" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;Hard cap enforced at orchestrator — LLM never self-limits&lt;/text&gt;
  
  &lt;rect x="400" y="448" width="200" height="14" rx="7" fill="#334155" /&gt;
  &lt;rect x="400" y="448" width="140" height="14" rx="7" fill="#0ea5e9"&gt;
    &lt;animate attributeName="width" values="200;160;120;80;40;200" dur="8s" repeatCount="indefinite" /&gt;
  &lt;/rect&gt;
  &lt;text x="610" y="458" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="10"&gt;20 → 0&lt;/text&gt;

  &lt;g transform="translate(25, 430)"&gt;
    &lt;rect width="170" height="70" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1" /&gt;
    &lt;text x="85" y="18" text-anchor="middle" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="10" font-weight="600"&gt;Legend&lt;/text&gt;
    &lt;line x1="15" y1="32" x2="35" y2="32" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" /&gt;
    &lt;text x="42" y="36" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;Tool call&lt;/text&gt;
    &lt;line x1="15" y1="52" x2="35" y2="52" stroke="#334155" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#arrow)" /&gt;
    &lt;text x="42" y="56" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="9"&gt;Result return&lt;/text&gt;
  &lt;/g&gt;

  &lt;rect x="213" y="98" width="134" height="54" rx="12" fill="none" stroke="#38bdf8" stroke-width="2" opacity="0"&gt;
    &lt;animate attributeName="opacity" values="0;1;0;0;0;0;0;0;0;0" dur="8s" repeatCount="indefinite" /&gt;
  &lt;/rect&gt;
  &lt;rect x="213" y="188" width="134" height="54" rx="12" fill="none" stroke="#38bdf8" stroke-width="2" opacity="0"&gt;
    &lt;animate attributeName="opacity" values="0;0;1;0;0;0;0;0;0;0" dur="8s" repeatCount="indefinite" /&gt;
  &lt;/rect&gt;
  &lt;rect x="413" y="188" width="134" height="54" rx="12" fill="none" stroke="#38bdf8" stroke-width="2" opacity="0"&gt;
    &lt;animate attributeName="opacity" values="0;0;0;1;0;0;0;0;0;0" dur="8s" repeatCount="indefinite" /&gt;
  &lt;/rect&gt;
  &lt;rect x="613" y="188" width="134" height="54" rx="12" fill="none" stroke="#38bdf8" stroke-width="2" opacity="0"&gt;
    &lt;animate attributeName="opacity" values="0;0;0;0;1;0;0;0;0;0" dur="8s" repeatCount="indefinite" /&gt;
  &lt;/rect&gt;
  &lt;rect x="613" y="278" width="134" height="54" rx="12" fill="none" stroke="#38bdf8" stroke-width="2" opacity="0"&gt;
    &lt;animate attributeName="opacity" values="0;0;0;0;0;1;0;0;0;0" dur="8s" repeatCount="indefinite" /&gt;
  &lt;/rect&gt;
  &lt;rect x="763" y="98" width="114" height="54" rx="12" fill="none" stroke="#38bdf8" stroke-width="2" opacity="0"&gt;
    &lt;animate attributeName="opacity" values="0;0;0;0;0;0;0;1;0;0" dur="8s" repeatCount="indefinite" /&gt;
  &lt;/rect&gt;
&lt;/svg&gt;
&lt;/p&gt;

---

## Features

- 🔎 **Identifier-focused code search** — extracts `snake_case`/`CamelCase`/
  backticked symbols from the report (raw prose confuses GitHub's lexical
  search into returning `CHANGES.md`)
- 🌳 **AST-structured context** — the model sees the *functions named in the
  bug report* with real bodies, not a raw file dump
- ✅ **Lenient-but-safe patch validation** — tolerates LLM whitespace/quirkiness,
  but hard-rejects patches touching files it never read, or producing invalid
  Python
- 💰 **Hard tool-call budget** — enforced at the orchestrator; a bad search loop
  can't burn API quota
- 🔇 **Loud failure** — a clear "could not patch confidently" path with a full
  trace, instead of a confidently-wrong patch
- 📜 **Full JSON trace** of every tool call (inputs/outputs/duration) for
  later analysis — secrets redacted at capture time

## Install

Requires **Python 3.11+**.

```bash
git clone https://github.com/abdullahhshafique/coding-agent.git
cd coding-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
