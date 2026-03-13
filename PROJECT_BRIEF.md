# Acme Dental Agent — Architectural Brief

## Overview

Technical challenge to build AI receptionist for dental clinic. This document outlines the key architectural decisions made during development and the reasoning behind each choice.

---

## Framework — FastAPI

FastAPI was chosen as the web framework over alternatives such as Django for several reasons:

- **Async-native** — FastAPI is built on ASGI and supports `async`/`await` throughout, which is essential when the primary workload is awaiting responses from an LLM and external APIs (Calendly, SMTP or twilio text confirmation if used).
- **Lightweight setup** — For a project of this scope, Django's ORM configuration, middleware stack, and project scaffolding would add unnecessary overhead. FastAPI requires minimal boilerplate and is quicker to iterate on.
- **MVP-appropriate** — This is a demonstration-scale project where the AI agent does the heavy lifting. FastAPI is a good fit for this style of thin API layer that primarily orchestrates tool calls and persists results.

---

## LLM — Gemini 2.5 Flash

Google Gemini 2.5 Flash was selected as the underlying model:

- **Benchmark performance** — Gemini 2.5 Flash performs well on agentic tasks involving basic tool use, which is the primary requirement here (slot lookups, booking, FAQ retrieval). It does not require a more capable or expensive model for this task profile.
- **Cost** — The model is significantly cheaper than comparable alternatives.
- **Token allowance** — The Gemini Tier 1 provides a sufficient daily request quota to test and refine agent behaviour, guardrails, and system prompt changes without incurring cost that's any more than pennies.

---

## Database — SQLite

SQLite was selected for persistence:

- **Simplicity** — The data requirements are minimal: a PIN record per appointment (hashed name and PIN), a conversation audit log, session booking records, and admin review notes. SQLite is more than adequate for this workload at demo or small-clinic scale.
- **No infrastructure overhead** — No separate database server is required. The database is a single file mounted via a Docker volume, which simplifies both local development and deployment.
- **Production note** — For a multi-tenant or higher-traffic production system, this would be replaced with PostgreSQL.

---

## Knowledge Base — Markdown file

Agent context is served via a flat Markdown file (`KNOWLEDGE_BASE.md`) loaded at startup:

- **Sufficient for a single-agent, single-domain deployment** — The clinic has a small, stable FAQ (pricing, policies, what to bring, cancellation terms). A Markdown file is easy to maintain and update without re-deploying a vector index.
- **Production consideration** — For a multi-agent system or an agent requiring access to large or frequently changing document sets, this approach would not scale. In that scenario I would use a vector database (e.g., pgvector on PostgreSQL) with embedding-based retrieval would be the appropriate replacement. Using vector is overkill for something simple like this but in real world application I found it to be very quick. I have used it before in vehicle routing problems to calculate distance matrixs with roads.

---

## Containerisation — Docker

Docker + Docker Compose was used to bundle and run the project:

- **Portability** — The entire project (backend, frontend/Nginx, SQLite volume) is self-contained in a single `docker compose up --build` command. This made it straightforward to move the project between devices during development without reinstalling dependencies or reconfiguring the environment each time.
- **Reproducibility** — All dependencies, environment variables, and service wiring are declared in the Compose file. There is no divergence between environments and no manual setup steps to remember between sessions.
- **Developer convenience** — For a project built iteratively, Docker removes the overhead of managing virtual environments, port conflicts, and startup order across multiple processes. Rebuilding after a change is a single command, which keeps the feedback loop short.

/tests were done outside of docker though which was a bit of a pain for agent orientated tasks. Handy for testing calendly api and tool's functions.
---

## Security — Appointment PIN

A 6-digit security PIN was introduced to protect appointment amendments and cancellations:

- **Problem identified** — During testing it became apparent that without any identity verification, it was trivially easy to supply a patient's name and email and cancel or amend their appointment. This represented a real fraud risk in production.
- **Solution** — On booking, a 6-digit PIN is generated and bcrypt-hashed before storage. The PIN is delivered to the patient via their Calendly confirmation email and is shown once in the chat at the point of booking. It is not repeated in subsequent messages.
- **Session exemption** — If the patient is amending or cancelling within the same session in which they booked, no PIN is required. The PIN is only enforced when a new session is started, which covers the case of a third party attempting to interfere with someone else's appointment.
- **Lockout** — Three consecutive failed PIN attempts trigger a lockout on that appointment record to prevent brute-force guessing.

---

## Admin Dashboard

A lightweight admin UI (`/admin.html`) backed by a dedicated API (`/admin-api/`) was built to support ongoing agent evaluation:

- **Motivation** — During testing, conversations were being run specifically to probe the agent's weaknesses: prompt injection attempts, off-topic queries, social engineering for sensitive data, and attempts to exhaust the agent's context or manipulate its memory. Reviewing these conversations through a raw database query was impractical.
- **Functionality** — The dashboard displays all recorded conversation sessions with timestamps and a first-message preview. Each session can be opened to view the full transcript and marked with a review status: `unreviewed`, `safe`, `risky`, or `dangerous`. Free-text notes can be added to each session to record specific observations.
- **Purpose** — The review workflow feeds directly into improvements to the system prompt, guardrail rules, and tool docstrings. Flagging a session as `risky` or `dangerous` provides a concrete record of the failure mode and the context in which it occurred.
