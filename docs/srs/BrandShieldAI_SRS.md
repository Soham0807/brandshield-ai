# Software Requirements Specification

## BrandShield AI – Real-Time Brand Risk & Sentiment Intelligence System

| | |
|---|---|
| **Document version** | 1.0 |
| **Date** | 6 October 2025 |
| **Project** | Final Year Project, PID 02 – T.Y. A (AIDS), K.K. Wagh Institute of Engineering Education & Research, Nashik |
| **Team** | Soham Borse, Tanish Bantwal, Aryan Baakle, Omsingh Rajput |
| **Guide** | Dr. Darshan Medhane |
| **Baseline** | Repository `main` at commit `d4271a8`, plus untracked `backend/scripts/go_live.py`, `backend/scripts/export_static.py`, `start-public.bat` |

### Revision history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2025-10-06 | First SRS. Written from the implemented system (reverse-engineered from code), not from a pre-build plan. |

### How to read this document

This SRS was written after the system had been built. Every requirement was checked against the code at the baseline commit above. Each requirement carries one of three statuses:

- **Implemented** – present in the code and exercised by the running system.
- **Partial** – present but with a known gap, which is described next to the requirement.
- **Planned** – not in the code. These are kept in Section 16 (Future Scope) and are never mixed into the functional requirements.

Anything we could not verify from the code alone is marked **To be confirmed (TBC)**.

File references are relative to the repository root. `routes.py` always means `backend/app/api/routes.py`.

---

## Table of contents

1. Introduction
2. Overall Description
3. System Overview
4. Functional Requirements
5. Non-Functional Requirements
6. System Interfaces
7. Data Requirements
8. Detailed Validation Requirements
9. Error Handling Requirements
10. Use Cases
11. System Constraints
12. Security Requirements
13. Performance Requirements
14. Testing and Verification Requirements
15. Deployment Requirements
16. Future Scope
17. Traceability Matrix
- Appendix A – SRS Validation Summary
- Appendix B – Implementation/Documentation Inconsistencies Found

---

## 1. Introduction

### 1.1 Purpose

This document specifies the requirements of BrandShield AI as implemented. It is meant to:

- give evaluators a complete, checkable description of what the system does;
- serve as the reference for test cases (Section 14) and the traceability matrix (Section 17);
- record the known gaps between the implementation, its documentation and what a production system would need.

### 1.2 Scope

BrandShield AI collects public or owned social-media mentions of one brand, runs each mention through an NLP pipeline (cleaning, language detection, spam filtering, hybrid DistilBERT sentiment, aspect-based sentiment), stores the results, and continuously computes:

- sentiment trends and KPIs over selectable time windows,
- crisis anomalies (Isolation Forest combined with a robust z-score),
- a 12-hour sentiment forecast (Prophet, with Holt smoothing as fallback),
- a 0–100 brand-risk score built from five signals,
- alerts, delivered to the dashboard and optionally to email, Slack, Microsoft Teams and SMS.

All of this is presented in a React dashboard that updates live over a WebSocket.

**In scope:** the FastAPI backend (`backend/app/`), the React dashboard (`frontend/`), the evaluation script (`backend/scripts/evaluate_model.py`), helper scripts, and the deployment artefacts (`Dockerfile`, `docker-compose.yml`, `deploy/`, `start*.bat`).

**Out of scope:** the phase-1 Flask prototype (`app.py`, `routes/`, `services/`, `templates/`, root `scripts/`, root `data/`). The README describes it as an "earlier Flask prototype (phase 1)". The current system does not use it, and it is not specified here.

**Single-tenant by design:** one installation monitors one brand at a time. The brand name and keywords can be changed at runtime. There are no user accounts (see Section 12).

### 1.3 Intended audience

| Reader | Sections of most interest |
|---|---|
| Project guide / evaluators | 1–4, 10, 14, 17, Appendix A |
| Developers on the team | 3–9, 17 |
| Whoever deploys or operates the system | 6, 11, 12, 15 |
| Testers | 8, 9, 14, 17 |

### 1.4 Definitions, acronyms and abbreviations

| Term | Meaning in this project |
|---|---|
| Mention | One unit of text about the brand (comment, post, review, news item), stored as a row of the `mentions` table. |
| Source | Where a mention came from: `instagram`, `youtube`, `twitter`, `reddit`, `news`, `appstore`, `google_reviews`, `csv`, `api`, `manual`, or any source string supplied through the ingest API. |
| Origin | `live` (real data) or `simulated` (produced by the built-in simulator). |
| Aspect | A business dimension a mention talks about, such as `delivery` or `price`. Aspects are defined by an editable keyword lexicon. |
| ABSA | Aspect-Based Sentiment Analysis. |
| Sentiment score | `P(positive) − P(negative)`, in the range [-1, 1]. |
| Health index | `round(50 + 50 × average score)`, clamped to 0–100. Spam is excluded. |
| Risk score | Integer from 0 to 100 combining negativity, velocity, anomaly, forecast and concentration (FR-028). |
| Bucket | A fixed time interval (15 min by default) over which mentions are aggregated. |
| Incident | One or more consecutive anomalous buckets merged into a single event. |
| Crisis simulation | A simulator mode that temporarily floods the stream with complaints about one aspect. |
| Bus | The message queue between collectors and the processor: Apache Kafka, or an in-memory asyncio queue. |
| Hub | The WebSocket broadcaster (`pipeline/hub.py`). |
| Runtime config | Settings that can be changed from the dashboard. They are persisted in the `settings` table under the key `runtime_config`. |
| Setup endpoint | An endpoint restricted to requests from the host machine itself (FR-045). |
| Tunnel | A Cloudflare quick tunnel (`cloudflared`) that gives the local server a public HTTPS address. |
| IF | Isolation Forest. |
| MAD | Median Absolute Deviation. |
| OAuth | OAuth 2.0 authorization-code flow. |
| SPA | Single-Page Application. |
| TBC | To be confirmed. |
| WAL | SQLite write-ahead logging mode. |

### 1.5 References

| Ref | Document |
|---|---|
| R1 | `README.md` – setup, architecture, evaluation results |
| R2 | `backend/.env.example` – configuration keys |
| R3 | `deploy/DEPLOY.md`, `deploy/huggingface/README.md` – deployment guides |
| R4 | `docs/uml/` – class, object and component diagrams generated from the code |
| R5 | `docs/paper/` – draft research paper and the source of each reported number |
| R6 | IEEE Std 830-1998 / ISO/IEC/IEEE 29148:2018 – structure followed loosely |
| R7 | Instagram API with Instagram Login (Meta), YouTube Data API v3, Twitter API v2, Reddit API, Apple iTunes Search & customer-review RSS – external API documentation |
| R8 | Hugging Face models `cardiffnlp/twitter-xlm-roberta-base-sentiment` and `cardiffnlp/twitter-roberta-base-sentiment-latest` (deployed ensemble); `tabularisai/multilingual-sentiment-analysis` and `distilbert-base-uncased-finetuned-sst-2-english` (fallbacks) |

---

## 2. Overall Description

### 2.1 Product perspective

BrandShield AI is a self-contained web application. It is not part of a larger product. It replaces the phase-1 Flask prototype, which read CSV files in batch, with a streaming design:

```
Collectors ─► Message bus ─► Stream processor ─► SQLite ─► FastAPI (REST + WebSocket) ─► React dashboard
                (Kafka |      (preprocess,         │
                 memory)       sentiment, ABSA,    ├─ analytics loop (30 s): anomalies, risk, alert rules
                               spam)               ├─ forecast loop (300 s): Prophet / Holt
                                                   └─ alert engine ─► dashboard, email, Slack, Teams, SMS
```

One Python process (`uvicorn app.main:app`) hosts the API, the background loops and the static dashboard build. Kafka is the only optional external runtime dependency. If Kafka cannot be reached, the system falls back to the in-memory bus.

### 2.2 Product functions (summary)

1. Collect mentions from the simulator, Google News/RSS, Reddit, Twitter/X, Apple App Store reviews, YouTube channels, connected Instagram Business/Creator accounts, CSV upload and a REST ingest endpoint.
2. Normalise and de-duplicate mentions, then pass them through the NLP pipeline.
3. Persist every analysed mention, together with its probabilities and aspect results.
4. Serve KPIs, trends, aspect tables, anomaly series, forecasts and the risk score.
5. Evaluate six snapshot-based alert rules and one per-mention rule. Deduplicate alerts with cool-downs, and deliver them.
6. Let users manage alerts, settings, thresholds, aspects, data sources, API keys and connected social accounts from the UI.
7. Show pipeline performance and offline model evaluation metrics.
8. Provide demo tooling: seeded history, crisis simulation, data reset, and a public tunnel.

### 2.3 User classes and characteristics

The application has **no login**. Every user who can open the dashboard has the same privileges, with one exception: setup endpoints accept only requests that come from the host machine without proxy headers (FR-045).

| User class | Description | Typical actions | Technical skill |
|---|---|---|---|
| Brand analyst / manager | Watches brand health and responds to issues | Dashboard, Mentions, Alerts, Aspects, Trends | Non-technical |
| Operator (local admin) | Runs the system on their own machine or server | Connect accounts, save API keys, start the tunnel, reset data, change thresholds | Moderate: can edit `.env` and run scripts |
| Evaluator / presenter | Faculty or team member demonstrating the system | Crisis simulation, Analyze Text, Performance page | Moderate |
| External system | Script or service pushing data | `POST /api/ingest`, `POST /api/ingest/csv` | Developer |
| Scheduler (internal actor) | Background asyncio tasks | Polling, analytics, forecasting, metrics push | – |

### 2.4 Operating environment

| Component | Requirement | Source |
|---|---|---|
| Python | 3.12+ (Docker images use `python:3.12-slim`; the local venv was observed on 3.14) | README, Dockerfiles |
| Node.js | 20+ (needed only to build the dashboard) | README |
| OS | Windows 10/11 (`start.bat`), Ubuntu 22.04/24.04 (`deploy/install.sh`), any Docker host. On macOS the tunnel needs `brew install cloudflared`. | scripts, `tunnel.py` |
| Memory | About 1.8 GB resident for PyTorch and the model. The server guide asks for at least 4 GB RAM. The systemd unit caps memory at 3.5 GB. | DEPLOY.md, `brandshield.service` |
| Disk | About 1.6 GB for the two model downloads. The server guide recommends 25 GB. | README, DEPLOY.md |
| CPU | CPU inference only. No GPU is required or used. | Dockerfiles use the CPU torch wheel index |
| Browser | A modern browser with WebSocket and ES-module support. The Notification API is optional. | `frontend/src/lib/live.jsx` |
| Network | Outbound HTTPS to Hugging Face (first model download) and to whichever source APIs are enabled | – |

### 2.5 Design and implementation constraints

- **C-1 Storage:** SQLite (single file, WAL mode) accessed through one connection guarded by a re-entrant lock (`db.py`). All SQL lives in `db.py` and the service classes, so the store can be swapped later.
- **C-2 Single process:** the server runs with `--workers 1`. The runtime state (crisis state, tunnel state, evaluation flag, caches) lives in memory and is not shared across processes.
- **C-3 Official APIs only:** Instagram is accessed only through the official OAuth flow. Password-based or unofficial scraping is deliberately unsupported (README).
- **C-4 External quotas:** the YouTube Data API allows 10,000 units/day on a free key. Twitter/X search requires a paid tier. Reddit blocks unauthenticated traffic. Meta requires an HTTPS redirect URI and app roles or App Review.
- **C-5 Model:** a fixed pretrained model, with no training inside the system. Its 5 classes are folded into 3.
- **C-6 Frontend:** React 19, Vite 8, Tailwind 4, Chart.js 4, React Router 7. The production build is served by FastAPI from `frontend/dist`.

### 2.6 Assumptions and dependencies

- **A-1** The machine can download the Hugging Face model on first start. Otherwise the fallback model must already be cached (TBC for fully offline installs).
- **A-2** NLTK stop-word and WordNet data are downloaded by the start scripts. If they are missing, the preprocessor falls back to built-in rules (`preprocess.py`).
- **A-3** Timestamps without a time zone (for example, from CSV files) are interpreted in the local time zone of the machine running the backend (`db.parse_any_datetime`).
- **A-4** The simulator's templates and their labels are written by the team. Live-agreement figures computed on simulated data are therefore optimistic (README limitation).
- **A-5** Instagram data is limited to the connected account's own posts. Comments on posts published before the account became professional are not returned by the API.
- **A-6** The Python package `cryptography` is available. It is imported by `integrations/instagram.py` but **not listed** in `backend/requirements.txt` (see Appendix B, item 1).

---

## 3. System Overview

### 3.1 End-to-end workflow

1. **Input.** A collector loop (`core.App._collector_loop`), the simulator loop (`_seed_then_simulate`), a sync request (`sync_youtube` / `sync_instagram`) or an ingest endpoint calls `App.publish(raw)`. This stamps `ingested_at` and puts the raw dict on the bus.
2. **Batching.** `Processor.run` reads batches of up to 32 messages, waiting at most 0.5 s per batch.
3. **Normalisation.** `normalise_raw` fills in defaults, parses timestamps, clamps future dates to now, and derives a deterministic `id`.
4. **De-duplication.** Rows are deduplicated within the batch and against the database (`existing_ids`).
5. **NLP.** `Processor.analyze` runs `preprocess()` → `SentimentModel.predict()` → `AspectExtractor.analyze_batch()`.
6. **Storage.** `Database.insert_mentions` runs `INSERT OR IGNORE`.
7. **Real-time push.** Up to 50 new mentions are broadcast as a `mentions` event. `AlertEngine.check_mentions` applies the viral-negative rule.
8. **Analytics loop (every 30 s).** `AnalyticsService.compute_snapshot` loads the last 72 h, buckets the data at 15 min, detects anomalies, computes risk and incidents, then calls `AlertEngine.evaluate`. A `risk` event is broadcast.
9. **Forecast loop (every 300 s).** `refresh_forecast` builds hourly series from the last 7 days and forecasts 12 h ahead.
10. **Output.** The REST endpoints serve aggregates on demand, and the WebSocket keeps the dashboard current.

### 3.2 Major modules

| # | Module | Location | Responsibility |
|---|---|---|---|
| M1 | Application core | `backend/app/core.py`, `main.py` | Wires the components together, runs the background tasks, publishes to the bus, implements reset and live-only actions |
| M2 | Configuration | `config.py`, `runtime.py` | Static settings from env/`.env`, runtime config persisted in the DB |
| M3 | Collectors | `collectors/platforms.py`, `collectors/public_sources.py`, `collectors/simulator.py` | Reddit, RSS/News, Twitter, App Store, simulator |
| M4 | Social integrations | `integrations/youtube.py`, `integrations/instagram.py`, `integrations/tunnel.py` | YouTube channel monitoring, Instagram OAuth and sync, Cloudflare tunnel |
| M5 | Streaming pipeline | `pipeline/bus.py`, `pipeline/processor.py`, `pipeline/hub.py`, `pipeline/metrics.py` | Bus, processing, WebSocket hub, metrics |
| M6 | NLP | `nlp/preprocess.py`, `nlp/sentiment.py`, `nlp/aspects.py` | Cleaning, language, spam, sentiment, ABSA |
| M7 | Analytics | `analytics/service.py`, `analytics/anomaly.py`, `analytics/forecast.py`, `analytics/risk.py` | Aggregation, anomalies, forecast, risk |
| M8 | Alerts | `alerts/engine.py`, `alerts/notifiers.py` | Rules, deduplication, delivery |
| M9 | Storage | `db.py` | Schema, migrations, data access |
| M10 | REST/WS API | `api/routes.py` | 43 REST routes (2 hidden from OpenAPI) and 1 WebSocket |
| M11 | Dashboard | `frontend/src/` | 10 pages, live context, API client |
| M12 | Evaluation & scripts | `backend/scripts/evaluate_model.py`, `go_live.py`, `export_static.py` | Offline metrics, public-link helper, static snapshot export |

### 3.3 Module interaction

```
                    ┌──────────── RuntimeConfig (M2) ◄──── PUT /api/settings
                    │ get()/subscribe()
 Simulator ─┐       ▼
 Collectors ┼─► App.publish ─► Bus (M5) ─► Processor ─► NLP (M6) ─► Database (M9)
 YouTube/IG ┤                               │                         ▲   ▲
 /ingest    ┘                               ├─► Hub "mentions" ─► WS  │   │
                                            └─► AlertEngine.check_mentions  │
 analytics loop ─► AnalyticsService (M7) ─► AlertEngine.evaluate ─► Notifier ─► Email/Slack/Teams/SMS
                         │                         └─► alerts table, Hub "alert"
                         └─► Hub "risk"
 REST routes (M10) ─► AnalyticsService / Database / services ─► JSON ─► Dashboard (M11)
```

### 3.4 High-level architecture

- **Presentation layer:** the React SPA, served as static files by FastAPI (`main.spa`), or by the Vite dev server on port 5173, which proxies `/api` and `/ws`.
- **Application layer:** FastAPI routes plus the `App` container, which owns every service. CPU-bound work (inference, pandas, Prophet) runs in worker threads through `asyncio.to_thread`, so the event loop stays responsive.
- **Data layer:** SQLite (`backend/data/brandshield.db`), plus the files `backend/.env`, `backend/data/secret.key`, `backend/data/evaluation.json` and `backend/data/bin/` (the cloudflared binary and its log).
- **Integration layer:** httpx clients for the external APIs, aiokafka for Kafka, smtplib for email.

Diagrams that match this description are in `docs/uml/` (component diagram `03-component-diagram.png`, class diagrams `01*.png`, `04-*.png`).

---

## 4. Functional Requirements

Notation: "The system shall …" is a binding requirement. **Code** points to where the requirement is implemented. Unless stated otherwise, endpoint paths are under `/api`. FastAPI request-schema failures always return HTTP 422 with a `detail` array, and are not repeated in every FR.

### 4.1 Data Collection & Ingestion (M3)

#### FR-001 Simulated mention stream and history seeding
**Status:** Implemented · **Code:** `collectors/simulator.py` → `MentionSimulator.generate()`, `history()`; `core.py` → `App._seed_then_simulate()`, `seed_history()`

