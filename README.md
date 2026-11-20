---
title: BrandShield AI
emoji: 🛡️
colorFrom: orange
colorTo: red
sdk: docker
app_port: 7860
pinned: false
short_description: Real-time brand risk and sentiment intelligence
---

# BrandShield AI – Real-Time Brand Risk & Sentiment Intelligence System

Final year project · T.Y. A (AIDS) · K.K. Wagh Institute of Engineering Education & Research, Nashik
Team (PID 02): Soham Borse, Tanish Bantwal, Aryan Baakle, Omsingh Rajput · Guide: Dr. Darshan Medhane

BrandShield AI monitors social media mentions of a brand in real time. It classifies sentiment with an ensemble of BERT-family models (RoBERTa + XLM-RoBERTa), finds which
aspects people complain about, detects crises with Isolation Forest, forecasts sentiment with Prophet, and raises alerts.

## Quick start (Windows)

Requirements: Python 3.12+ and Node.js 20+.

```bat
start.bat
```

The script installs everything, builds the dashboard, and opens **http://127.0.0.1:8000**.
The first start downloads the two sentiment models (~1.6 GB) and generates 3 days of demo history (about 3–5 minutes).

### Manual start / development

```bash
# backend (terminal 1)
python -m venv env
env\Scripts\pip install -r backend/requirements.txt
cd backend
..\env\Scripts\python -m uvicorn app.main:app --reload     # http://127.0.0.1:8000/docs for the API

# frontend with hot reload (terminal 2)
cd frontend
npm install
npm run dev                                               # http://localhost:5173
```

### With Apache Kafka (Docker)

```bash
cd frontend && npm install && npm run build && cd ..
docker compose up --build
```

## Connect a real Instagram account

Open **Instagram** in the sidebar — the page walks through the whole setup, no file editing and no restart.
BrandShield uses the official **Instagram API with Instagram Login** (OAuth): the user types their Instagram
username and password **on instagram.com itself** and approves read access. The app only receives a token,
which is stored encrypted and refreshed automatically. Instagram has no password API, and logging in with a
password through an unofficial library breaks their terms and gets accounts locked, so it is not supported here.

**Requirements:** an Instagram **Business** or **Creator** account (free to switch: Instagram app → Settings →
Account type) and one Meta app, which Meta requires before any account can log in.