- **Description:** When the `simulator` source is enabled, the system shall generate a continuous stream of realistic brand mentions. If the database is empty at start-up, it shall also generate past history so that the charts and the forecast have data.
- **Preconditions:** Sentiment model loaded (the loop waits on `model.ready`). Runtime `sources.simulator = true`.
- **Inputs:** Runtime `brand_name`, `simulator_rate_per_min` (0.5–600); env `SEED_HISTORY_DAYS` (default 3).
- **Processing:**
  1. On start, if the simulator is enabled, `SEED_HISTORY_DAYS > 0` and `mentions` is empty, generate `days` of history. The history includes one 100-minute delivery incident at intensity 0.8, placed `min(30 h, 40 % of the window)` before now. It is processed in chunks of 256 without broadcasting, and seeding progress is broadcast.
  2. Afterwards, sleep for an exponential inter-arrival time with rate `rate/1.1 × seasonal_factor(IST hour)`, capped at 30 s, then publish one mention.
  3. Each mention is a mix of spam (4 %), mixed opinions (5 %) and aspect templates. Weights: positive 0.62, neutral 0.24, negative 0.14. Text is in English, Hinglish, Hindi or Marathi. Sources are instagram/twitter/reddit/google_reviews, and `origin = "simulated"`. The intended label is kept in `true_label`.
- **Outputs:** Raw mentions on the bus. Seeding status `{total, done}` in `/api/status`, then a `refresh` WS event.
- **Postconditions:** After seeding, the forecast and the snapshot are recomputed and the analytics cache is cleared.
- **Validation:** The rate is validated by RuntimeConfig (VR-030). Turning the simulator off while the loop sleeps prevents the next publish.
- **Errors:** A seeding exception is logged, `seeding` is reset to `null`, and live simulation continues.

#### FR-002 Crisis simulation
**Status:** Implemented · **Code:** `routes.py` → `start_crisis()`, `stop_crisis()`; `simulator.py` → `start_crisis()`, `CrisisState`

- **Description:** An evaluator shall be able to start a time-limited crisis in which complaints about one aspect dominate the simulated stream, and to stop it early.
- **Preconditions:** Simulator source enabled.
- **Inputs:** `POST /simulator/crisis` `{aspect, minutes, intensity}`; `POST /simulator/crisis/stop`.
- **Processing:** During the crisis the volume multiplier becomes `seasonal × (1 + 2.5 × intensity)`. With probability `0.55 + 0.35 × intensity`, a mention is a negative template for the crisis aspect. The other mentions use crisis weights (positive 0.35 / neutral 0.25 / negative 0.40). 3 % of crisis negatives get an engagement of 600–4000, which simulates viral posts.
- **Outputs:** Crisis state `{active, aspect, ends_at, intensity}`. A `status` WS broadcast.
- **Postconditions:** The crisis ends automatically at `ends_at`, or on stop, on data reset or on switching to live-only data.
- **Validation:** `aspect` ∈ simulator template keys {food_quality, service, delivery, price, ambience, hygiene, app_experience, packaging}. `minutes` 1–240 (default 20; the UI defaults to 15). `intensity` 0.1–1.0 (default 0.8).
- **Errors:** Unknown aspect → 422 `aspect must be one of [...]`. Simulator disabled → 409 `Enable the simulator source first`.

#### FR-003 Google News / RSS collector
**Status:** Implemented · **Code:** `collectors/platforms.py` → `RssCollector.poll()`

- **Description:** When the `rss` source is enabled, the system shall poll Google News RSS for the brand name, plus any extra feeds listed in `RSS_FEEDS`.
- **Inputs:** Brand, keywords, `RSS_FEEDS` (comma-separated URLs).
- **Processing:** The Google News query is `"<brand>"` with locale en-IN. The parser reads up to 50 entries per feed and strips HTML. Custom feeds are kept only if the text contains the brand or a keyword. Text is truncated to 2000 chars. Mentions are stored with `source = "news"` and engagement 0.
- **Outputs:** A list of raw mentions.
- **Validation:** Entries without a title are dropped later, because text is empty.
- **Errors:** A non-2xx HTTP response raises inside `poll`. The collector loop stores the message in `last_error` (FR-006).

#### FR-004 Reddit and Twitter/X collectors
**Status:** Implemented (credential-gated) · **Code:** `platforms.py` → `RedditCollector`, `TwitterCollector`

- **Description:** When enabled and configured, the system shall search Reddit and Twitter/X for recent posts that contain the brand or its keywords.
- **Preconditions:** Reddit needs `REDDIT_CLIENT_ID/SECRET` for reliable access, because unauthenticated access is usually blocked. Twitter needs `TWITTER_BEARER_TOKEN` on a paid tier.
- **Processing:**
  - **Reddit:** gets an OAuth client-credentials token (cached until 60 s before expiry) and searches with `q = OR` of up to 5 terms, `sort = new`, limit 50. Text is `title. selftext`, and engagement is score + comments.
  - **Twitter:** `/2/tweets/search/recent` with up to 6 terms and `-is:retweet`, max 50 results, with incremental `since_id`. Engagement is likes + retweets + replies.
- **Errors:** Reddit 401/403/429 → `CollectorError` ("Add REDDIT_CLIENT_ID/SECRET in .env"). Twitter with no token → `CollectorError`; 429 → "Twitter rate limit reached"; ≥400 → status code plus the first 200 chars of the response.

#### FR-005 App Store review collector
**Status:** Implemented · **Code:** `collectors/public_sources.py` → `AppStoreCollector`

- **Description:** When the `appstore` source is enabled, the system shall collect recent iOS App Store reviews of the brand's app and keep the star rating as ground truth.
- **Inputs:** `APPSTORE_APP_ID` (optional; otherwise the app is found with the iTunes Search API using the brand name), `APPSTORE_COUNTRY` (default `in`), up to 3 pages.
- **Processing:** Reads the customer-review RSS JSON and skips the app-description entry. Stars map to `true_label`: 1–2 → negative, 3 → neutral, 4–5 → positive. Engagement is the vote count.
- **Errors:** No app found → `CollectorError` that suggests setting `APPSTORE_APP_ID`. HTTP ≥400 (other than 404) → `CollectorError`. A 404 ends paging normally.

#### FR-006 Collector scheduling, source toggles and manual poll
**Status:** Implemented · **Code:** `core.py` → `_collector_loop()`, `wake_collectors()`; `routes.py` → `poll_now()`

- **Description:** Each collector shall run in its own background loop. It polls only while its source toggle is on, and its status is reported to the UI.
- **Processing:** The interval is the collector's `interval` (YouTube 300 s, Instagram 180 s) or `POLL_INTERVAL_SECONDS` (180 s), plus 0–10 s of random jitter. Polling happens early when `wake_collectors()` is called by `POST /collectors/poll`, or when sources, keywords, brand or keys change. Only items with non-empty `text` are published.
- **Outputs:** Per-collector status `{name, configured, requires_credentials, last_poll, last_count, last_error, total_collected}`, shown in `/api/status` and `/api/settings`.
- **Errors:** `CollectorError`, `InstagramError` and `YouTubeError` are stored verbatim in `last_error`. Other exceptions are stored as `Type: message` and logged as warnings. The loop continues in every case.

#### FR-007 REST bulk ingestion
**Status:** Implemented · **Code:** `routes.py` → `ingest()`, models `IngestItem`, `IngestRequest`

- **Description:** External systems shall be able to push mentions into the streaming pipeline.
- **Inputs:** `POST /ingest` with `{items: [{text, source?, author?, url?, created_at?, external_id?, engagement?}]}`.
- **Processing:** Each item is published to the bus. NLP runs asynchronously, so the response does not wait for analysis.
- **Outputs:** `{queued: n, bus: "memory"|"kafka"}`.
- **Validation:** VR-010 to VR-015. The model does not need to be ready: items wait in the bus.
- **Errors:** Schema violation → 422. If the memory bus is full (50,000 items), the request waits until there is space (back-pressure).

#### FR-008 CSV ingestion
**Status:** Implemented · **Code:** `routes.py` → `ingest_csv()`; UI `pages/Analyze.jsx` → `uploadCsv()`

- **Description:** A user shall be able to upload a CSV file of comments, which are queued into the pipeline.
- **Inputs:** Multipart field `file`. The text column is matched case-insensitively against `text`, `comment`, `content` or `message`. Optional columns: `created_at`/`timestamp`/`date`, `author`, `source`, `engagement`.
- **Processing:** The file is decoded as UTF-8 (a BOM is tolerated). Rows with blank text are skipped. `source` is lower-cased and defaults to `csv`. Engagement is parsed only if it is a non-negative decimal number, otherwise 0. Processing stops after 50,000 queued rows.
- **Outputs:** `{queued, filename}`.
- **Validation:** VR-020 to VR-026.
- **Errors:** > 20 MB → 413. Non-UTF-8 → 400. No text column → 400 `CSV needs a 'text' or 'comment' column` (the message lists only two of the four accepted names; see Appendix B).

### 4.2 Streaming Pipeline (M5)

#### FR-009 Message bus with Kafka fallback
**Status:** Implemented · **Code:** `pipeline/bus.py` → `create_bus()`, `KafkaBus`, `MemoryBus`

- **Description:** The system shall decouple producers from the processor through a bus. Kafka is used when configured, otherwise an in-memory queue.
- **Inputs:** `BUS_BACKEND` (`memory` | `kafka`), `KAFKA_BOOTSTRAP_SERVERS`, topic `brandshield.raw_mentions`, group `brandshield-processor`.
- **Processing:** For Kafka, the producer and consumer must each start within 10 s. The producer uses JSON serialisation and `linger_ms = 20`. The consumer uses `auto_offset_reset = latest` and auto-commit. If Kafka fails, a warning is logged and the memory bus (maxsize 50,000) is used. Batches hold up to 32 messages and wait up to 0.5 s.
- **Outputs:** The bus name in `/api/status` and `/api/system/metrics`. Queue depth is reported for the memory bus only (`null` for Kafka).
- **Errors:** Kafka connection failure → automatic fallback; the service does not fail to start.

#### FR-010 Normalisation and de-duplication
**Status:** Implemented · **Code:** `pipeline/processor.py` → `normalise_raw()`, `mention_id()`, `Processor.process_batch()`

- **Description:** Every raw message shall be normalised to one internal shape and stored at most once.
- **Processing:**
  - Text is stripped. Source defaults to `api` and is lower-cased.
  - `external_id` defaults to `sha1(text|author|created_at)`.
  - `id = sha1("source:external_id")[:24]`.
  - `created_at` is parsed by `parse_any_datetime`; it falls back to now and is clamped to now if in the future.
  - Engagement is converted to int. `origin` defaults to `live`.
  - Duplicates are removed within the batch (last occurrence wins) and against existing IDs, checked in chunks of 500.
- **Postconditions:** Re-ingesting the same item, for example the same YouTube comment on the next sync, does not create a second row.
- **Validation:** Messages with empty or whitespace-only text are dropped before analysis.
- **Errors:** An exception anywhere in a batch is caught by `Processor.run`, recorded in metrics (`errors_total`, `last_error`), and the stream continues. **The whole batch is lost**, with no retry (see NFR-REL-02).

### 4.3 NLP Pipeline (M6)

#### FR-011 Text preprocessing and language detection
**Status:** Implemented · **Code:** `nlp/preprocess.py` → `preprocess()`, `detect_language()`, `lemmatize()`

- **Description:** Each text shall be cleaned for display and prepared for the model, and its language shall be detected.
- **Processing (in order):**
  1. Remove HTML tags.
  2. Remove URLs.
  3. Remove `@mentions`.
  4. Turn `#tag` into `tag`.
  5. Squeeze runs of 4 or more repeated characters down to 2 ("sooooo" → "soo").
  6. Collapse whitespace. The result is `clean`.
  7. Replace 32 known emojis with words (😍 → "love"). The result is `model_text`.
  8. Tokenise Latin and Devanagari words and drop stop words (NLTK English, or the built-in list, plus Hinglish/Marathi fillers). Negations are always kept.
  9. Lemmatise with WordNet, or with suffix rules if WordNet is missing.
- **Language:** If Devanagari is present, the base language is `hi`, otherwise `en`. For texts of 12 characters or more, the langdetect result is used when its probability is ≥ 0.80. Empty clean text gives `unknown`.
- **Outputs:** `PreparedText {original, clean, model_text, tokens, lemmas, language, is_spam, spam_reason}`.
- **Known limitation:** langdetect can mislabel short informal text. For example, "Coffee was soo good love yum" was detected as `so` (Somali) in our check. Romanised Hinglish is labelled `en`.

#### FR-012 Spam detection
**Status:** Implemented · **Code:** `preprocess.py` → `detect_spam()`

- **Description:** The system shall flag spam and bot-like mentions. Flagged mentions are excluded from every sentiment metric, aspect table, anomaly feature and alert rule except the spam-wave rule.
- **Rules (first match wins):**
  1. Promotional or scam phrase (22 regexes, e.g. "follow me", "free followers", "crypto", "giveaway", "link in bio") → "promotional / scam phrase".
  2. Two or more URLs → "multiple links".
  3. One URL with 4 or fewer words of clean text → "link with little content".
  4. Six or more hashtags making up more than 50 % of the words → "hashtag stuffing".
  5. Text longer than 20 chars, more than 85 % upper-case letters, and a URL → "all caps with link".
  6. Empty clean text → "no textual content".
- **Outputs:** `is_spam`, `spam_reason`, stored on the mention.

#### FR-013 Sentiment model loading and readiness
**Status:** Implemented · **Code:** `nlp/sentiment.py` → `SentimentModel.load()`; `core.py` → `_load_model()`; `routes.py` → `_require_model()`

- **Description:** The system shall load the primary multilingual model in the background. If that fails it shall load the binary fallback model. Features that need inference shall be gated until a model is ready.
- **Processing:** Load every model in `SENTIMENT_MODEL` (default: `cardiffnlp/twitter-xlm-roberta-base-sentiment` and `cardiffnlp/twitter-roberta-base-sentiment-latest`, both BERT-family encoders fine-tuned on tweets) and average their 3-class probabilities. If none loads, try `FALLBACK_SENTIMENT_MODEL` in order: `tabularisai/multilingual-sentiment-analysis` (multilingual DistilBERT, 5 classes folded into 3), then `distilbert-base-uncased-finetuned-sst-2-english` (binary; neutral is synthesised as `max(0, 1 − |pos − neg| × 1.4)` and renormalised). The processor, collectors, simulator and analytics loops all wait for `model.ready`.
- **Outputs:** `/api/health.model_ready`, `/api/status.model` (`loading` | `ready` | `error: …`), `model_name`.
- **Errors:** If both models fail, `status.model = "error: …"`, the error is logged and the pipeline stays paused. Endpoints that need the model return **503** `The sentiment model is still loading, try again in a few seconds`. These are `/analyze`, `/data/reset`, `/system/evaluation/run`, `/youtube/channels`, `/youtube/channels/{id}/sync` and `/instagram/accounts/{id}/sync`.

#### FR-014 Hybrid sentiment classification
**Status:** Implemented · **Code:** `sentiment.py` → `predict()`, `_raw_predict()`, `_finalise()`, `lexicon_polarity()`

- **Description:** Each text shall be classified as positive, neutral or negative, with calibrated probabilities, a confidence value and a score.
- **Processing:**
  1. Cache lookup. The key is the text stripped and cut to 2000 chars. The cache is an LRU of 50,000 entries.
  2. Batched transformer inference: batch 32, truncation at 256 tokens.
  3. Regional lexicon polarity. 51 Hinglish/Hindi/Marathi terms are scored; a negator within ±2 words flips the sign; the result is averaged and clamped to [-1, 1]. On a hit, probabilities are blended `0.65 × model + 0.35 × lexicon target`.
  4. Neutral margin. If there was no lexicon hit and `top1 − top2 < 0.20` for a non-neutral top label, the label becomes `neutral`.
- **Outputs:** `{label, confidence, score = P(pos) − P(neg), probs{positive, neutral, negative}, lexicon_polarity}`, with values rounded to 4 decimals.
- **Validation:** Empty text gives a fixed neutral result (`confidence 1.0`, `score 0`) without calling the model.
- **Measured quality (`backend/data/evaluation.json`):** domain set (83): accuracy 0.8313, macro F1 0.8174. App Store star agreement: 385 of 483 reviews (79.7%). Real comments (200, random sample of the live database): accuracy 0.7400, macro F1 0.7276, against 0.665 for the previous DistilBERT model. These are the team's measured figures, not guarantees.

#### FR-015 Aspect-based sentiment analysis
**Status:** Implemented · **Code:** `nlp/aspects.py` → `AspectExtractor.extract_clauses()`, `analyze_batch()`, `split_clauses()`

- **Description:** The system shall detect which configured aspects a mention discusses and assign each aspect its own sentiment.
- **Inputs:** `model_text`, the overall sentiment, and the aspect lexicon from runtime config. The default lexicon has 8 aspects and 132 keywords.
- **Processing:**
  1. Split the text into clauses on `. ! ? ; newline` and the connectives *but, however, although, though, whereas, except, lekin, magar, par, pan*. Only clauses of 2 or more words are kept.
  2. Find aspects per clause. ASCII keywords use whole-word, case-insensitive matching, so "late" does not match "chocolate". Non-ASCII keywords use substring matching. If no clause matches, the whole text is tried.
  3. If the text has more than one distinct clause, or its single clause differs from the full text, classify the clauses in one batch. Otherwise reuse the overall sentiment.
  4. For each aspect, the score is the mean of its clause scores. The label is that of the clause with the largest |score|.
- **Outputs:** `[{aspect, sentiment, score, evidence (first clause, ≤160 chars)}]`.
- **Postconditions:** A change to the aspect lexicon takes effect immediately for new mentions, through `RuntimeConfig.subscribe`. Stored mentions are **not** re-analysed.
- **Measured quality:** aspect detection P 0.900 / R 0.730 / F1 0.806 on the domain set.

#### FR-016 Single-text analysis ("Analyze Text")
**Status:** Implemented · **Code:** `routes.py` → `analyze()`; UI `pages/Analyze.jsx`

- **Description:** A user shall be able to submit one text and see every pipeline step, optionally storing it as a mention.
- **Inputs:** `POST /analyze` `{text, store=false, source="manual", author?}`.
- **Processing:** preprocess → predict → aspects → clause map. Timing is measured from the start of inference. If `store = true`, the raw text goes through `Processor.process_batch` directly, bypassing the bus.
- **Outputs:** `{preprocessing, sentiment, aspects, clauses, model, processing_ms, stored_id}`. `stored_id` is a mention ID, `"duplicate"` if the same item already exists, or `null` if not stored.
- **Validation:** VR-001 to VR-004. The UI disables the button for blank text and limits input to 5000 chars.
- **Errors:** Model not ready → 503. Text empty or longer than 5000 chars → 422.

### 4.4 Mention Storage & Retrieval (M9, M10)

#### FR-017 Mention persistence
**Status:** Implemented · **Code:** `db.py` → `Database.insert_mentions()`, `SCHEMA`, `MIGRATIONS`

- **Description:** Every analysed, non-duplicate mention shall be stored with its raw text, cleaned text, lemmas, language, sentiment, probabilities, aspects, spam flag, engagement, origin and parent reference.
- **Processing:** `INSERT OR IGNORE` with `executemany`. The return value is the number of rows actually inserted, which feeds the `stored_total` and `duplicates_total` metrics. Two columns were added after release by migrations: `origin` (with a back-fill that marks old instagram/twitter/reddit/google_reviews rows as `simulated`) and `parent_id`.
- **Postconditions:** The data is durable across restarts, except on a Hugging Face Space without `/data` (FR deployment, Section 15).

#### FR-018 Mention search, filter, sort and paginate
**Status:** Implemented · **Code:** `routes.py` → `mentions()`; UI `pages/Mentions.jsx`, `MentionRow.jsx`

- **Description:** Users shall be able to browse stored mentions with combinable filters.
- **Inputs:** `GET /mentions` with `sentiment`, `source`, `aspect`, `language`, `spam`, `origin`, `parent_id`, `q`, `hours`, `sort`, `limit`, `offset`.
- **Processing:** A parameterised `WHERE` clause is built from fixed column names. The `aspect` filter does a `LIKE` match on the stored JSON (`"aspect": "<name>"`). `q` matches text or author with `LIKE %q%`. Sort options map to fixed `ORDER BY` clauses: newest, oldest, engagement, most_negative (score ascending).
- **Outputs:** `{total, items[]}`. Items are decoded (aspects and probs become JSON; `keywords` is removed).
- **Validation:** VR-040 to VR-048. The UI pages 30 mentions at a time (`PAGE`) and debounces search by 350 ms.

#### FR-019 Mention facets
**Status:** Implemented · **Code:** `routes.py` → `mention_facets()`

- **Description:** The system shall return the distinct values available for the mention filters.
- **Outputs:** `{sources: all distinct, languages: top 20 by count, aspects: configured aspect names}`.

### 4.5 Analytics (M7)

#### FR-020 Overview KPIs with period comparison
**Status:** Implemented · **Code:** `analytics/service.py` → `overview()`, `sentiment_counts()`; UI `pages/Dashboard.jsx`

- **Description:** For a chosen window of *h* hours, the system shall return sentiment KPIs and their change compared with the previous *h* hours.
- **Inputs:** `GET /overview?hours=h` (0 < h ≤ 2160, default 24).
- **Processing:**
  - Load 2*h* of data and split it at now − *h*.
  - Counts and percentages exclude spam. Health index = 50 + 50 × average score.
  - Deltas: total % change, positive/negative percentage-point change, health change, spam % change. A % change is `null` when the previous value is 0.
  - Also computed: sources, top 8 languages, aspect table with negative % change, open alert counts by severity, current risk, and the top 10 negative and positive keywords (generic words and brand words removed, words longer than 2 chars only).
- **Outputs:** `{window_hours, brand_name, generated_at, current, previous, deltas, sources, languages, aspects, risk, open_alerts, summary, negative_keywords, positive_keywords}`.
- **Validation:** `hours` outside the range → 422.

#### FR-021 Automatic text summary
**Status:** Implemented · **Code:** `service.py` → `build_summary()`

- **Description:** The overview shall include a rule-based English summary. It is template text; no generative model is involved.
- **Processing:**
  - Mood: "mostly positive" if positive ≥ 55 %, "mostly negative" if negative ≥ 45 %, otherwise "mixed".
  - Worst aspect: the one with the most negatives, among aspects with at least 3 negatives. A trend phrase is added if its change exceeds ±10 %.
  - Happiest aspect: the best average score among aspects with at least 3 positives.
  - Spam count, risk level with its top two drivers if high or critical, and the forecast direction (stable if the change is under 0.05).
- **Outputs:** `summary` string. With no data: "No mentions have been collected in this period yet. Enable a data source in Settings."

#### FR-022 Sentiment trends
**Status:** Implemented · **Code:** `service.py` → `trends()`, `_auto_bucket()`; `anomaly.py` → `bucketize()`

- **Description:** The system shall return a bucketed time series of mention counts by sentiment.
- **Inputs:** `GET /trends?hours=h&bucket_minutes=b`, with b optional and 5–1440.
- **Processing:** When b is omitted, the bucket is 15 min for h ≤ 6, 60 min for h ≤ 48, and 180 min otherwise. Empty buckets are kept as zeros. Each bucket is marked `anomaly` if the latest snapshot flagged a 15-min bucket inside it.
- **Outputs:** `{bucket_minutes, points[{t, total, positive, neutral, negative, spam, avg_score, neg_ratio, anomaly}]}`.

#### FR-023 Aspect insights and keywords
**Status:** Implemented · **Code:** `service.py` → `aspects()`, `aspect_table()`, `top_keywords()`; UI `pages/Aspects.jsx`

- **Description:** The system shall return per-aspect counts, the negative share, the average score and the values for the previous period.
- **Inputs:** `GET /aspects?hours=h`.
- **Outputs:** `{window_hours, aspects[{aspect, total, positive, neutral, negative, avg_score, negative_pct, previous_negative, previous_avg_score}], configured, negative_keywords(15), positive_keywords(15)}`. Aspects are sorted by total.

#### FR-024 Anomaly (crisis) detection
**Status:** Implemented · **Code:** `analytics/anomaly.py` → `detect_anomalies()`, `_robust_z()`; `service.py` → `compute_snapshot()`, `anomalies()`

- **Description:** The system shall flag 15-minute buckets in which negativity rises abnormally. A burst of praise is never flagged.
- **Inputs:** The last 72 h in 15-min buckets. Thresholds: `anomaly_contamination` (default 0.05), `z_threshold` (2.5), `min_negative_mentions` (5).
- **Processing:**
  1. Extrapolate counts in the bucket still in progress when 20–100 % of it has elapsed.
  2. Compute robust z-scores of the negative count (`neg_z`) and of the negative share (`ratio_z`). The share uses only buckets with 3 or more mentions. Both use the trailing median and MAD over 96 buckets, with at least 8 buckets required.
  3. Fit an Isolation Forest (200 trees, `random_state` 42) on {total, negative, neg_ratio, avg_score, neg_delta} once there are at least 24 non-empty buckets.
  4. `is_anomaly = negative ≥ min_neg AND ((IF outlier AND ratio_z ≥ z AND neg_z ≥ 0.6z) OR (ratio_z ≥ 1.6z AND neg_z ≥ z))`.
- **Outputs:** `GET /anomalies?hours=h` (0 < h ≤ 72, default 48) → `{bucket_minutes, points[{t, total, negative, neg_ratio, avg_score, anomaly_score, neg_z, ratio_z, is_anomaly}], incidents, computed_at}`.
- **Validation:** If no snapshot exists yet, empty `points` and `incidents` are returned.

#### FR-025 Incident summarisation
**Status:** Implemented · **Code:** `anomaly.py` → `summarise_anomalies()`

- **Description:** Consecutive anomalous buckets, meaning gaps of at most one bucket, shall be merged into incidents.
- **Outputs:** `{start, end (= last bucket + 15 min), negative, peak_neg_ratio, peak_score}`. These are exposed in `/anomalies` (filtered by window) and `/risk`.

#### FR-026 Sentiment forecasting
**Status:** Implemented · **Code:** `analytics/forecast.py` → `forecast()`, `_holt()`; `service.py` → `refresh_forecast()`; `routes.py` → `forecast()`

- **Description:** The system shall forecast the hourly sentiment index, the negative ratio and the volume for the next 12 hours.
- **Processing:**
  - Data: the last 7 days in hourly buckets. The current hour is dropped, leading empty hours are trimmed, and gaps are interpolated.
  - Fewer than 6 points → `insufficient_data`. Fewer than 36 points, or Prophet unavailable → Holt linear smoothing (α 0.5, β 0.2, an 80 % band of ±1.28σ√h). Otherwise Prophet: 80 % interval, `changepoint_prior_scale` 0.08, daily seasonality with 48 or more points, weekly seasonality with 14 days or more.
  - Clipping: sentiment to [-1, 1], ratio to [0, 1], volume ≥ 0.
- **Outputs:** `GET /forecast` → `{computed_at, horizon_hours, history(last 72 h), sentiment, negative_ratio, volume}`. Each forecast is `{method, points[{t, yhat, lower, upper}]}`. If nothing has been computed yet, the endpoint computes synchronously first.
- **Errors:** A Prophet failure logs a warning and falls back to Holt. An exception in the forecast loop is logged and the loop continues.

#### FR-027 Periodic analytics snapshot
**Status:** Implemented · **Code:** `core.py` → `_analytics_loop()`, `_forecast_loop()`; `service.py` → `compute_snapshot()`

- **Description:** Every 30 s (`ANALYTICS_INTERVAL_SECONDS`) the system shall recompute anomalies, risk, incidents, last-hour counts and last-hour aspects, evaluate the alert rules, and broadcast `risk`. Every 300 s (`FORECAST_REFRESH_SECONDS`) it shall refresh the forecast.
- **Preconditions:** Model ready, and no seeding in progress (both loops skip while seeding).
- **Errors:** An exception is logged ("Analytics tick failed" or "Forecast refresh failed") and the next tick runs normally.

#### FR-028 Brand risk score
**Status:** Implemented · **Code:** `analytics/risk.py` → `compute_risk()`, `risk_level()`; `routes.py` → `risk()`; UI `components/RiskGauge.jsx`

- **Description:** The system shall compute a 0–100 brand risk score from five signals, together with human-readable drivers.
- **Processing:** "Recent" means the last hour (4 buckets). The baseline is the preceding 96 buckets.

| Component | Max points | Formula | Driver text when |
|---|---|---|---|
| Negativity | 35 | `35 × clamp(0.55 × ratio/0.5 + 0.45 × clamp(lift/0.3))` | total ≥ 3 and lift > 0.08 |
| Velocity | 20 | `20 × clamp(max neg_z / 6)` | z ≥ 3 and negatives ≥ min_neg |
| Anomaly | 25 | `25 × clamp(0.5 + 0.5 × max anomaly_score)` if any anomaly | any anomaly in the last hour |
| Forecast | 10 | `10 × clamp(drop / 0.4)`, where drop = recent average score − minimum forecast over 6 h | drop > 0.15 |
| Concentration | 10 | `10 × clamp((top-aspect share − 0.3) / 0.5)`, if aspect negatives ≥ min_neg | share ≥ 0.5 |

  Score = `round(min(100, sum))`. Level: ≥ 75 critical, ≥ 55 high, ≥ 30 medium, otherwise low.
- **Outputs:** `GET /risk` → `{computed_at, score, level, components, drivers, recent_negative_ratio, baseline_negative_ratio, incidents}`. Before the first snapshot, the score is 0 and the level is low.

### 4.6 Alerts (M8)

#### FR-029 Snapshot alert rules
**Status:** Implemented · **Code:** `alerts/engine.py` → `AlertEngine.evaluate()`

- **Description:** After every analytics snapshot the system shall evaluate these rules:

| Rule (type) | Condition | Severity | Cool-down |
|---|---|---|---|
| `negative_spike` | Any anomaly in the last 4 buckets | critical if risk ≥ 75, otherwise high | `alert_cooldown_minutes` (30) |
| `risk_threshold` | risk ≥ `risk_alert` (60) | critical if ≥ 75, otherwise high | 30 |
| `negative_ratio` | last hour total ≥ 10, negatives ≥ min_neg, share ≥ `negative_ratio_alert` (0.35) | medium | 30 |
| `aspect_surge` (per aspect) | aspect negatives ≥ max(min_neg, 3) and negative share ≥ 50 % | high if negatives ≥ 2 × min_neg, otherwise medium | 30, keyed per aspect |
| `forecast_decline` | lowest `yhat` in the next 6 h < `forecast_score_floor` (0.0) | medium | 120 min (fixed) |
| `spam_wave` | last hour spam ≥ `spam_wave` (40) | low | 60 min (fixed) |

- **Outputs:** New rows in `alerts`, an `alert` WS event, and notifier delivery (FR-033).

#### FR-030 Viral negative mention rule
**Status:** Implemented · **Code:** `engine.py` → `check_mentions()`; called from `core.App._on_processed`

- **Description:** For each newly stored mention that is negative, not spam, and has engagement ≥ `viral_engagement` (500), the system shall raise a **high** alert, "Negative post is going viral". The alert includes the source, author and the first 180 chars of the text.
- **Notes:** Dedupe key `viral_negative:<mention_id>`, with cool-down 0. Because each mention is processed only once, this rule fires at most once per mention. Mentions stored with `broadcast = false` (history seeding) are not checked.

#### FR-031 Alert de-duplication (cool-down)
**Status:** Implemented · **Code:** `engine.py` → `raise_alert()`, `_recently_fired()`

- **Description:** An alert shall not be inserted if an alert with the same `dedupe_key` was created within its cool-down window. Cool-down 0 disables the check.
- **Note:** The cool-down applies regardless of alert status, so dismissing an alert does not let it fire again sooner.

#### FR-032 Alert listing and lifecycle
**Status:** Implemented · **Code:** `routes.py` → `list_alerts()`, `update_alert()`; `engine.py` → `list()`, `set_status()`; UI `pages/Alerts.jsx`

- **Description:** Users shall be able to list alerts and move them between `open`, `acknowledged` and `dismissed`.
- **Inputs:** `GET /alerts?status=&limit=` (limit 1–500, default 100); `POST /alerts/{id}/{acknowledge|dismiss|reopen}`.
- **Outputs:** `{items (newest first, meta decoded), open_counts{severity: n}}`; `{id, status}` plus an `alert_updated` WS event.
- **Errors:** Unknown ID → 404 `Alert not found`. Invalid action → 422.
- **Note:** Any transition is allowed, including dismissed → acknowledged. There is no transition history; only `updated_at` is recorded.

#### FR-033 Outbound alert notifications
**Status:** Implemented · **Code:** `alerts/notifiers.py` → `Notifier.send()`, `_email()`, `_slack()`, `_teams()`, `_sms()`, `channels_status()`

- **Description:** Each new alert whose severity is at least `notifications.min_severity` (default high) shall be delivered to every channel that is both enabled in runtime config and configured in `.env`.
- **Channels:** Email (SMTP + STARTTLS, 20 s timeout), Slack and Teams (incoming webhook POST, 15 s), SMS (Twilio REST, body cut to 320 chars, 15 s). The dashboard always receives the alert.
- **Outputs:** A per-channel result (`sent` or `error: …`), stored in `alert.meta.delivery`.
- **Errors:** A channel failure is logged as a warning and recorded. It does not block the other channels or the creation of the alert. There is no retry.

#### FR-034 Test notification
**Status:** Implemented · **Code:** `routes.py` → `test_alert()`; UI Settings → "Send test"

- **Description:** `POST /alerts/test` shall send a medium-severity test alert to every configured channel, ignoring the severity and enable flags (`force = true`), and broadcast it to the dashboard. The test alert is **not** stored (id 0).
- **Outputs:** `{delivery, channels}`.

### 4.7 Social Integrations (M4)

#### FR-035 Add a YouTube channel
**Status:** Implemented · **Code:** `routes.py` → `add_youtube_channel()`; `integrations/youtube.py` → `YouTubeService.resolve()`, `save_channel()`; UI `pages/YouTube.jsx`

- **Description:** A user shall be able to add a channel by @handle, URL, channel ID or name. The system then monitors the channel's recent uploads and their comments.
- **Preconditions:** YouTube API key configured. Model ready.
- **Inputs:** `POST /youtube/channels` `{query (2–120 chars), set_brand = true}`.
- **Processing:**
  1. Resolution order: channel ID regex `UC…22`, then `forHandle`, then `forUsername` for legacy URLs, then a name search costing 100 quota units.
  2. Upsert the channel and enable the `youtube` source.
  3. If `set_brand`, set the brand to the channel title and keywords to {title, @handle}.
  4. Run an immediate forced sync (FR-036).
- **Outputs:** `{channel, queued_comments}`.
- **Errors:** Resolution failure (not found, invalid key, quota, API not enabled) → 422 with the message. Sync failure → 502. Model not ready → 503.

#### FR-036 YouTube channel sync and polling
**Status:** Implemented · **Code:** `youtube.py` → `sync_channel()`, `_video_comments()`, `sync_all()`, `YouTubeChannelCollector`; `core.py` → `sync_youtube()`

- **Description:** The system shall refresh channel statistics, the most recent `YOUTUBE_MAX_VIDEOS` (default 5) uploads, and comments on those videos, fetching comments only for videos whose comment count changed.
- **Processing:** Fetch the uploads playlist, then video stats in chunks of 50. Re-read comments when `force` is set, when the video is new, or when `synced_comments ≠ commentCount`. Read up to 5 pages × 100 comment threads, including replies, at 2000 chars each, with `parent_id = video_id` and `origin = live`. Store `synced_comments = count` if comments were fetched, otherwise 0, so the next sync retries. Polling runs every 300 s while the source is enabled and at least one channel exists. Manual sync: `POST /youtube/channels/{id}/sync {force}`.
- **Errors:** Quota exceeded → "resets at 12:30 PM IST". Comments disabled → the video is stored with a comment count of 0. The error is saved to `youtube_channels.last_error`. Manual sync returns 404 if the channel is not found, otherwise 502.

#### FR-037 YouTube channel removal and video listing
**Status:** Implemented · **Code:** `routes.py` → `remove_youtube_channel()`, `youtube_videos()`, `youtube_status()`

- **Description:** Users shall be able to list channels with per-channel sentiment counts, list videos with per-video sentiment, and remove a channel, optionally deleting its comments.
- **Inputs:** `DELETE /youtube/channels/{id}?delete_data=bool`; `GET /youtube/videos?channel_id=&limit=` (1–200, default 60); `GET /youtube/status`.
- **Errors:** Unknown channel → 404.

#### FR-038 Instagram app credentials
**Status:** Implemented · **Code:** `routes.py` → `save_instagram_credentials()`; `config.py` → `write_env()`

- **Description:** The operator shall be able to save the Meta app ID and secret from the UI. They are written to `backend/.env` and applied without a restart.
- **Preconditions:** The request comes from the local machine (FR-045).
- **Inputs:** `POST /instagram/credentials` `{app_id, app_secret}` (VR-060, VR-061).
- **Outputs:** `{app_configured, saved_to, setup}`.
- **Errors:** Remote request → 403. Pattern or length violation → 422.

#### FR-039 Public HTTPS tunnel
**Status:** Implemented · **Code:** `integrations/tunnel.py` → `TunnelManager.start()`, `stop()`, `restore()`; `routes.py` → `instagram_tunnel()`; helper `backend/scripts/go_live.py` + `start-public.bat` (untracked)