1. **Create a Meta app** at [developers.facebook.com/apps](https://developers.facebook.com/apps) — use case
   *Manage messaging and content on Instagram*, type **Business**. Open **Instagram → API setup with Instagram
   login** and copy the Instagram app ID and secret.
2. **Paste both keys into the Instagram page** and click *Save keys*. They are written to `backend/.env` and
   applied immediately.
3. **Click *Start secure address***. Meta only accepts https redirect URIs, which `127.0.0.1` cannot provide, so
   BrandShield downloads `cloudflared` and opens a free Cloudflare tunnel. Copy the redirect URI shown on the
   page into the Meta app (Instagram → *Set up Instagram business login* → **Business login settings** →
   *OAuth redirect URIs*) and save it there. It must match **character for character**, including `https://`
   and the `/api/auth/instagram/callback` path — a mismatch is what causes Instagram’s
   *“Invalid Request: Request parameters are invalid: Invalid redirect_uri”* page.
   The address keeps running in the background and is reused after a BrandShield restart, so you only paste it
   once; it changes only if you stop it or reboot. Stop it from the Instagram page when the demo is over —
   connected accounts keep working without it.
4. **Choose who may log in.** While the Meta app is in development mode, add each Instagram account under
   **App roles → Roles** as an **Instagram Tester** and accept the invite in Instagram (Settings → Website
   permissions → Apps and websites). For anyone outside that list, submit the app for **App Review** with
   `instagram_business_basic` and `instagram_business_manage_comments` plus Business Verification.
5. **Click *Continue with Instagram***, log in, approve — the profile, posts and comments are imported and
   analysed within a minute.

The Instagram page then shows the connected profile, each post with the sentiment of its comments, and a
button that switches the dashboard to real data only (deleting the simulated demo mentions).

**What the Instagram API allows:** comments on *your own* account's posts, plus mentions and tags of it.
Reading another brand's comments is not possible with the official API — use the simulator, CSV import or the
news/RSS source for competitor monitoring.

**Security notes:** tokens are encrypted with a Fernet key (`backend/data/secret.key`, or `SECRET_KEY`), never
returned by the API, and refreshed before their 60-day expiry. The OAuth `state` parameter is verified against
cross-site request forgery. While the public address is running the dashboard is reachable by anyone who knows
the link, so setup actions (saving keys, starting/stopping the tunnel) are refused for any request that arrives
through it. Only posts whose comment count changed are re-fetched, which keeps the app inside Instagram's
rate limits.

## Deploying to a server

To run BrandShield AI permanently on the internet (any phone, any laptop, no laptop required at home),
see **[deploy/DEPLOY.md](deploy/DEPLOY.md)**. One command on a fresh Ubuntu server sets up Python, the
model, a systemd service and HTTPS:

```bash
sudo bash deploy/install.sh yourdomain.me you@email.com
```

The GitHub Student Developer Pack covers the cost: $200 DigitalOcean credit plus a free domain.

## Demo script (for the review)

1. **Dashboard**: KPIs, AI summary, sentiment trend, distribution, brand-risk gauge, aspect insights, live mention feed.
2. **Settings → Crisis simulation**: start a *Delivery* crisis. The complaint thread that was building up arrives at once
   (about five minutes of crisis comments), so within about 20 seconds the risk score jumps to HIGH/CRITICAL and alerts
   appear (*Sudden spike in negative sentiment*, *Multiple delivery complaints detected*, *Negative post is going viral*).
3. **Trends & Forecast**: the anomaly chart marks the spike; the incident list and the Prophet forecast update.
4. **Instagram**: connect a real Business/Creator account with Instagram login (see above) and watch real comments being classified per post.
5. **Analyze Text**: paste any comment (English, Hinglish, Hindi, Marathi) to see every pipeline step:
   cleaning → tokens → lemmas → language → spam → sentiment probabilities → aspect-level sentiment.
   **Why this label?** shows which words moved the prediction (each word is removed in turn and the comment
   re-scored) and which lexicon terms matched.
6. **Report**: a one-page brand summary (risk, sentiment split, topics, worst complaints, alerts) to print or save
   as PDF. **Mentions → Export CSV** downloads the filtered mentions (up to 10,000) for Excel.
7. **Performance**: live throughput/latency/inference time, plus accuracy, precision, recall, F1, and the confusion
   matrix. **API docs** opens the interactive OpenAPI documentation (`/docs`) for every endpoint.

## Architecture

```
Collectors ──► Message bus ──► Stream processor ──────────────► SQLite ──► FastAPI (REST + WebSocket) ──► React dashboard
 simulator      Kafka or         preprocessing                               │
 Google News    in-memory        RoBERTa ensemble                            ├─ Isolation Forest + adaptive z-score (every 30 s)
 Reddit         queue            aspect-based sentiment                      ├─ Prophet forecast (every 5 min)
 Twitter / X                     spam filter                                 ├─ Risk score (5 signals)
 Instagram                                                                   └─ Alert engine ─► dashboard, browser push,
 CSV / REST API                                                                                email, Slack, Teams, SMS
```

| Slide module | Implementation |
|---|---|
| Data collection | `backend/app/collectors/` – simulator, Google News RSS, Reddit, Twitter API v2; `backend/app/integrations/instagram.py` – real Instagram accounts via OAuth login; CSV upload; `POST /api/ingest` |
| Ingestion & streaming | `backend/app/pipeline/bus.py` – Apache Kafka (aiokafka), falls back to an asyncio queue |
| Preprocessing | `backend/app/nlp/preprocess.py` – URL/mention/hashtag removal, emoji normalisation, tokenisation, NLTK stop words, WordNet lemmatisation, language detection, spam detection |
| Sentiment analysis | `backend/app/nlp/sentiment.py` – ensemble of XLM-RoBERTa + RoBERTa (BERT family, fine-tuned on tweets by Cardiff NLP), averaged, + Hinglish/Hindi/Marathi lexicon + neutral margin; DistilBERT as fallback |
| Aspect-based analysis | `backend/app/nlp/aspects.py` – clause splitting, keyword lexicon (editable in Settings), per-clause sentiment |
| Anomaly detection | `backend/app/analytics/anomaly.py` – Isolation Forest + robust (median/MAD) z-score on negative share |
| Sentiment prediction | `backend/app/analytics/forecast.py` – Prophet (Holt smoothing fallback) |
| Risk & alerts | `backend/app/analytics/risk.py`, `backend/app/alerts/` |
| Backend API | `backend/app/api/routes.py` – FastAPI, interactive docs at `/docs` |
| Dashboard | `frontend/` – React, Tailwind CSS, Chart.js, live WebSocket updates |

## Evaluation results

Run with `cd backend && ..\env\Scripts\python -m scripts.evaluate_model` (add `--datasets domain tweet_eval --limit 2000`
for the public TweetEval benchmark). Results are also shown on the Performance page.

Two test sets:

- **Domain set** – 83 hand-labelled brand comments (`backend/eval/domain_labeled.csv`), including Hinglish, Hindi, Marathi, sarcasm and mixed opinions, written by the team.
- **Real comments** – 200 comments sampled at random from the live database (110 YouTube, 60 Instagram, 30 news) and labelled by hand (`backend/eval/real_comments_labeled.csv`).

| Model | Domain acc. | Domain F1 | Real acc. | Real F1 |
|---|---|---|---|---|
| `lxyuan/distilbert-base-multilingual-cased-sentiments-student` (first attempt) | 49.4% | 40.6% | – | – |
| DistilBERT (`tabularisai/multilingual-sentiment-analysis`) + lexicon (previous) | 78.3% | 77.6% | 66.5% | 65.2% |
| XLM-RoBERTa alone (`cardiffnlp/twitter-xlm-roberta-base-sentiment`) + lexicon | 81.9% | 80.6% | 72.0% | 70.3% |
| XLM-RoBERTa + RoBERTa ensemble + lexicon (v1, in the report) | 83.1% | 81.7% | 74.0% | 72.8% |
| **Ensemble + neutral recalibration + brand-risk lexicon (deployed)** | **89.2%** | **87.4%** | **76.0%** | **75.9%** |

**Recalibration (after error analysis).** On the real comments, v1 labelled 40% of the negatives (19 of 47) as
neutral: the tweet-trained models treat complaints, price grumbles and negative news ("Zomato lays off 250
employees", "way too expensive") as neutral statements. Two changes fixed most of it: neutral's probability is
scaled by 0.6 before the decision, and a small English brand-risk lexicon (layoffs, scam, lawsuit, outage, too
expensive, ...) plus the Hinglish comparison idiom "isse acha toh X" ("X is better than this") were added.
Negatives caught on the real set rose from 26 to 33 of 47 with no extra positive↔negative swaps (2 before and
after). Caveat: some lexicon terms were chosen after reading the real-set errors, so the real-set gain is
slightly optimistic; the domain and App Store sets improved as well. App Store accuracy rose from 79.7% to 83.6%;
many remaining App Store "errors" are reviews whose text contradicts their star rating ("The app is so Worst"
with 5 stars), so that set has a noisy ceiling.

Aspect detection on the domain set: precision 0.90, recall 0.73, F1 0.81.
Inference on a laptop CPU (both models): about 32 ms per comment in batches on the domain set, about 120 ms on the longer real comments; about 140 ms for a single comment from the Analyze Text page. App Store reviews: predictions agree with the reviewer's star rating for 83.6% of reviews (79.7% in v1).
On the live simulated stream, the model agreed with the generator's intended label for 87% of 22,299 mentions.

Limitations to report honestly: the test set is small; mixed opinions ("tasty food but late delivery") are usually classified
negative; some Hinglish complaints about price ("bahut mehenga hai") are still missed; the simulator's templates are written
by the team, so the live agreement number is optimistic. Twitter/X search needs a paid API tier, and Reddit blocks unauthenticated access.

## Dashboard login

Set `ADMIN_PASSWORD` (and optionally `ADMIN_USERNAME`, default `admin`) in `backend/.env` to require sign-in.
Leave it empty for open access during development.

- **Accounts and roles.** The `.env` account is created as the first **admin**. Anyone can **sign up** from the
  login screen and becomes a **viewer**: every page and Analyze Text work, but changes (settings, sources, crisis
  simulation, deleting data) are refused with 403. Admins promote, demote and delete users under
  **Settings → Users**; at least one admin always remains. Set `ALLOW_SIGNUP=false` to disable sign-up.
  For a review, create a read-only account for examiners (for example `jury`) so they can explore on their own
  devices without changing anything.
- **Storage.** Accounts live in `backend/data/users.db`, separate from the mention database, so the real (8000)
  and demo (8001) instances share them. Passwords are hashed with PBKDF2-HMAC-SHA256 (200,000 iterations,
  random 16-byte salt).
- **Sessions.** A signed, HttpOnly, SameSite cookie (HMAC-SHA256 with a server key in `data/session.key`,
  12-hour expiry). Changing a password or deleting a user ends that user's sessions. Every `/api` call and the
  live WebSocket require a session; five failed attempts lock a client out for five minutes.

## Testing

```bash
cd backend
..\env\Scripts\pip install -r requirements-dev.txt
..\env\Scripts\python -m pytest tests -q          # 52 unit tests: preprocessing, aspects, lexicon, anomaly, risk, accounts, explanation, CSV
..\env\Scripts\python -m scripts.smoke_test       # 23 end-to-end API tests against a running server
```

## Configuration

Copy `backend/.env.example` to `backend/.env` for API keys (Reddit, Twitter, Instagram), SMTP email, Slack/Teams webhooks, Twilio SMS, or Kafka.
Brand name, keywords, sources, aspects, thresholds and notification channels can also be changed from the **Settings** page.

## Project layout

```
backend/
  app/            FastAPI application (api, collectors, nlp, analytics, alerts, pipeline)
  eval/           labelled evaluation data
  scripts/        evaluate_model.py, smoke_test.py
  tests/          pytest unit tests
  data/           SQLite database + evaluation results (created at runtime)
frontend/         React dashboard (Vite)
deploy/           Ubuntu server + Hugging Face Spaces deployment
docs/             SRS, report, paper, UML, presentation, user manual
start.bat         one-click start on Windows
docker-compose.yml  Kafka + backend
legacy/           earlier Flask prototype (phase 1), kept for reference only
```