- **Description:** The operator shall be able to start and stop a Cloudflare quick tunnel that gives the local server a public `https://*.trycloudflare.com` address. Meta requires an HTTPS address for the OAuth redirect.
- **Processing:** Download the platform's `cloudflared` binary to `backend/data/bin/` on first use. Start it detached. Read the URL from its log file within 75 s. Store `{url, pid}` in the settings table. Point `public_base_url` and `frontend_url` at the tunnel. On restart, re-adopt a still-running process. The tunnel is intentionally **not** stopped when the backend stops.
- **Outputs:** `{state (stopped | downloading | starting | running | error), url, local_url, error, binary_present, redirect_uri, setup}` and a `tunnel` WS event.
- **Errors:** Remote request → 403. Unsupported platform, download failure, process exit or 75 s timeout → `TunnelError` → 502. On macOS the user is told to `brew install cloudflared`.

#### FR-040 Instagram OAuth login
**Status:** Implemented · **Code:** `routes.py` → `instagram_login()`, `instagram_callback()`; `instagram.py` → `authorization_url()`, `consume_state()`, `complete_login()`

- **Description:** A user shall be able to connect an Instagram Business or Creator account through Instagram's own login page. BrandShield never sees the password.
- **Processing:**
  1. `GET /auth/instagram/login` creates a random `state` (valid for 600 s, single use) and redirects with HTTP 303 to `instagram.com/oauth/authorize`. Scopes: `instagram_business_basic`, `instagram_business_manage_comments`.
  2. The callback validates `state`.
  3. It exchanges the code for a short-lived token, then a long-lived 60-day token, and fetches the profile.
  4. It rejects account types other than BUSINESS, MEDIA_CREATOR or CREATOR.
  5. It upserts the account with a Fernet-encrypted token, enables the `instagram` source, and wakes the collectors.
- **Outputs:** A redirect to `<frontend>/instagram?connected=<username>`, or `?error=<message>`.
- **Errors (all reported by redirect, never as a raw error page):** user denied → "Instagram login was cancelled."; missing or expired state → "Login session expired or is invalid…"; no code; token exchange failure; personal account; network error → "Could not reach Instagram: <Type>". App not configured at login → redirect with an error.

#### FR-041 Instagram account sync and token refresh
**Status:** Implemented · **Code:** `instagram.py` → `sync_account()`, `_refresh_if_needed()`, `_paged()`, `sync_all()`, `InstagramCollector`; `core.py` → `sync_instagram()`

- **Description:** The system shall pull the account's recent media (up to `INSTAGRAM_MEDIA_LIMIT`, default 25) and the comments and replies on each, re-fetching only media whose comment count changed.
- **Processing:**
  - Refresh the token when 10 days or fewer remain and the last refresh was at least 24 h ago.
  - Up to 10 pages of 50 comments per media item.
  - Skip comments written by the account itself (the brand's own replies) and empty comments.
  - Store mentions with `parent_id = media_id` and `origin = live`.
  - Update the profile counters and `last_sync_at`.
  - Polling runs every 180 s while the source is enabled.
- **Inputs (manual):** `POST /instagram/accounts/{id}/sync {force}`.
- **Errors:** Token rejected (401/403/code 190) → "reconnect the account". Rate limit (code 4/32, or HTTP 429) → "will retry later". Undecryptable token, because the secret key changed → "Reconnect the account". Unknown account → 404. Other failures → 502. In `sync_all`, a failing account does not stop the others. An error is raised only if every account failed and nothing was collected.

#### FR-042 Instagram disconnect and media listing
**Status:** Implemented · **Code:** `routes.py` → `instagram_disconnect()`, `instagram_media()`, `instagram_status()`

- **Description:** Users shall be able to see connected accounts and per-post sentiment, and disconnect an account, optionally deleting its media and comments.
- **Inputs:** `DELETE /instagram/accounts/{id}?delete_data=bool`; `GET /instagram/media?ig_user_id=&limit=` (1–200).
- **Outputs:** Account rows **never include `access_token`** (`_public()`).
- **Errors:** Unknown account → 404.

#### FR-043 Switch to live data only
**Status:** Implemented · **Code:** `routes.py` → `use_live_only()`; `core.py` → `use_live_data_only()`

- **Description:** One action shall turn off the simulator, delete all simulated mentions and **all** alerts, and, if an Instagram account is connected, rename the brand after the first account.
- **Inputs:** `POST /data/use-live-only` `{confirm, rename_brand = true}`. The UI asks for confirmation first.
- **Processing:** Wait up to 5 s for the bus to drain, plus 1 s, so in-flight simulated items are not re-inserted. Then delete, recompute the forecast and snapshot, and broadcast `status` and `refresh`.
- **Outputs:** `{deleted_simulated, config}`.
- **Errors:** `confirm ≠ true` → 400.

### 4.8 Configuration & Administration (M2)

#### FR-044 Runtime settings management
**Status:** Partial (validation gaps, see VR-033 and VR-036) · **Code:** `runtime.py` → `RuntimeConfig.update()`, `reset()`, `_validate()`, `deep_merge()`; `routes.py` → `get_settings()`, `put_settings()`, `reset_settings()`; UI `pages/Settings.jsx`

- **Description:** Users shall be able to view and change the brand name, keywords, source toggles, simulator rate, aspect lexicon, alert thresholds and notification preferences. Changes take effect without a restart and persist in the DB.
- **Inputs:** `PUT /settings` with a partial JSON object (deep-merged; `aspects` is replaced as a whole); `POST /settings/reset`.
- **Processing:** Merge, validate, persist under `settings.runtime_config`, then notify subscribers (the aspect extractor). If `sources`, `keywords` or `brand_name` changed, wake the collectors. Broadcast `status`.
- **Outputs:** `{config}`. `GET /settings` also returns `channels` (configured notification channels) and `collectors` status.
- **Errors:** Body not JSON → 400 `Body must be JSON`. Body not an object → 400. A validation `ValueError`, `KeyError` or `TypeError` → 422 with the message.

#### FR-045 Local-only restriction of setup actions
**Status:** Implemented (see Appendix B, item 2 for its effect on server deployments) · **Code:** `routes.py` → `_setup_only()`

- **Description:** Saving Instagram credentials, saving API keys and starting or stopping the tunnel shall be allowed only when the client address is `127.0.0.1`, `::1` or `localhost` **and** the request carries no `X-Forwarded-For` or `CF-Connecting-IP` header.
- **Errors:** Otherwise → 403 `This action is only allowed from the computer running BrandShield AI`.

#### FR-046 API key management
**Status:** Implemented · **Code:** `routes.py` → `api_keys()`, `save_api_keys()`; UI Settings → "API keys" card, YouTube page key form

- **Description:** The system shall report which source keys are configured **without returning their values**, and shall let the local operator save new keys to `.env`, applied immediately.
- **Inputs:** `GET /keys`; `PUT /keys` `{youtube_api_key?, reddit_client_id?, reddit_client_secret?, twitter_bearer_token?, appstore_app_id?, appstore_country?}`.
- **Outputs:** `GET` → `{configured{name: bool}, appstore_app_id, appstore_country}`. `PUT` → `{saved[], collectors}`.
- **Errors:** No keys in the body → 400 `No keys given`. Remote request → 403. Pattern or length violation → 422 (VR-062 to VR-064).

#### FR-047 Data reset
**Status:** Implemented · **Code:** `routes.py` → `reset_data()`; `core.py` → `reset_data()`

- **Description:** Users shall be able to delete all mentions and alerts, optionally regenerating simulated history.
- **Inputs:** `POST /data/reset` `{confirm, reseed = true}`. The UI asks for confirmation.
- **Processing:** Delete from `mentions` and `alerts`, clear caches and the forecast, and stop any crisis. If `reseed`, seed `SEED_HISTORY_DAYS or 3` days (so `SEED_HISTORY_DAYS = 0` still seeds 3 days), otherwise recompute the snapshot and broadcast `refresh`.
- **Outputs:** `{seeded}`.
- **Errors:** `confirm ≠ true` → 400. Model not ready → 503.
- **Note:** Channels, accounts, settings and media rows are kept.

### 4.9 Real-Time Delivery, Monitoring & Evaluation (M5, M12)

#### FR-048 WebSocket live events
**Status:** Implemented · **Code:** `routes.py` → `websocket()`; `pipeline/hub.py` → `Hub.broadcast()`; UI `lib/live.jsx`

- **Description:** The system shall push live events to every connected dashboard.
- **Protocol:** `GET /ws` (upgrade). The server sends `{"type": "status", …}` on connect and replies `{"type": "pong"}` to the text `ping`. Event types: `status`, `metrics` (every 5 s while clients are connected), `risk`, `mentions` (up to 50 per batch), `alert`, `alert_updated`, `refresh`, `tunnel`, `evaluation`.
- **Client behaviour:** Ping every 25 s. Reconnect 2.5 s after a close.
- **Errors:** A client that fails a send or exceeds the 5 s send timeout is dropped from the hub.

#### FR-049 Health, status and pipeline metrics
**Status:** Implemented · **Code:** `routes.py` → `health()`, `status()`, `system_metrics()`; `pipeline/metrics.py` → `PipelineMetrics.snapshot()`; UI `pages/System.jsx`

- **Description:** The system shall expose liveness, overall status and pipeline performance.
- **Outputs:**
  - `/health` → `{status: "ok", model_ready, time}`.
  - `/status` → brand, model state, seeding, bus, sources, collectors, simulator/crisis, channels, tunnel, YouTube/Instagram summary, simulated count, stored count, WS clients, server time.
  - `/system/metrics` → uptime; ingested, processed, stored, duplicates, errors and batches totals; last error; throughput per second (60 s window); processed in the last minute; queue depth; latency avg/p50/p95/max over the last 2000 items (ingest → stored); processing ms per item; model name, readiness, average inference ms per text, texts inferred and load error; live agreement against `true_label` over the last 5000 non-spam labelled items; bus name.

#### FR-050 Model evaluation
**Status:** Implemented · **Code:** `backend/scripts/evaluate_model.py` → `evaluate_datasets()`, `main()`; `routes.py` → `evaluation()`, `run_evaluation()`, `evaluation_status()`

- **Description:** The system shall compute accuracy, macro and weighted precision/recall/F1, per-class metrics, the confusion matrix, inference ms per text and aspect-detection P/R/F1. It reports both the hybrid model and the model on its own (an ablation), plus up to 15 sample errors.
- **Inputs:**
  - CLI: `python -m scripts.evaluate_model [--datasets domain tweet_eval] [--limit N]`.
  - API: `POST /system/evaluation/run`, which runs the domain set only in the background.
  - Dataset: `backend/eval/domain_labeled.csv`, 83 rows with columns `text,label,aspects` (aspects separated by `|`).
- **Outputs:** `backend/data/evaluation.json`, which merges datasets across runs. `GET /system/evaluation` returns `{available: false}` or the file contents. `GET /system/evaluation/status` returns `{running, error}`. An `evaluation` WS event is sent when a run finishes.
- **Errors:** A run already in progress → 409. Model not ready → 503. An exception during the job is stored in `error` and broadcast.

### 4.10 Dashboard (M11)

#### FR-051 Dashboard pages
**Status:** Implemented · **Code:** `frontend/src/main.jsx`, `components/Layout.jsx`, `pages/*.jsx`

- **Description:** The SPA shall provide these routes, with a sidebar badge for open alerts:

| Route | Page | Main data |
|---|---|---|
| `/` | Dashboard | `/overview`, `/trends`, open alerts, latest 12 mentions, risk gauge, summary; window selector |
| `/youtube` | YouTube | key form, add channel, channels, videos, comments per video |
| `/instagram` | Instagram | guided setup (keys → tunnel → login), accounts, posts, comments per post, "use live data only" |
| `/mentions` | Mentions | filters in URL query parameters, search, pagination |
| `/analytics` | Trends & Forecast | anomalies, incidents, forecast, risk components |
| `/aspects` | Aspect Insights | aspect table and keywords |
| `/alerts` | Alerts | status filter, acknowledge/dismiss/reopen, browser-notification permission |
| `/analyze` | Analyze Text | single-text analysis, CSV upload |
| `/system` | Performance | live metrics, evaluation results, "run evaluation" |
| `/settings` | Settings | brand, keywords, sources, simulator rate, crisis simulation, API keys, thresholds, notifications, aspects, data reset |

- **Error display:** API errors are shown in the page (`ErrorBox` or inline). For FastAPI 422 arrays, the client formats the message as `field: msg; …` (`lib/api.js`).
- **Polling:** Pages refresh on intervals of 30–120 s in addition to WS events (`useApi`).

#### FR-052 Live UI updates and browser notifications
**Status:** Implemented · **Code:** `lib/live.jsx` → `LiveProvider`; `pages/Alerts.jsx`

- **Description:** The UI shall show a toast for every `alert` event (the last 4 are kept, each auto-dismissed after 9 s). If the user has granted Notification permission, it shall also show an OS notification for high and critical alerts.
- **Constraint:** Notifications appear only while a dashboard tab is open. There is no service worker or push subscription (README's "browser push" wording overstates this; see Appendix B).

#### FR-053 Static snapshot export
**Status:** Partial (untracked; no consumer in the frontend) · **Code:** `backend/scripts/export_static.py`

- **Description:** A script shall export the responses of a running server for a fixed list of dashboard API paths into `frontend/public/snapshot.json`, so the dashboard could run as a static site.
- **Gap:** `frontend/src/lib/api.js` has no static or snapshot mode, so the exported file is not used yet. Completing this is listed in Future Scope (FS-07).

---

## 5. Non-Functional Requirements

Performance requirements are in Section 13 (NFR-PERF-xx) and security requirements in Section 12 (NFR-SEC-xx). They are not repeated here. Every value below comes from the code or from a measurement the team recorded. Where we chose a value as a team rather than measuring it, the requirement says so.

### 5.1 Reliability

| ID | Requirement | Basis in code | Verification |
|---|---|---|---|
| NFR-REL-01 | If Kafka is configured but unreachable within 10 s, the system shall start on the in-memory bus instead of failing. | `bus.create_bus()` | Start with `BUS_BACKEND=kafka` and no broker; `/api/status.bus == "memory"` |
| NFR-REL-02 | An exception while processing a batch shall not stop the processor. The error shall be counted in `errors_total`. *Known limitation: the messages of the failed batch are discarded.* | `Processor.run()` | Fault injection (TC-12) |
| NFR-REL-03 | A failing collector shall not affect other collectors or the pipeline. Its error shall be visible in collector status, and the next poll shall retry. | `_collector_loop()` | Invalid Twitter token → `last_error` set, others keep running |
| NFR-REL-04 | If the primary sentiment model cannot be loaded, the system shall load the fallback model. | `SentimentModel.load()` | Set `SENTIMENT_MODEL` to an invalid name → `model_name` is the SST-2 model |
| NFR-REL-05 | If Prophet fails or the history is shorter than 36 h, forecasting shall fall back to Holt smoothing. With fewer than 6 hourly points, it shall report `insufficient_data` and not raise an error. | `forecast.forecast()` | TC-20 |
| NFR-REL-06 | Exceptions in background loops (analytics, forecast) shall be logged, and the loop shall continue on its next interval. Crashed tasks shall be logged with a traceback. | `core._spawn()`, loops | Code inspection, logs |
| NFR-REL-07 | The dashboard shall reconnect its WebSocket automatically 2.5 s after a disconnect. | `live.jsx` | Restart the backend while the UI is open |

### 5.2 Availability

| ID | Requirement | Basis | Verification |
|---|---|---|---|
| NFR-AV-01 | In the server deployment, the service shall be restarted by systemd 5 s after any exit and memory-capped at 3500 MB. | `deploy/brandshield.service` | `systemctl kill brandshield`, observe restart |
| NFR-AV-02 | Stored mentions, alerts, settings, accounts and channels shall survive a restart. Exception: a Hugging Face Space without `/data`, where data lives in `/tmp` and is reset. | SQLite file, `deploy/huggingface/start.sh` | Restart, compare counts |
| NFR-AV-03 | The REST API and dashboard shall be reachable while the model is loading. `/api/health` shall report `model_ready: false`, and model-dependent endpoints shall return 503. | lifespan starts the loader as a task | TC-02 |
| NFR-AV-04 | A running tunnel shall survive a backend restart and be re-adopted, so the Meta redirect URI stays valid. | `TunnelManager.restore()` | Restart with the tunnel running |

### 5.3 Scalability

| ID | Requirement / documented limit | Basis |
|---|---|---|
| NFR-SC-01 | The system is designed for **one brand per installation and one server process**. Horizontal scaling is not supported, because state is held in process memory and SQLite has a single writer. | `--workers 1`, `db.py` |
| NFR-SC-02 | The memory bus shall hold at most 50,000 pending messages. Producers wait when it is full (back-pressure, not data loss). | `MemoryBus(maxsize=50_000)` |
| NFR-SC-03 | All list endpoints shall be bounded: mentions ≤ 500 per page, alerts ≤ 500, media/videos ≤ 200, time windows ≤ 90 days (anomalies ≤ 72 h). | Query constraints in `routes.py` |
| NFR-SC-04 | The periodic analytics shall read a bounded window: 72 h for the snapshot and 7 days for the forecast, regardless of total DB size. | `compute_snapshot()`, `refresh_forecast()` |

### 5.4 Maintainability

| ID | Requirement | Basis |
|---|---|---|
| NFR-MA-01 | All SQL schema definitions and generic data access shall live in `db.py` and in the owning service classes. No SQL in the frontend, and none in collectors other than the YouTube/Instagram services. | Code structure |
| NFR-MA-02 | Schema changes shall be additive and applied automatically at start-up through the `MIGRATIONS` list (column + optional back-fill). | `Database._migrate()` |
| NFR-MA-03 | All static configuration shall be read from environment variables or `backend/.env` through one `Settings` class. Defaults are documented in `.env.example`. | `config.py` |
| NFR-MA-04 | The REST API shall be self-documented through OpenAPI at `/docs`. The two OAuth redirect routes are deliberately excluded. | FastAPI defaults |
| NFR-MA-05 | Python dependencies shall be pinned to exact versions. *Gap: `cryptography` is missing (Appendix B).* | `backend/requirements.txt` |

### 5.5 Usability

| ID | Requirement | Basis |
|---|---|---|
| NFR-US-01 | Connecting Instagram and YouTube shall be possible entirely from the UI (keys → tunnel → login, or key → channel), with no file editing and no restart. | `Instagram.jsx`, `YouTube.jsx`, FR-038/039/046 |
| NFR-US-02 | Errors from external services shall be translated into actionable messages. Examples: "YouTube's daily quota is used up. It resets at 12:30 PM IST.", "Only Instagram Business or Creator accounts can be connected…" | `YouTubeError`, `InstagramError` |
| NFR-US-03 | Every destructive UI action (data reset, live-only switch, disconnect, remove channel) shall require a browser `confirm()`. The matching APIs require `confirm: true` where applicable. | Settings/Instagram/YouTube pages |
| NFR-US-04 | The UI shall show the WebSocket connection state, model loading state and history-seeding progress. | `Layout.jsx`, `/api/status` |

### 5.6 Compatibility

| ID | Requirement |
|---|---|
| NFR-CO-01 | The backend shall run on Windows and on Linux (native or Docker). The tunnel binary is downloaded automatically for Windows/Linux on amd64/arm64. On macOS it must be installed with Homebrew. |
| NFR-CO-02 | The dashboard shall work in current Chromium, Firefox and Safari browsers that support ES modules and WebSocket (TBC: no formal cross-browser test record exists). |
| NFR-CO-03 | The NLP pipeline shall accept English, romanised Hindi/Marathi (Hinglish) and Devanagari Hindi/Marathi text. Other languages are processed by the multilingual model without lexicon support. |

### 5.7 Privacy

| ID | Requirement | Basis |
|---|---|---|
| NFR-PR-01 | Instagram access tokens shall be stored only in encrypted form and shall never appear in any API response. | `TokenCipher`, `InstagramService._public()` |
| NFR-PR-02 | API keys and secrets shall never be returned by the API. Only their presence (true/false) is reported. | `GET /api/keys` |
| NFR-PR-03 | The system shall never ask for or store Instagram passwords. Login happens on instagram.com. | FR-040 |
| NFR-PR-04 | For Instagram, only the connected account's own media and comments shall be collected. The account's own replies shall be excluded from analysis. | `sync_account()` |
| NFR-PR-05 | Removing a channel or disconnecting an account shall offer deletion of its collected comments. | FR-037, FR-042 |

### 5.8 Data Integrity

| ID | Requirement | Basis |
|---|---|---|
| NFR-DI-01 | A mention shall be identified deterministically by `sha1(source:external_id)[:24]`, and stored at most once. | FR-010 |
| NFR-DI-02 | All stored timestamps shall be UTC in the format `YYYY-MM-DDTHH:MM:SSZ`. | `db.to_iso()` |
| NFR-DI-03 | A `created_at` in the future shall be clamped to the ingestion time. An unparseable value shall be replaced with the ingestion time. | `normalise_raw()`, `parse_any_datetime()` |
| NFR-DI-04 | All database access shall be serialised through one re-entrant lock, with WAL journaling. | `Database` |
| NFR-DI-05 | Spam-flagged mentions shall be excluded consistently from sentiment counts, aspect tables, anomaly features, risk and every alert rule except spam-wave. | `sentiment_counts`, `aspect_table`, `bucketize`, rules |
| NFR-DI-06 | Runtime configuration shall be validated before it is persisted. *Partial: see VR-033 and VR-036.* | `RuntimeConfig._validate()` |

---

## 6. System Interfaces

### 6.1 User interface

A single-page React app with a dark theme, built with Vite and served from `/` by FastAPI. The ten pages are listed in FR-051. Common elements: a sidebar with an open-alert badge, a live/offline indicator, toasts for alerts, a time-window selector on the analytics pages, and in-page error boxes. Charts use Chart.js through react-chartjs-2. The layout is responsive, with a separate mobile navigation (`Layout.jsx` renders the nav twice).

### 6.2 REST API (base `/api`, JSON unless noted)

| Group | Method & path | Purpose | FR |
|---|---|---|---|
| Health | GET `/health`, GET `/status` | Liveness, overall status | FR-049 |
| Analytics | GET `/overview`, `/trends`, `/aspects`, `/anomalies`, `/forecast`, `/risk` | Aggregates | FR-020–028 |
| Mentions | GET `/mentions`, GET `/mentions/facets` | Browse | FR-018, 019 |
| NLP | POST `/analyze` | Single text | FR-016 |
| Ingest | POST `/ingest`, POST `/ingest/csv` (multipart) | External data | FR-007, 008 |
| Alerts | GET `/alerts`, POST `/alerts/{id}/{action}`, POST `/alerts/test` | Alert management | FR-032, 034 |
| Settings | GET/PUT `/settings`, POST `/settings/reset` | Runtime config | FR-044 |
| Simulator | POST `/simulator/crisis`, POST `/simulator/crisis/stop` | Demo | FR-002 |
| Collectors | POST `/collectors/poll` | Poll now | FR-006 |
| Data | POST `/data/reset`, POST `/data/use-live-only` | Admin | FR-047, 043 |
| System | GET `/system/metrics`, GET `/system/evaluation`, POST `/system/evaluation/run`, GET `/system/evaluation/status` | Monitoring | FR-049, 050 |
| Keys | GET/PUT `/keys` | Source keys | FR-046 |
| Instagram | POST `/instagram/credentials`, POST `/instagram/tunnel/{start\|stop}`, GET `/instagram/status`, GET `/instagram/media`, POST `/instagram/accounts/{id}/sync`, DELETE `/instagram/accounts/{id}` | Integration | FR-038–042 |
| OAuth (hidden) | GET `/auth/instagram/login`, GET `/auth/instagram/callback` | Redirects (303) | FR-040 |
| YouTube | GET `/youtube/status`, POST `/youtube/channels`, GET `/youtube/videos`, POST `/youtube/channels/{id}/sync`, DELETE `/youtube/channels/{id}` | Integration | FR-035–037 |
| WebSocket | `/ws` | Live events | FR-048 |

Error format: `{"detail": "<message>"}`, or for 422 schema errors `{"detail": [{loc, msg, type}, …]}`. Any non-API path returns the SPA's `index.html`. Unknown `/api/*` paths return 404 when the frontend build is present.

### 6.3 External services

| Service | Endpoint(s) used | Auth | Direction | Limits / notes |
|---|---|---|---|---|
| Hugging Face Hub | model download | none | in | ~1.6 GB, first start only |
| Google News RSS | `news.google.com/rss/search` | none | in | – |
| Reddit | `/api/v1/access_token`, `oauth.reddit.com/search` | client credentials | in | Unauthenticated access usually returns 403 |
| Twitter/X API v2 | `/2/tweets/search/recent` | Bearer token | in | Paid tier required |
| Apple | `itunes.apple.com/search`, `/rss/customerreviews` | none | in | Up to 3 pages × 50 reviews |
| YouTube Data API v3 | `channels`, `search`, `playlistItems`, `videos`, `commentThreads` | API key | in | 10,000 units/day; a name search costs 100 units |
| Instagram API with Instagram Login | `instagram.com/oauth/authorize`, `api.instagram.com/oauth/access_token`, `graph.instagram.com/{v23.0}/me`, `/me/media`, `/{media}/comments`, `/access_token`, `/refresh_access_token` | OAuth 2.0 | in | Business/Creator accounts only; app roles or App Review needed |
| Cloudflare | `cloudflared` quick tunnel; binary from GitHub releases | none | in/out | Random `*.trycloudflare.com` URL |
| SMTP server | configured host:port, STARTTLS | user/password | out | e.g. Gmail with an App Password |
| Slack / Teams | incoming webhook URL | URL secret | out | – |
| Twilio | `/2010-04-01/Accounts/{sid}/Messages.json` | SID/token | out | Body ≤ 320 chars |
| Apache Kafka | topic `brandshield.raw_mentions` | none (PLAINTEXT) | internal | Optional |

### 6.4 Database interface

SQLite 3 through Python's `sqlite3`, using a single connection (`check_same_thread=False`), `row_factory=Row`, `journal_mode=WAL` and `synchronous=NORMAL`. Callers use `query()`, `scalar()`, `execute()`, `insert_mentions()`, `existing_ids()`, `get_setting()` and `set_setting()`. Values are always passed as parameters. Only fixed column and sort names are interpolated into SQL text.

### 6.5 Hardware interfaces

None. The system needs a general-purpose CPU, 4 GB of RAM or more (server guide), and network access. No GPU, sensors or special devices are used.

---

## 7. Data Requirements

### 7.1 Entities and relationships

```
instagram_accounts 1 ──< instagram_media 1 ──< mentions (source='instagram', origin='live', parent_id = media.id)
youtube_channels   1 ──< youtube_videos  1 ──< mentions (source='youtube', parent_id = video.id)
mentions (other sources: parent_id NULL)
alerts       (meta.mention_id → mentions.id for viral_negative alerts; logical only)
settings     (key → JSON: 'runtime_config', 'tunnel')
```

All relationships are **logical**. No `FOREIGN KEY` constraints are declared. Referential clean-up is done in code (`disconnect()`, `remove_channel()`).

### 7.2 Data dictionary

**mentions** – one analysed mention

| Field | Type | Null | Description / constraint |
|---|---|---|---|
| id | TEXT PK | no | `sha1(source:external_id)[:24]` |
| source | TEXT | no | Lower-case source name |
| external_id | TEXT | yes | Platform ID, or a content hash |
| author | TEXT | yes | Display name or username |
| text | TEXT | no | Original text (non-empty) |
| clean_text | TEXT | yes | Cleaned text (FR-011) |
| keywords | TEXT | yes | Space-separated lemmas (internal; removed from API output) |
| url | TEXT | yes | Permalink |
| language | TEXT | yes | ISO 639-1 code from langdetect, or `unknown` |
| created_at | TEXT | no | UTC ISO; indexed |
| ingested_at | TEXT | no | UTC ISO |
| processed_at | TEXT | no | UTC ISO |
| sentiment | TEXT | no | positive \| neutral \| negative; indexed |
| confidence | REAL | no | 0–1 |
| score | REAL | no | -1 to 1 |
| probs | TEXT (JSON) | yes | `{positive, neutral, negative}` |
| aspects | TEXT (JSON) | yes | `[{aspect, sentiment, score, evidence}]` |
| is_spam | INTEGER | no | 0/1, default 0 |
| spam_reason | TEXT | yes | One of the FR-012 reasons |
| engagement | INTEGER | no | Default 0 |
| true_label | TEXT | yes | Ground truth (simulator / App Store stars) |
| origin | TEXT | no | live \| simulated, default `live`; indexed (migration) |
| parent_id | TEXT | yes | Media/video ID; indexed (migration) |

**alerts**: `id` INTEGER PK AUTOINCREMENT; `created_at` TEXT not null (indexed); `severity` (low\|medium\|high\|critical); `type` (negative_spike\|risk_threshold\|negative_ratio\|aspect_surge\|forecast_decline\|spam_wave\|viral_negative); `dedupe_key`; `title`; `message`; `meta` JSON (includes `delivery`); `status` (open\|acknowledged\|dismissed, default open); `updated_at`.

**settings**: `key` TEXT PK, `value` TEXT (JSON).

**instagram_accounts**: `ig_user_id` PK, `username` not null, `name`, `account_type`, `profile_picture_url`, `followers_count`, `follows_count`, `media_count`, `access_token` not null (**Fernet-encrypted**), `token_expires_at`, `token_refreshed_at`, `connected_at` not null, `last_sync_at`, `last_error`.

**instagram_media**: `id` PK, `ig_user_id` not null, `caption`, `media_type`, `media_url`, `thumbnail_url`, `permalink`, `timestamp`, `like_count`, `comments_count`, `synced_comments`, `updated_at`. Index `(ig_user_id, timestamp)`.

**youtube_channels**: `channel_id` PK, `handle`, `title`, `description` (≤ 800 chars), `thumbnail_url`, `country`, `published_at`, `subscriber_count`, `video_count`, `view_count`, `uploads_playlist`, `added_at` not null, `last_sync_at`, `last_error`.

**youtube_videos**: `id` PK, `channel_id` not null, `title`, `description` (≤ 500 chars), `thumbnail_url`, `published_at`, `view_count`, `like_count`, `comment_count`, `synced_comments`, `updated_at`. Index `(channel_id, published_at)`.

### 7.3 Runtime configuration object (`settings.runtime_config`)

```json
{
  "brand_name": "Saffron Cafe",
  "keywords": ["Saffron Cafe", "SaffronCafe", "saffron_cafe"],
  "sources": {"simulator": true, "reddit": false, "rss": false, "twitter": false,
              "youtube": false, "appstore": false, "instagram": false},
  "simulator_rate_per_min": 8.0,
  "aspects": {"food_quality": ["food", "taste", "..."], "service": ["..."], "...": []},
  "thresholds": {"risk_alert": 60, "negative_ratio_alert": 0.35, "min_negative_mentions": 5,
                 "anomaly_contamination": 0.05, "z_threshold": 2.5, "viral_engagement": 500,
                 "spam_wave": 40, "alert_cooldown_minutes": 30, "forecast_score_floor": 0.0},
  "notifications": {"email": false, "slack": false, "teams": false, "sms": false, "min_severity": "high"}
}
```

### 7.4 Files

| File | Content | Sensitivity |
|---|---|---|
| `backend/.env` | Static settings and API keys (plain text) | **Secret**. Written by `write_env()`; `chmod 600` on the server installer |
| `backend/data/brandshield.db` (+ `-wal`, `-shm`) | All data | Contains collected public comments |
| `backend/data/secret.key` | Fernet key (if `SECRET_KEY` is unset) | **Secret**. Losing it makes stored tokens unreadable |
| `backend/data/evaluation.json` | Evaluation results | – |
| `backend/data/bin/` | `cloudflared` binary, `tunnel.log` | – |
| `backend/eval/domain_labeled.csv` | 83 labelled comments (`text,label,aspects`) | – |

### 7.5 Input/output formats

- **Input:** JSON bodies (FR-007, FR-016, FR-044), multipart CSV (FR-008), query strings, OAuth query parameters.
- **Output:** JSON. Timestamps are UTC ISO-8601 with a `Z` suffix. Percentages are 0–100 with one decimal place. Ratios are 0–1 with four decimal places.
- **WebSocket:** `{"type": "<event>", "data": <payload>}`.

### 7.6 Data retention

- **Implemented:** none automatic. Mentions and alerts are kept indefinitely until a data reset (FR-047), a live-only switch (FR-043), or deletion on disconnect/removal.
- The analytics read only the most recent 72 h (snapshot) or 7 days (forecast), and the API windows are capped at 90 days, so older rows are stored but not shown in aggregates.
- An automatic retention or purge policy is listed in Future Scope (FS-09).

---

## 8. Detailed Validation Requirements

**Layer codes:** UI = React page · API = FastAPI/Pydantic (automatic 422) · BL = backend business logic · DB = SQLite · ML = NLP/analytics processing. Rows marked **Gap** describe current behaviour that a reviewer should treat as a known weakness (see FS-03).

### 8.1 Analyze Text – `POST /api/analyze`

| ID | Input | Type / format | Req. | Rule | Layer | Invalid-input response | Valid example | Invalid example |
|---|---|---|---|---|---|---|---|---|
| VR-001 | `text` | string | Yes | 1–5000 chars | UI (maxLength 5000; button disabled when blank), API | 422 `string_too_short` / `string_too_long` | `"Delivery was 40 min late but coffee was great"` | `""`, 5001-char string |
| VR-002 | `store` | boolean | No (false) | JSON boolean | API | 422 `bool_parsing` | `true` | `"maybe"` |
| VR-003 | `source` | string | No (`manual`) | **Gap:** no length or charset limit | API | – | `"manual"` | (any string accepted) |
| VR-004 | `author` | string \| null | No | No limit | API | – | `"priya_07"` | – |

### 8.2 Bulk ingest – `POST /api/ingest`

| ID | Input | Type | Req. | Rule | Layer | Invalid response | Valid | Invalid |
|---|---|---|---|---|---|---|---|---|
| VR-010 | `items` | array | Yes | 1–5000 elements | API | 422 `too_short`/`too_long` | `[{"text":"Love it"}]` | `[]` |
| VR-011 | `items[].text` | string | Yes | 1–5000 chars. Whitespace-only text passes the API but is dropped by BL (VR-070). | API, BL | 422 | `"Great service"` | `""` |
| VR-012 | `items[].engagement` | int | No (0) | Integer. **Gap:** negative values are accepted. | API | 422 if not an integer | `120` | `"lots"` (422); `-5` (accepted) |
| VR-013 | `items[].created_at` | string | No | ISO-8601, `YYYY-MM-DD HH:MM`, `DD-MM-YYYY HH:MM`, `DD/MM/YYYY HH:MM`, `YYYY-MM-DD`. No zone → server local time. | BL | **Silently replaced with now** (no error) | `"2025-09-01T10:30:00Z"` | `"yesterday"` → now |
| VR-014 | `items[].created_at` (future) | datetime | – | Must not be later than now | BL | Clamped to now | – | `"2030-01-01T00:00:00Z"` |
| VR-015 | `items[].source` / `external_id` / `url` / `author` | string | No | `source` is lower-cased, default `api`. No length limits. | BL | – | `"Twitter"` → `twitter` | – |

### 8.3 CSV upload – `POST /api/ingest/csv`

| ID | Input | Rule | Layer | Invalid response | Valid | Invalid |
|---|---|---|---|---|---|---|
| VR-020 | file size | ≤ 20 MB (checked after the file is read) | API/BL | 413 `CSV must be smaller than 20 MB` | 2 MB file | 25 MB file |
| VR-021 | encoding | UTF-8 (BOM allowed) | BL | 400 `CSV must be UTF-8 encoded` | UTF-8 export | UTF-16 file |
| VR-022 | header | Contains `text`, `comment`, `content` or `message` (case-insensitive, trimmed) | BL | 400 `CSV needs a 'text' or 'comment' column` | `Comment,Timestamp` | `body,date` |
| VR-023 | row text | Non-blank after trim | BL | Row skipped silently | `"Too salty"` | `"   "` |
| VR-024 | `engagement` cell | Non-negative decimal (`12`, `12.0`) | BL | Treated as 0 | `"35"` | `"1e3"`, `"-4"`, `"n/a"` → 0 |
| VR-025 | row count | At most 50,000 rows queued | BL | Further rows ignored (no error); `queued` = 50000 | 10k rows | 60k rows → 50k queued |
| VR-026 | timestamp cell | Same parser as VR-013 | BL | Replaced with now | `01/09/2025 10:30` | `soon` |
| (UI) | file picker | `accept=".csv,text/csv"` | UI | Other types hidden by the picker | – | – |

### 8.4 Runtime settings – `PUT /api/settings`

| ID | Field | Rule | Layer | Invalid response | Valid | Invalid |
|---|---|---|---|---|---|---|
| VR-038 | body | JSON object | API/BL | 400 `Body must be JSON` / `Body must be a JSON object` | `{"brand_name":"Blue Tokai"}` | `[1,2]`, `not json` |
| VR-031 | `brand_name` | Non-empty after trim | BL | 422 `brand_name cannot be empty` | `"Blue Tokai"` | `"  "` |
| VR-030 | `simulator_rate_per_min` | Number, 0.5–600 | UI (min/max), BL | 422 `simulator_rate_per_min must be between 0.5 and 600` | `8` | `0.1`, `1000` |
| VR-032 | `aspects` | Object of name → list. Names are lower-cased, trimmed, spaces → `_`. Blank names and words are removed. Replaces the whole lexicon. | BL | 422 `aspects must be an object of aspect -> keyword list` | `{"parking":["parking","valet"]}` | `["parking"]` |
| VR-033 | `keywords` | List of strings, blanks removed. **Gap:** a plain string is iterated character by character (`"abc"` → `["a","b","c"]`, observed). | BL | – | `["Blue Tokai","@bluetokai"]` | `"Blue Tokai"` (accepted, wrong) |
| VR-034 | `thresholds.anomaly_contamination` | 0 < x ≤ 0.5 | BL | 422 `anomaly_contamination must be in (0, 0.5]` | `0.05` | `0.9` |
| VR-035 | `thresholds.risk_alert` | 0–100 | BL | 422 `risk_alert must be between 0 and 100` | `60` | `150` |
| VR-036 | other thresholds (`negative_ratio_alert`, `min_negative_mentions`, `z_threshold`, `viral_engagement`, `spam_wave`, `alert_cooldown_minutes`, `forecast_score_floor`) | **Gap:** no range check. Negative cooldowns and ratios > 1 are accepted (observed). A non-numeric value surfaces later as an analytics error. | UI (number inputs only) | – | `0.35` | `-5`, `7` (accepted) |
| VR-037 | `notifications.min_severity` | One of low, medium, high, critical | UI (select), BL | 422 `min_severity must be one of [...]` | `"high"` | `"urgent"` |
| (BL) | `thresholds` not an object | – | BL | 422 (`TypeError` message, e.g. `'int' object is not subscriptable`) | – | `{"thresholds":5}` |

### 8.5 Crisis simulation – `POST /api/simulator/crisis`

| ID | Field | Rule | Layer | Invalid response | Valid | Invalid |
|---|---|---|---|---|---|---|
| VR-050 | `aspect` | One of the 8 simulator aspects | UI (select), BL | 422 `aspect must be one of [...]` | `"delivery"` | `"parking"` |
| VR-051 | `minutes` | Integer 1–240 | UI (min 1, max 240), API | 422 | `20` | `0`, `300` |
| VR-052 | `intensity` | 0.1–1.0 | UI (range slider), API | 422 | `0.8` | `1.5` |
| – | simulator state | Source must be enabled | UI (button disabled), BL | 409 `Enable the simulator source first` | – | – |

### 8.6 Query parameters

| ID | Parameter (endpoints) | Rule | Invalid response | Valid | Invalid |
|---|---|---|---|---|---|
| VR-040 | `hours` (`/overview`, `/trends`, `/aspects`, `/mentions`) | float, 0 < h ≤ 2160 | 422 | `24` | `0`, `3000` |
| VR-041 | `hours` (`/anomalies`) | 0 < h ≤ 72 | 422 | `48` | `100` |
| VR-042 | `bucket_minutes` (`/trends`) | int 5–1440, optional | 422 | `60` | `2` |
| VR-043 | `sentiment` (`/mentions`) | positive \| neutral \| negative | 422 | `negative` | `bad` |
| VR-044 | `origin` (`/mentions`) | live \| simulated | 422 | `live` | `real` |
| VR-045 | `sort` (`/mentions`) | newest \| oldest \| engagement \| most_negative | 422 | `engagement` | `random` |
| VR-046 | `limit` / `offset` (`/mentions`) | limit 1–500 (default 50); offset ≥ 0 | 422 | `limit=30&offset=60` | `limit=1000` |
| VR-047 | `q` / `parent_id` (`/mentions`) | q ≤ 200 chars; parent_id ≤ 64 chars; `spam` boolean | 422 | `q=late` | 201-char q |
| VR-048 | `/alerts`: `status`, `limit`; `/alerts/{id}/{action}` | status ∈ open\|acknowledged\|dismissed; limit 1–500; id integer; action ∈ acknowledge\|dismiss\|reopen | 422; unknown id → 404 | `POST /alerts/12/acknowledge` | `POST /alerts/abc/close` |

### 8.7 Integrations and administration

| ID | Input | Rule | Layer | Invalid response | Valid | Invalid |
|---|---|---|---|---|---|---|
| VR-060 | `app_id` (`/instagram/credentials`) | 3–64 chars, `^[0-9A-Za-z._-]+$` | UI (button disabled until filled), API | 422 | `"1234567890123456"` | `"12"`, `"abc def"` |
| VR-061 | `app_secret` | 8–128 chars, same charset | UI, API | 422 | `"a1b2c3d4e5f6"` | `"short"` |
| VR-062 | `youtube_api_key`, `reddit_client_id/secret` | ≤ 200 chars; `twitter_bearer_token` ≤ 500 | API | 422 | `"AIza…"` | 201-char key |
| VR-063 | `appstore_app_id` | Digits only, ≤ 40 | API | 422 | `"310633997"` | `"id3106"` |
| VR-064 | `appstore_country` | Letters only, ≤ 2 | API | 422 | `"in"` | `"ind"`, `"1n"` |
| VR-065 | `query` (`/youtube/channels`) | 2–120 chars. Then resolved as ID → handle → username → name search | UI (disabled when blank), API, BL | 422 (length) or 422 with the resolver message | `"@mkbhd"`, `"https://youtube.com/@mkbhd"` | `"a"`; `"@no_such_channel_xyz"` → 422 "No YouTube channel found…" |
| VR-066 | OAuth `state` | Must exist, be unused and be < 600 s old | BL | Redirect `?error=Login session expired or is invalid…` | issued state | replayed/expired state |
| VR-067 | Instagram `account_type` | BUSINESS, MEDIA_CREATOR or CREATOR (an empty type is not rejected) | BL | Redirect with "Only Instagram Business or Creator accounts…" | `BUSINESS` | `PERSONAL` |
| VR-068 | `limit` (`/instagram/media`, `/youtube/videos`) | 1–200 | API | 422 | `60` | `500` |
| VR-069 | `confirm` (`/data/reset`, `/data/use-live-only`) | Must be `true` | UI (`confirm()` dialog), BL | 400 `Set confirm=true …` | `{"confirm":true}` | `{}` |
| – | origin of request for setup endpoints | Loopback address, no forwarding headers (FR-045) | BL | 403 | request from `127.0.0.1` | request via the tunnel |

### 8.8 ML / data-processing level

| ID | Rule | Where | Effect on invalid/edge data |
|---|---|---|---|
| VR-070 | Messages with empty or whitespace-only `text` are dropped before NLP | `process_batch()`, `_collector_loop()` | Not stored, not counted as stored |
| VR-071 | Spam (FR-012) is stored but excluded from metrics and alerts | analytics, alerts | – |
| VR-072 | Model input is truncated to 256 tokens | `_raw_predict()` | Long texts are classified on their first 256 tokens |
| VR-073 | The sentiment cache key is the text cut to 2000 chars | `predict()` | Texts identical in the first 2000 chars share a result |
| VR-074 | Isolation Forest runs only with ≥ 24 non-empty buckets | `detect_anomalies()` | Below that, only the z-score path can flag anomalies |
| VR-075 | Robust z needs ≥ 8 baseline buckets. The MAD scale is floored at 0.5 for counts and 0.05 for ratios. | `_robust_z()` | z = 0 until there is enough history |
| VR-076 | The negative-ratio z-score uses only buckets with ≥ 3 mentions (forward-filled) | `detect_anomalies()` | Noise from tiny buckets is suppressed |
| VR-077 | Forecast: < 6 points → `insufficient_data`; < 36 → Holt | `forecast()` | No exception |
| VR-078 | Forecast outputs are clipped: sentiment [-1, 1], ratio [0, 1], volume ≥ 0 | `forecast()` | – |
| VR-079 | Collector texts are truncated to 2000 chars (Reddit, News, YouTube, App Store). Instagram comments and API/CSV text are not truncated beyond their own limits. | collectors | – |

### 8.9 Database level

| ID | Rule | Effect |
|---|---|---|
| VR-080 | NOT NULL on `mentions.source, text, created_at, ingested_at, processed_at, sentiment, confidence, score, is_spam, engagement, origin`, and on the required columns of the other tables | Insert fails. This cannot normally happen because BL fills every field. |
| VR-081 | PRIMARY KEY on every table. Mentions use `INSERT OR IGNORE`; accounts, channels, media and videos use upserts. | Duplicates are ignored or updated, never doubled |
| VR-082 | **Gap:** no FOREIGN KEY or CHECK constraints (e.g. on `sentiment` or `status` values) | Integrity relies on application code |
| VR-083 | `settings.key` is unique and written with an upsert | Last write wins |

### 8.10 UI level (summary)

| ID | Page | Rule |
|---|---|---|
| VR-090 | Analyze | Textarea maxLength 5000. Analyze button disabled while busy or when the text is blank. |
| VR-091 | Analyze | CSV picker accepts `.csv,text/csv` |
| VR-092 | Settings | Crisis minutes `min=1 max=240`; intensity slider 0.1–1 step 0.1 |
| VR-093 | Settings | Simulator rate `min=0.5 max=600 step=0.5` |
| VR-094 | Instagram | "Save keys" disabled until both app ID and secret are non-blank |
| VR-095 | YouTube | "Add" disabled for a blank query. The key form is disabled for a blank key. |
| VR-096 | Settings/Instagram/YouTube | `confirm()` before reset, live-only, disconnect, remove |
| VR-097 | Settings | Threshold inputs are `type=number` with a step but **no min/max** (Gap; backend gap VR-036 applies) |

**Total validation rules: 70** (VR-001–004, 010–015, 020–026, 030–038, 040–048, 050–052, 060–069, 070–079, 080–083, 090–097).

---

## 9. Error Handling Requirements

| ID | Failure case | Detected in | Required behaviour | What the user sees |
|---|---|---|---|---|
| EH-01 | Invalid input / schema violation | FastAPI/Pydantic | Reject with 422 before any processing | Inline message formatted as `field: msg` (`lib/api.js`) |
| EH-02 | Missing required field or confirmation | Pydantic / route | 422 for missing fields. 400 for `confirm ≠ true`, an empty key set, or a non-JSON settings body. | Inline error |
| EH-03 | Authentication failure (no app login exists) | – | Not applicable inside the app. Server deployment: Caddy basic-auth returns 401 before the app is reached. | Browser auth prompt |
| EH-04 | Authorization failure on setup endpoints | `_setup_only()` | 403 with an explanation. No state change. | "This action is only allowed from the computer running BrandShield AI" |
| EH-05 | External API failure (HTTP error, quota, rate limit, bad key) | Collectors, YouTube/Instagram services | Collector loop: store `last_error`, keep polling. Manual action: 422 (YouTube resolve) or 502 (sync), with a translated message. Save the account/channel `last_error`. | Error on the source card or in the Settings collector list |
| EH-06 | Expired or revoked Instagram token | `InstagramService._get()` | Record `last_error` "reconnect the account". Other accounts continue. | Error on the account card |
| EH-07 | OAuth failure (denied, bad state, exchange failure, personal account, network) | `instagram_callback()` | Always 303-redirect to `/instagram?error=…`. Never show a raw stack trace. | Error banner on the Instagram page |
| EH-08 | Database failure (locked, disk full, corrupt) | `sqlite3` exceptions | Request: FastAPI returns 500. Processor: the batch is lost and counted in `errors_total`. Loops: logged and retried next tick. **No retry/queue for failed writes (TBC under real disk-full conditions).** | Generic "Request failed (500)" |
| EH-09 | Model load failure | `_load_model()` | Try the fallback model. If both fail, `status.model = "error: …"`, inference endpoints return 503, and the pipeline waits. | Model status on the Performance page; 503 message |
| EH-10 | Model not yet ready | `_require_model()` | 503 "The sentiment model is still loading…". Bus items are kept until the model is ready. | Inline error |
| EH-11 | Empty or invalid data | Processor, analytics | Empty text dropped. Unparseable timestamps → now. Empty windows return zero counts, a `null` health index, and the summary "No mentions have been collected…". Forecast `insufficient_data`. | Empty-state messages |
| EH-12 | Network failure: Kafka down at start | `create_bus()` | Fall back to the memory bus (warning logged) | Bus shown as "memory" |
| EH-13 | Network failure: dashboard ↔ backend | `live.jsx`, `useApi` | WS reconnect every 2.5 s. REST errors keep the last data and show an error. | Offline indicator |
| EH-14 | Notification channel failure | `Notifier.send()` | Log a warning, record `error: …` in `alert.meta.delivery`, continue with the other channels. The alert is still stored and broadcast. | Delivery result in the alert meta / test-send message |
| EH-15 | Tunnel failure | `TunnelManager` | State `error` with a message. The API returns 502. Running accounts are unaffected. | Error on the Instagram page |
| EH-16 | Unexpected server error in a request | FastAPI | Default 500 response; traceback in the server log | "Request failed (500)" |
| EH-17 | Background task crash | `_spawn()` done-callback | Logged with a traceback. **The task is not restarted automatically (TBC whether any loop can exit; all loops catch their own exceptions).** | – |
| EH-18 | Concurrent evaluation run | `run_evaluation()` | 409 "An evaluation is already running" | Inline error |
| EH-19 | Encryption key changed | `TokenCipher.decrypt()` | `InstagramError` "Stored token cannot be decrypted… Reconnect the account." | Account error |

---

## 10. Use Cases

### UC-01 Monitor brand health
- **Actor:** Brand analyst · **Goal:** Understand the current sentiment and risk at a glance.
- **Preconditions:** Server running, model ready, at least one source producing data.
- **Main flow:** 1. The analyst opens `/`. 2. The system loads `/overview?hours=24`, `/trends`, open alerts and the latest mentions. 3. The system shows the KPIs, deltas, summary, sentiment chart, risk gauge, aspects and live feed. 4. New mentions and risk updates arrive over WS without a reload.
- **Alternative flow:** 2a. The analyst picks another window (e.g. 6 h or 7 d). The system re-queries with the new `hours` and an automatic bucket size.
- **Exception flow:** 2b. The model is still loading or seeding is in progress. Progress is shown and the KPIs may be empty. 4a. The WS drops. The indicator shows offline, and the UI reconnects and keeps polling over REST.
- **Postconditions:** None. This is a read-only use case.

### UC-02 Investigate mentions
- **Actor:** Brand analyst · **Goal:** Find the mentions behind a spike or complaint.
- **Preconditions:** Mentions stored.
- **Main flow:** 1. Open Mentions, or click through from an aspect or chart. 2. Set filters (sentiment = negative, aspect = delivery, last 6 h) and a sort order. 3. The system returns a page of 30 mentions with the total count. 4. The analyst expands a mention to see its probabilities, aspects and spam reason, and opens the original via its URL.
- **Alternative flow:** 2a. Free-text search (debounced 350 ms) matches text or author.
- **Exception flow:** 2b. An invalid parameter (e.g. a hand-edited URL with `sort=random`) gives a 422 message.
- **Postconditions:** None.

### UC-03 Analyse a single comment
- **Actor:** Analyst or evaluator · **Goal:** See how the pipeline handles one text.
- **Preconditions:** Model ready.
- **Main flow:** 1. Open Analyze Text and paste a comment, e.g. "khana mast tha but delivery bahut late". 2. Submit. 3. The system shows the cleaning, tokens, lemmas, language, spam check, probabilities, label and per-aspect sentiment with evidence clauses, plus the processing time.
- **Alternative flow:** 1a. Tick "store". The mention is saved and its `stored_id` (or "duplicate") is returned.
- **Exception flow:** 2a. The model is loading → 503 message. 2b. Text over 5000 chars is blocked by the textarea (API 422 otherwise).
- **Postconditions:** If stored, the mention appears in the feed and analytics.

### UC-04 Import historical comments from CSV
- **Actor:** Analyst · **Goal:** Analyse an exported comment file.
- **Preconditions:** A UTF-8 CSV under 20 MB with a text-like column.
- **Main flow:** 1. Analyze Text → upload the CSV. 2. The system validates the size, encoding and header. 3. Non-blank rows are queued (at most 50,000). 4. The system reports "Queued N rows…". 5. The processor analyses the rows in the background, and they appear in the dashboards using their own timestamps.
- **Alternative flow:** 3a. Rows without a timestamp column get the current time.
- **Exception flow:** 2a. Wrong encoding → 400. 2b. No text column → 400. 2c. Too large → 413.
- **Postconditions:** New mentions are stored. Rows already imported are ignored as duplicates, because their ID is derived from text, author and timestamp.

### UC-05 Push mentions from an external system
- **Actor:** External system · **Goal:** Feed mentions from a platform BrandShield does not collect itself.
- **Preconditions:** Network access to `/api/ingest`. No authentication is required (see SEC-01).
- **Main flow:** 1. The client POSTs `{items: [...]}`. 2. The system validates and queues the items and returns `{queued, bus}`. 3. The items are analysed asynchronously.
- **Exception flow:** 2a. Schema error → 422 and nothing is queued. 2b. Memory bus full → the request waits.
- **Postconditions:** The mentions are stored with the supplied `source`.

### UC-06 Demonstrate crisis detection
- **Actor:** Evaluator/presenter · **Goal:** Show that a complaint spike is detected and alerted.
- **Preconditions:** Simulator enabled, with roughly a day or more of history so that the Isolation Forest has ≥ 24 active buckets.
- **Main flow:** 1. Settings → Crisis simulation → aspect "delivery", 20 min, intensity 0.8 → Start. 2. The volume and the negative share rise. 3. Within the next analytics ticks, the risk score rises and `negative_spike`, `aspect_surge` and possibly `risk_threshold` alerts appear as toasts. 4. Trends & Forecast marks the anomalous buckets and lists the incident.
- **Alternative flow:** 1a. Stop the crisis early.
- **Exception flow:** 1b. Simulator disabled → 409 (the button is disabled in the UI).
- **Postconditions:** Alerts stored. The incident remains visible for 72 h.

### UC-07 Triage alerts
- **Actor:** Brand analyst · **Goal:** Work through open alerts.
- **Main flow:** 1. Open Alerts (filter: open). 2. Read the alert message and drivers. 3. Acknowledge or dismiss. 4. The status updates, and the sidebar badge updates through `alert_updated`.
- **Alternative flow:** 3a. Reopen a dismissed alert.
- **Exception flow:** 3b. The alert was deleted by a reset in the meantime → 404.
- **Postconditions:** The status and `updated_at` are changed.

### UC-08 Configure brand, thresholds and notifications
- **Actor:** Operator · **Goal:** Adapt monitoring to a brand and to the team's alerting preferences.
- **Main flow:** 1. Open Settings. 2. Edit the brand, keywords, sources, thresholds, aspects and notification toggles. 3. Save. 4. The system validates, persists, applies the aspect changes and wakes the collectors.
- **Alternative flow:** 3a. "Send test" to check the configured channels. 3b. "Reset to defaults".
- **Exception flow:** 4a. Validation failure (e.g. contamination 0.9) → 422 message and nothing is saved.
- **Postconditions:** The new config is effective immediately for new mentions and the next analytics tick.

### UC-09 Monitor a YouTube channel
- **Actor:** Operator/analyst · **Goal:** Track sentiment in a channel's comments.
- **Preconditions:** A YouTube Data API v3 key.
- **Main flow:** 1. YouTube page → paste the key (from the local machine) → save. 2. Enter `@handle` → Add. 3. The system resolves the channel, sets it as the brand (by default), enables the source and syncs the last 5 videos and their comments. 4. The page shows per-video sentiment, and clicking a video lists its analysed comments. 5. A background sync runs every 5 min.
- **Exception flow:** 1a. Saving the key through the tunnel or a proxy → 403. 3a. Channel not found / quota / key rejected → 422 with an explanation. 3b. Comments disabled on a video → the video is listed with 0 comments.
- **Postconditions:** The channel and videos are stored and the comments analysed.

### UC-10 Connect an Instagram Business account
- **Actor:** Operator (on the host machine) · **Goal:** Analyse real comments on the brand's own posts.
- **Preconditions:** A Business/Creator account, a Meta app, and the user added as an Instagram Tester (or the app approved).
- **Main flow:** 1. Instagram page → save the app ID and secret. 2. Start the secure address (tunnel). 3. Copy the shown redirect URI into the Meta app. 4. Continue with Instagram → log in on instagram.com → Allow. 5. The callback stores the encrypted token, enables the source and syncs. 6. Posts with sentiment per post appear within about a minute.
- **Alternative flow:** 2a. A real domain is used (server deployment) and `PUBLIC_BASE_URL` is set, so no tunnel is needed.
- **Exception flow:** 4a. Redirect URI mismatch → Instagram's own error page (outside BrandShield). 4b. The user cancels → redirect with "login was cancelled". 5a. Personal account → error redirect. 5b. Expired state (> 10 min) → error redirect.
- **Postconditions:** The account is connected and polled every 3 min.

### UC-11 Switch to live data only
- **Actor:** Operator · **Goal:** Remove the demo data before using real data.
- **Preconditions:** Ideally an account or channel is connected.
- **Main flow:** 1. Instagram page → "Use live data only" → confirm. 2. The system disables the simulator, drains the bus, deletes the simulated mentions and all alerts, optionally renames the brand, and recomputes the analytics. 3. The dashboards refresh.
- **Exception flow:** 1a. The API is called without `confirm` → 400.
- **Postconditions:** Only `origin = live` mentions remain. The alert history is empty.

### UC-12 Evaluate model performance
- **Actor:** Evaluator · **Goal:** Obtain accuracy metrics for the report.
- **Main flow:** 1. Performance page → "Run evaluation" (or the CLI). 2. The system evaluates the 83-row domain set (hybrid and model-only, plus aspects) in the background. 3. On completion, the WS `evaluation` event triggers a reload. The metrics and confusion matrix are shown.
- **Alternative flow:** 1a. The CLI with `--datasets tweet_eval --limit 2000` adds the public benchmark (needs Hub access).
- **Exception flow:** 1b. Already running → 409. 1c. Model loading → 503. 2a. Job error → shown from `evaluation_status.error`.
- **Postconditions:** `evaluation.json` is updated.

---

## 11. System Constraints

1. **Single brand, single process.** One brand at a time, `--workers 1`, SQLite single-writer (NFR-SC-01).
2. **No user accounts.** Access control is outside the app: loopback-only setup endpoints, and Caddy basic-auth on the server deployment.
3. **External API policy limits.** Instagram: only the account's own media; Business/Creator only; app roles or App Review needed. YouTube: 10k units/day. Twitter/X: a paid tier for search. Reddit: credentials needed.
4. **HTTPS redirect.** Meta OAuth needs an HTTPS redirect URI, so a tunnel or a domain is needed for Instagram on a laptop.
5. **CPU inference.** Throughput is limited by CPU. Model memory is about 1.8 GB.
6. **Fixed model.** No in-app retraining. The neutral margin (0.20) and lexicon weight (0.35) are code constants.
7. **Analytics granularity.** Anomaly buckets are fixed at 15 min (`BUCKET_MINUTES`, env). The forecast is hourly with a 12 h horizon.
8. **Stored mentions are not re-analysed** when the aspect lexicon or the model changes.
9. **Time zone.** Naive timestamps from CSV/API are interpreted in the server's local time zone. The simulator's seasonality assumes IST.
10. **CORS** allows only the Vite dev origins by default (`CORS_ORIGINS`). Production uses same-origin serving.

---

## 12. Security Requirements

| ID | Requirement | Status | Implementation / note |
|---|---|---|---|
| NFR-SEC-01 | When the dashboard is reachable from beyond the host, access shall be protected by an authenticating layer in front of the app. | **Partial** | The server installer puts Caddy `basic_auth` in front (`deploy/Caddyfile.template`). **Not covered:** the Cloudflare tunnel and Hugging Face Spaces expose the dashboard without any authentication (the README warns about the tunnel). |
| NFR-SEC-02 | Setup actions (credentials, API keys, tunnel) shall be accepted only from the host machine and not via any proxy. | Implemented | FR-045 |
| NFR-SEC-03 | Destructive and configuration actions should have the same protection as setup actions. | **Gap** | `/data/reset`, `/data/use-live-only`, `PUT /settings`, `POST /settings/reset`, `DELETE` account/channel, `/simulator/*` and `/ingest*` are open to anyone who can reach the API (e.g. through the tunnel). Listed as FS-01. |
| NFR-SEC-04 | The OAuth flow shall use a random, single-use, time-limited `state` (600 s) to prevent CSRF. | Implemented | `secrets.token_urlsafe(24)`, `consume_state()` |
| NFR-SEC-05 | Access tokens shall be encrypted at rest with Fernet (AES-128-CBC + HMAC). The key comes from `SECRET_KEY` or the auto-generated `data/secret.key`. | Implemented | `TokenCipher` |
| NFR-SEC-06 | Secrets shall never be returned by the API, and tokens shall be removed from account objects. | Implemented | `GET /keys`, `_public()` |
| NFR-SEC-07 | `.env` shall be readable only by the service user on the server. | Implemented (server only) | `chmod 600` in `install.sh`. On Windows/local this relies on the OS user profile. |
| NFR-SEC-08 | All SQL shall use bound parameters. Only whitelisted column and sort names shall be interpolated. | Implemented | `routes.mentions()`, services |
| NFR-SEC-09 | Static-file serving shall not escape `frontend/dist` (path-traversal guard). | Implemented | `main.spa()` checks `FRONTEND_DIST in candidate.resolve().parents` |
| NFR-SEC-10 | Cross-origin browser access shall be limited to the configured `CORS_ORIGINS`. | Implemented | `CORSMiddleware` |
| NFR-SEC-11 | All external integrations shall be read-only. The system shall never post, reply or delete on any platform. | Implemented | Only GET calls to the platform APIs (POST only for token exchange) |
| NFR-SEC-12 | Traffic to public deployments shall use HTTPS. | Implemented (server, tunnel, HF) | Caddy + Let's Encrypt; `trycloudflare.com`; HF Spaces |

**Note on API keys in `.env`:** these are stored in plain text, which is common practice for `.env` files. Only Instagram tokens are encrypted.

---

## 13. Performance Requirements

### 13.1 Requirements (design-level, from the code)

| ID | Requirement | Basis |
|---|---|---|
| NFR-PERF-01 | The processor shall handle mentions in micro-batches of at most 32, waiting at most 0.5 s to fill a batch. Inference is batched at 32. | `bus.batches()`, `Settings.model_batch_size` |
| NFR-PERF-02 | CPU-bound work (inference, pandas, IF, Prophet, SMTP) shall run outside the asyncio event loop, so API and WS responsiveness does not depend on inference load. | `asyncio.to_thread` throughout |
| NFR-PERF-03 | Repeated texts shall not be re-inferred (LRU cache of 50,000). Analytics data frames shall be cached for 3 s. | `SentimentModel._cache`, `AnalyticsService.load()` |
| NFR-PERF-04 | Risk and anomaly state shall be at most 30 s old (analytics interval). The forecast shall be at most 300 s old. Metrics shall be pushed every 5 s. | `Settings`, `_metrics_loop()` |
| NFR-PERF-05 | Incremental syncs shall re-fetch comments only for media/videos whose comment count changed, to stay within API quotas. | FR-036, FR-041 |
| NFR-PERF-06 | Each YouTube sync shall cost roughly 1 (channel) + 1 per 50 videos (playlist) + 1 per 50 videos (stats) + 1 per comment page (≤ 5 per changed video) quota units. A name search costs 100 and is used only when resolving a channel. | `youtube.py` docstring and calls |
| NFR-PERF-07 | Collectors shall poll no more often than their interval (180 s; YouTube 300 s) plus 0–10 s jitter, unless woken explicitly. | `_collector_loop()` |
| NFR-PERF-08 | Response sizes shall be bounded as in NFR-SC-03. | `routes.py` |

### 13.2 Measured baselines (reference values, not guarantees)

| Metric | Value | Conditions | Source |
|---|---|---|---|
| Inference time | 32.4 ms/text (domain), 120 ms/text (real comments) | Batched, CPU, two-model ensemble | `backend/data/evaluation.json` (latest run) |
| Single-text inference | ~140 ms including HTTP | Laptop CPU, Analyze Text request | Measured on the running server |
| Resident memory | ~2 GB | Running process, both models loaded | Measured on the running server |
| Crisis detection delay | 24 s; risk 20 → 79 | Controlled crisis injection on live data | Alerts table, crisis test run |
| End-to-end latency, throughput | Reported live: p50/p95 latency, items/s | `/api/system/metrics` | FR-049 |

The team has set no hard numeric SLAs for this academic deployment. Regressions should be judged against these baselines, re-measured on the same machine (see TC-29).

---

## 14. Testing and Verification Requirements

### 14.1 Current state (stated plainly)

- The repository has **no automated test suite**: no pytest, no frontend tests, no CI. `scripts/test_sentiment.py` belongs to the phase-1 Flask prototype and just prints predictions.
- Verification so far has been: the model evaluation script (FR-050), manual API testing through `/docs`, manual UI testing during demos, and measurements recorded in the README and paper.
- While preparing this SRS (6 Oct 2025) the following were checked by running code. These rows are marked "Checked" below: preprocessing/spam on sample inputs, the RuntimeConfig validation messages and gaps (VR-030–037), timestamp parsing (VR-013/014) and CSV engagement parsing (VR-024).

### 14.2 Verification methods

| Code | Method |
|---|---|
| A | Automated test (planned: pytest + FastAPI `TestClient`, with `SentimentModel` stubbed for speed) |
| M | Manual test through the Swagger UI `/docs` or the dashboard |
| E | Scripted evaluation (`scripts.evaluate_model`) |
| I | Code inspection |

### 14.3 Test cases

| TC | Covers | Procedure | Expected result | Method | Status |
|---|---|---|---|---|---|
| TC-01 | FR-049 | GET `/api/health` | 200 `{status:"ok"}` | M/A | Defined |
| TC-02 | FR-013, NFR-AV-03 | POST `/api/analyze` immediately after start | 503 until `model_ready`, then 200 | M | Defined |
| TC-03 | FR-016, VR-001 | Analyze `""` and 5001 chars | 422 both | M/A | Defined |
| TC-04 | FR-014 | Analyze "Worst coffee ever 😡" | label negative, score < 0 | M | Defined |
| TC-05 | FR-014 (lexicon) | Analyze "khana ekdum bekar tha" | negative, `lexicon_polarity < 0` | M | Defined |
| TC-06 | FR-015 | Analyze "food was great but delivery was late" | food_quality positive, delivery negative | M | Defined |
| TC-07 | FR-012 | Preprocess "Follow me for free followers!!! https://x.co" | spam, "promotional / scam phrase" | A | Checked |
| TC-08 | FR-012 | Preprocess "https://bit.ly/abc" | spam, "link with little content" | A | Checked |
| TC-09 | FR-011 | Preprocess "Coffee was sooooo good 😍 @saffron #yum" | clean "Coffee was soo good 😍 yum"; model text contains "love" | A | Checked |
| TC-10 | FR-007, VR-010 | POST `/ingest` `{items:[]}` | 422 | M/A | Defined |
| TC-11 | FR-010 | Ingest the same item twice | stored once; `duplicates_total` +1 | M/A | Defined |
| TC-12 | NFR-REL-02 | Force an exception in `analyze` | `errors_total` +1, stream continues | A | Defined |
| TC-13 | FR-008, VR-021/022 | Upload a UTF-16 CSV; a CSV without a text column | 400 with the specified messages | M/A | Defined |
| TC-14 | FR-008, VR-024 | CSV with engagement "1e3", "-4", "35" | 0, 0, 35 | A | Checked (parser) |
| TC-15 | VR-013/014 | Ingest `created_at` "garbage" and "2030-01-01T00:00:00Z" | both stored with ≈ the ingest time | A | Checked (parser) |
| TC-16 | FR-044, VR-030–037 | PUT `/settings` with each invalid value in 8.4 | 422 with the listed message (gaps accepted) | A | Checked |
| TC-17 | FR-002 | Crisis with simulator off; with aspect "parking" | 409; 422 | M | Defined |
| TC-18 | FR-024, FR-029, UC-06 | Start a delivery crisis (20 min, 0.8) on seeded data | `negative_spike` and/or `aspect_surge:delivery` alert within a few analytics ticks; anomaly visible on `/anomalies` | M | Defined (baseline ~60 s, §13.2) |
| TC-19 | FR-031 | Keep the crisis running past the first alert | no duplicate of the same `dedupe_key` within 30 min | M | Defined |
| TC-20 | FR-026, NFR-REL-05 | Forecast with an empty DB, < 36 h and ≥ 36 h of history | `insufficient_data` / `holt` / `prophet` | A | Defined |
| TC-21 | FR-028 | Unit test `compute_risk` with a synthetic frame | components within their maxima; level thresholds 30/55/75 | A | Defined |
| TC-22 | FR-032 | Acknowledge an alert; acknowledge id 999999 | 200 with `alert_updated` event; 404 | M | Defined |
| TC-23 | FR-033/034 | Configure a Slack webhook; Send test | `delivery.slack == "sent"`; an invalid URL gives `error: …` | M | Defined |
| TC-24 | FR-045, NFR-SEC-02 | PUT `/keys` with header `X-Forwarded-For: 1.2.3.4` | 403 | A | Defined |
| TC-25 | FR-040, VR-066 | Call the callback with an unknown `state` | 303 to `/instagram?error=Login session expired…` | A | Defined |
| TC-26 | FR-035 | Add channel "@mkbhd"; add "@no_such_channel_xyz" | channel stored with comments queued; 422 | M | Defined |
| TC-27 | FR-047, VR-069 | POST `/data/reset` `{}`; then with `confirm:true, reseed:false` | 400; tables empty | M/A | Defined |
| TC-28 | FR-048 | Open `/ws`, send "ping" | first message `status`, then `pong` | A | Defined |
| TC-29 | FR-050, §13.2 | `python -m scripts.evaluate_model` | `evaluation.json` updated; metrics reproducible within rounding for the same model | E | Executed earlier by the team (results in `evaluation.json`) |
| TC-30 | NFR-REL-01 | `BUS_BACKEND=kafka` with no broker | starts; bus "memory" | M | Defined |
| TC-31 | NFR-PR-01 | GET `/instagram/status` with a connected account | no `access_token` field | M/A | Defined |
| TC-32 | NFR-SEC-09 | GET `/..%2f..%2fbackend/.env` | serves `index.html`, not the file | M | Defined |

### 14.4 Acceptance criteria for the project review

1. All 53 FRs are demonstrable on the running system (FR-053 is demonstrated as Partial).
2. TC-01 to TC-32 are executed and their results recorded before the final submission. Automating at least the "A" cases is recommended (FS-02).
3. Evaluation figures in the paper and README are re-generated on submission day (see `docs/paper/README.md`).

---

## 15. Deployment Requirements

### 15.1 Supported deployment modes

| Mode | Artefacts | Bus | Persistence | Access protection |
|---|---|---|---|---|
| Local Windows, one click | `start.bat` (venv, pip, NLTK data, `npm run build`, uvicorn 127.0.0.1:8000) | memory | `backend/data/` | Loopback only |
| Local with a public link | `start-public.bat` + `backend/scripts/go_live.py` (waits for `model_ready`, starts the tunnel, checks reachability, retries 3×) | memory | `backend/data/` | **None on the public URL** |
| Development | uvicorn `--reload` + `npm run dev` (5173, proxies `/api` and `/ws`) | memory | `backend/data/` | – |
| Docker Compose + Kafka | `docker-compose.yml` (apache/kafka 3.9.1 KRaft + `backend/Dockerfile`); `frontend/dist` must be built first | kafka | Named volumes `brandshield-data`, `hf-models` | – |
| Ubuntu server | `deploy/install.sh <domain> <email>`: venv, CPU torch, model pre-download, systemd unit, Caddy (HTTPS + basic-auth), ufw 22/80/443, 2 GB swap | memory | `/opt/brandshield/backend/data` | Caddy basic-auth |
| Hugging Face Space | Root `Dockerfile` (multi-stage: node:20 build → python:3.12, model baked in), `deploy/huggingface/start.sh`, port 7860 | memory | `/data` if persistent storage is attached, otherwise `/tmp` (reset on restart) | **None** |

### 15.2 Deployment requirements

- **DR-01** The frontend must be built (`frontend/dist`) before the backend can serve the dashboard. Without it only the API is served.
- **DR-02** The first start needs internet access to download the models (about 1.6 GB), unless the model is baked into the image (HF Dockerfile) or pre-downloaded (`install.sh`).
- **DR-03** NLTK `stopwords`, `wordnet` and `omw-1.4` should be downloaded. All install paths do this. Without them, the rule-based fallbacks are used.
- **DR-04** `backend/data/` must be writable (DB, secret key, cloudflared binary).
- **DR-05** Only one backend process may use a given database file.
- **DR-06** For Instagram, `PUBLIC_BASE_URL` must be the externally visible HTTPS origin, and `<PUBLIC_BASE_URL>/api/auth/instagram/callback` must be registered character for character in the Meta app.
- **DR-07** `cryptography` must be installed. It is currently missing from `requirements.txt` (Appendix B, item 1). Add it before building any image.
- **DR-08** Back up `backend/data/brandshield.db`. Also keep `secret.key`, because without it the stored tokens cannot be decrypted. DEPLOY.md gives a cron example.

### 15.3 Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `BRAND_NAME`, `BRAND_KEYWORDS` | Saffron Cafe; 3 variants | Initial brand (the runtime config overrides it) |
| `DATABASE_PATH`, `EVALUATION_PATH` | `backend/data/…` | Storage locations |
| `SENTIMENT_MODEL`, `FALLBACK_SENTIMENT_MODEL`, `MODEL_BATCH_SIZE`, `MODEL_MAX_LENGTH` | cardiffnlp XLM-R + RoBERTa; tabularisai, SST-2; 32; 256 | NLP |
| `BUS_BACKEND`, `KAFKA_BOOTSTRAP_SERVERS` | memory, localhost:9092 | Streaming |
| `ENABLE_SIMULATOR`, `SIMULATOR_RATE_PER_MIN`, `SEED_HISTORY_DAYS` | true, 8, 3 | Simulator |
| `ENABLE_REDDIT/RSS/TWITTER/YOUTUBE/APPSTORE` | false | Initial source toggles |
| `REDDIT_CLIENT_ID/SECRET`, `TWITTER_BEARER_TOKEN`, `YOUTUBE_API_KEY`, `APPSTORE_APP_ID`, `APPSTORE_COUNTRY`, `RSS_FEEDS` | empty / `in` | Source credentials |
| `YOUTUBE_MAX_VIDEOS`, `YOUTUBE_POLL_SECONDS` | 5, 300 | YouTube |
| `INSTAGRAM_APP_ID/SECRET`, `INSTAGRAM_MEDIA_LIMIT`, `INSTAGRAM_POLL_SECONDS`, `INSTAGRAM_GRAPH_VERSION` | –, 25, 180, v23.0 | Instagram |
| `PUBLIC_BASE_URL`, `FRONTEND_URL`, `SECRET_KEY` | http://127.0.0.1:8000, –, auto | OAuth / encryption |
| `POLL_INTERVAL_SECONDS`, `BUCKET_MINUTES`, `ANALYTICS_INTERVAL_SECONDS`, `FORECAST_REFRESH_SECONDS`, `FORECAST_HORIZON_HOURS` | 180, 15, 30, 300, 12 | Scheduling |
| `SMTP_*`, `ALERT_EMAIL_TO`, `SLACK_WEBHOOK_URL`, `TEAMS_WEBHOOK_URL`, `TWILIO_*`, `ALERT_SMS_TO` | empty | Notifications |
| `CORS_ORIGINS` | localhost/127.0.0.1:5173 | CORS |

---

## 16. Future Scope (Planned – not implemented)

| ID | Item | Origin |
|---|---|---|
| FS-01 | User accounts, roles, and authentication on every endpoint. Extend local-only protection to destructive endpoints (closes NFR-SEC-01/03). | DEPLOY.md "Before you open it to real users", this audit |
| FS-02 | Automated test suite (pytest + TestClient, frontend component tests) and CI running TC-01–32 | This audit |
| FS-03 | Tighten validation: ranges for all thresholds, `keywords` must be a list, non-negative engagement, length limits on `source`/`author`, a Pydantic model for `PUT /settings` | This audit (VR gaps) |
| FS-04 | Per-user data isolation (multi-tenant): mentions, channels and alerts scoped to an owner | DEPLOY.md |
| FS-05 | PostgreSQL/TimescaleDB (or MongoDB) instead of SQLite for concurrent writers | DEPLOY.md, `db.py` docstring |
| FS-06 | Separate background worker process, so slow syncs never block the API | DEPLOY.md |
| FS-07 | Static "snapshot mode" in the frontend that uses `snapshot.json` (completes FR-053) | `export_static.py` |
| FS-08 | Per-user quota limits on the shared YouTube key | DEPLOY.md |
| FS-09 | Data-retention policy (automatic purge or archive of old mentions and alerts) | This audit |
| FS-10 | Retry or dead-letter handling for failed processor batches and failed notification deliveries | This audit (NFR-REL-02, EH-14) |
| FS-11 | Better mixed-opinion and Hinglish price-complaint handling; a larger labelled test set | README limitations |
| FS-12 | Kafka consumer-lag reporting (queue depth is currently `null` on Kafka) | `bus.py` |
| FS-13 | Re-analysis of stored mentions after aspect-lexicon or model changes | Constraint 8 |
| FS-14 | Remove dead code (`public_sources.YouTubeCollector`, unused settings `youtube_comment_pages`, `youtube_search_interval_hours`) | This audit |

---

## 17. Traceability Matrix

Test references point to Section 14.3. Status: **I** = Implemented, **P** = Partial.

| Req | Requirement | Module | Implementation location | Validation | Verification | Status |
|---|---|---|---|---|---|---|
| FR-001 | Simulated stream + seeding | M3 | `collectors/simulator.py` → `generate()`, `history()`; `core.py` → `_seed_then_simulate()`, `seed_history()` | VR-030 | M (Dashboard after first start) | I |
| FR-002 | Crisis simulation | M3 | `routes.py` → `start_crisis()`, `stop_crisis()`; `simulator.py` → `start_crisis()` | VR-050–052 | TC-17, TC-18 | I |
| FR-003 | News/RSS collector | M3 | `platforms.py` → `RssCollector.poll()` | VR-070, VR-079 | M (enable `rss`) | I |
| FR-004 | Reddit, Twitter collectors | M3 | `platforms.py` → `RedditCollector`, `TwitterCollector` | credential checks | M | I |
| FR-005 | App Store collector | M3 | `public_sources.py` → `AppStoreCollector` | rating map | M | I |
| FR-006 | Collector scheduling | M1 | `core.py` → `_collector_loop()`, `wake_collectors()`; `routes.py` → `poll_now()` | toggles | M, I | I |
| FR-007 | REST ingest | M10 | `routes.py` → `ingest()`, `IngestRequest` | VR-010–015 | TC-10, TC-11 | I |
| FR-008 | CSV ingest | M10 | `routes.py` → `ingest_csv()`; `Analyze.jsx` → `uploadCsv()` | VR-020–026 | TC-13, TC-14 | I |
| FR-009 | Bus + Kafka fallback | M5 | `bus.py` → `create_bus()`, `KafkaBus`, `MemoryBus` | 10 s connect timeout | TC-30 | I |
| FR-010 | Normalise + dedupe | M5 | `processor.py` → `normalise_raw()`, `mention_id()`, `process_batch()` | VR-013/014, VR-070 | TC-11, TC-15 | I |
| FR-011 | Preprocessing + language | M6 | `preprocess.py` → `preprocess()`, `detect_language()` | – | TC-09 | I |
| FR-012 | Spam detection | M6 | `preprocess.py` → `detect_spam()` | 6 rules | TC-07, TC-08 | I |
| FR-013 | Model load + readiness | M6 | `sentiment.py` → `load()`; `core.py` → `_load_model()`; `routes.py` → `_require_model()` | readiness gate | TC-02 | I |
| FR-014 | Hybrid sentiment | M6 | `sentiment.py` → `predict()`, `_finalise()`, `lexicon_polarity()` | VR-072, VR-073 | TC-04, TC-05, TC-29 | I |
| FR-015 | ABSA | M6 | `aspects.py` → `AspectExtractor.analyze_batch()`, `split_clauses()` | lexicon normalisation VR-032 | TC-06, TC-29 | I |
| FR-016 | Analyze Text | M10/M11 | `routes.py` → `analyze()`; `Analyze.jsx` | VR-001–004, VR-090 | TC-02, TC-03 | I |
| FR-017 | Mention persistence | M9 | `db.py` → `insert_mentions()`, `SCHEMA`, `MIGRATIONS` | VR-080, VR-081 | TC-11 | I |
| FR-018 | Mention search | M10/M11 | `routes.py` → `mentions()`; `Mentions.jsx` | VR-040, VR-043–047 | M/A | I |
| FR-019 | Mention facets | M10 | `routes.py` → `mention_facets()` | – | M | I |
| FR-020 | Overview KPIs | M7 | `service.py` → `overview()`, `sentiment_counts()` | VR-040 | M | I |
| FR-021 | Text summary | M7 | `service.py` → `build_summary()` | – | M | I |
| FR-022 | Trends | M7 | `service.py` → `trends()`; `anomaly.py` → `bucketize()` | VR-040, VR-042 | M | I |
| FR-023 | Aspect insights | M7 | `service.py` → `aspects()`, `aspect_table()`, `top_keywords()` | VR-040 | M | I |
| FR-024 | Anomaly detection | M7 | `anomaly.py` → `detect_anomalies()`, `_robust_z()`; `service.py` → `anomalies()` | VR-041, VR-074–076 | TC-18 | I |
| FR-025 | Incidents | M7 | `anomaly.py` → `summarise_anomalies()` | – | TC-18 | I |
| FR-026 | Forecast | M7 | `forecast.py` → `forecast()`, `_holt()`; `service.py` → `refresh_forecast()` | VR-077, VR-078 | TC-20 | I |
| FR-027 | Periodic snapshot | M1/M7 | `core.py` → `_analytics_loop()`, `_forecast_loop()`; `service.py` → `compute_snapshot()` | seeding guard | I, logs | I |
| FR-028 | Risk score | M7 | `risk.py` → `compute_risk()`, `risk_level()`; `routes.py` → `risk()`; `RiskGauge.jsx` | clamps | TC-21 | I |
| FR-029 | Snapshot alert rules | M8 | `engine.py` → `evaluate()` | thresholds VR-034–036 | TC-18 | I |
| FR-030 | Viral negative rule | M8 | `engine.py` → `check_mentions()` | `viral_engagement` | M (crisis) | I |
| FR-031 | Cool-down dedupe | M8 | `engine.py` → `raise_alert()`, `_recently_fired()` | – | TC-19 | I |
| FR-032 | Alert lifecycle | M8/M10 | `routes.py` → `list_alerts()`, `update_alert()`; `engine.py` → `set_status()`; `Alerts.jsx` | VR-048 | TC-22 | I |
| FR-033 | Notifications | M8 | `notifiers.py` → `Notifier.send()` and channel methods | `min_severity` VR-037 | TC-23 | I |
| FR-034 | Test notification | M8 | `routes.py` → `test_alert()` | – | TC-23 | I |
| FR-035 | Add YouTube channel | M4 | `routes.py` → `add_youtube_channel()`; `youtube.py` → `resolve()`, `save_channel()` | VR-065 | TC-26 | I |
| FR-036 | YouTube sync | M4 | `youtube.py` → `sync_channel()`, `sync_all()`, `YouTubeChannelCollector`; `core.py` → `sync_youtube()` | change detection | M | I |
| FR-037 | YouTube remove/list | M4 | `routes.py` → `remove_youtube_channel()`, `youtube_videos()`, `youtube_status()` | VR-068 | M | I |
| FR-038 | Instagram credentials | M4 | `routes.py` → `save_instagram_credentials()`; `config.py` → `write_env()` | VR-060, VR-061 | TC-24 (pattern) | I |
| FR-039 | Tunnel | M4 | `tunnel.py` → `TunnelManager.start/stop/restore()`; `routes.py` → `instagram_tunnel()`; `go_live.py` | local-only | M | I |
| FR-040 | Instagram OAuth | M4 | `routes.py` → `instagram_login()`, `instagram_callback()`; `instagram.py` → `complete_login()` | VR-066, VR-067 | TC-25 | I |
| FR-041 | Instagram sync | M4 | `instagram.py` → `sync_account()`, `_refresh_if_needed()`, `InstagramCollector`; `core.py` → `sync_instagram()` | own-reply filter | M | I |
| FR-042 | Instagram disconnect/media | M4 | `routes.py` → `instagram_disconnect()`, `instagram_media()`, `instagram_status()` | VR-068 | TC-31 | I |
| FR-043 | Live-only switch | M1 | `routes.py` → `use_live_only()`; `core.py` → `use_live_data_only()` | VR-069 | M | I |
| FR-044 | Runtime settings | M2 | `runtime.py` → `RuntimeConfig`; `routes.py` → `get/put/reset_settings()`; `Settings.jsx` | VR-030–038 | TC-16 | P |
| FR-045 | Local-only setup | M10 | `routes.py` → `_setup_only()` | origin check | TC-24 | I |
| FR-046 | API keys | M2/M10 | `routes.py` → `api_keys()`, `save_api_keys()` | VR-062–064 | TC-24 | I |
| FR-047 | Data reset | M1 | `routes.py` → `reset_data()`; `core.py` → `reset_data()` | VR-069 | TC-27 | I |
| FR-048 | WebSocket events | M5/M11 | `routes.py` → `websocket()`; `hub.py` → `Hub`; `live.jsx` | – | TC-28 | I |
| FR-049 | Health/metrics | M5 | `routes.py` → `health()`, `status()`, `system_metrics()`; `metrics.py` | – | TC-01 | I |
| FR-050 | Model evaluation | M12 | `scripts/evaluate_model.py` → `evaluate_datasets()`; `routes.py` → `run_evaluation()` | 409 guard | TC-29 | I |
| FR-051 | Dashboard pages | M11 | `main.jsx`, `Layout.jsx`, `pages/*.jsx` | VR-090–097 | M | I |
| FR-052 | Toasts/notifications | M11 | `live.jsx` → `LiveProvider`; `Alerts.jsx` | permission check | M | I |
| FR-053 | Static snapshot export | M12 | `backend/scripts/export_static.py` (untracked) | – | M | P |
| NFR-SEC-02 | Local-only setup | M10 | `routes.py` → `_setup_only()` | – | TC-24 | I |
| NFR-SEC-03 | Protect destructive endpoints | M10 | – | – | – | Gap |
| NFR-SEC-04 | OAuth state | M4 | `instagram.py` → `consume_state()` | VR-066 | TC-25 | I |
| NFR-SEC-05 | Token encryption | M4 | `instagram.py` → `TokenCipher` | – | I, TC-31 | I |
| NFR-SEC-09 | Path-traversal guard | M10 | `main.py` → `spa()` | – | TC-32 | I |
| NFR-REL-01 | Kafka fallback | M5 | `bus.py` → `create_bus()` | – | TC-30 | I |
| NFR-REL-05 | Forecast fallback | M7 | `forecast.py` | VR-077 | TC-20 | I |
| NFR-DI-01 | Deterministic IDs | M5 | `processor.py` → `mention_id()` | VR-081 | TC-11 | I |

---

## Appendix A – SRS Validation Summary

| Item | Count / result |
|---|---|
| Functional requirements | **53** (FR-001–FR-053): 51 Implemented, 2 Partial (FR-044, FR-053) |
| Non-functional requirements | **58**: Reliability 7, Availability 4, Scalability 4, Maintainability 5, Usability 4, Compatibility 3, Privacy 5, Data integrity 6, Security 12, Performance 8 |
| Use cases | **12** (UC-01–UC-12) |
| Validation rules | **70** (Section 8), 6 of them flagged as gaps (VR-003, 012, 033, 036, 082, 097) |
| Error-handling requirements | 19 (EH-01–EH-19) |
| Test cases | 32 (TC-01–TC-32); 6 checked during SRS preparation, 1 executed earlier by the team, the rest defined |
| Requirements mapped to implementation | 53/53 FRs mapped to concrete files and functions; 8 key NFRs in the matrix; all other NFRs carry their code basis in Section 5/12/13 |
| Requirements "To be confirmed" | NFR-CO-02 (cross-browser), EH-08 (behaviour under real disk-full/locked DB), EH-17 (whether a loop can exit), A-1 (fully offline install) |
| Planned / Future scope | 14 items (FS-01–FS-14), kept out of the FR list |

Audit checks performed: every endpoint in Section 6.2 was compared with the 43 decorators in `routes.py` plus `/ws`. Every table and column in Section 7.2 was compared with `db.SCHEMA` plus `MIGRATIONS`. Every default and limit was taken from code and cross-checked by grep. Counts (32 emoji mappings, 22 spam patterns, 51 lexicon terms, 132 default aspect keywords, 83 evaluation rows) were computed by running the code. Requirement IDs are unique and sequential. Vague terms such as "fast" or "secure" are either tied to a number or mechanism, or are not used.

## Appendix B – Implementation/Documentation Inconsistencies Found

1. **Missing dependency:** `backend/app/integrations/instagram.py` imports `cryptography`, but it is not in `backend/requirements.txt`. It is installed in the local venv (`pip show` lists it as required by nothing), so a clean install, Docker image or HF Space build would likely fail at import. *TBC by a clean build; fix by adding `cryptography` to requirements.*
2. **Server/HF key entry vs. the local-only guard:** `deploy/DEPLOY.md` (step 6) and `deploy/huggingface/README.md` tell users to paste keys in the web UI. `_setup_only()` rejects any request carrying `X-Forwarded-For`, which Caddy and the HF proxy normally add, so those saves would return 403. *TBC on the live deployments.* The workaround is editing `.env` or using HF secrets.
3. **Paper README cites a non-existent script:** `docs/paper/README.md` refers to `backend/scripts/evaluate_domain.py`. The actual script is `backend/scripts/evaluate_model.py`.
4. **CSV error message is narrower than the code:** the message says "'text' or 'comment' column", but `content` and `message` are also accepted.
5. **Dead code:** `collectors/public_sources.YouTubeCollector` (a keyword-search YouTube collector) is never instantiated. `core.py` uses `integrations/youtube.YouTubeChannelCollector`. The settings `youtube_comment_pages` and `youtube_search_interval_hours` are only used by the dead class.
6. **"Browser push" wording:** the README says "browser push". The implementation uses the in-page Notification API, which works only while a dashboard tab is open. There is no push service.
7. **Validation gaps in runtime config:** a `keywords` string is split into characters, and most thresholds have no range check (VR-033, VR-036). Both were reproduced on 6 Oct 2025.
8. **Unprotected destructive endpoints:** reset, live-only, settings, delete and ingest are callable by anyone who can reach the API through the tunnel or an unauthenticated Space (NFR-SEC-03).
9. **`SEED_HISTORY_DAYS=0` and reset:** a data reset with `reseed=true` seeds 3 days even when the env says 0 (`seed_history_days or 3`).
10. **Crisis default differs:** the API defaults to 20 minutes, the Settings UI to 15. This is harmless, but documented.
11. **Language detection quality:** short informal English can be mislabelled (e.g. `so`), and Hinglish is labelled `en`. This affects the language breakdown only, not sentiment.
12. **Static export has no consumer:** `export_static.py` (untracked) writes `snapshot.json`, but the frontend has no snapshot mode yet (FR-053).

**Assumptions made in writing this SRS:**

- The phase-1 Flask prototype is out of scope.
- The untracked scripts (`go_live.py`, `export_static.py`, `start-public.bat`) are part of the intended baseline.
- Measured figures in the README and paper were taken at face value as baselines, not re-measured, except for `evaluation.json`, which was read directly.
- "User" means anyone who can reach the dashboard, because the app has no authentication.
