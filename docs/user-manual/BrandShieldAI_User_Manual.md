# BrandShield AI – User Manual

**Real-Time Brand Risk and Sentiment Intelligence System**

Version 1.0 (draft) · 2025

**Team:** Soham Borse, Tanish Bantwal, Aryan Baakle, Omsingh Rajput

**Guide:** Dr. D. V. Medhane

Department of Artificial Intelligence and Data Science, K. K. Wagh Institute of Engineering Education and Research, Nashik

---

## Contents

1. [What BrandShield AI does](#1-what-brandshield-ai-does)
2. [Before you start](#2-before-you-start)
3. [Installing and starting the system](#3-installing-and-starting-the-system)
4. [A quick tour of the screen](#4-a-quick-tour-of-the-screen)
5. [Page-by-page guide](#5-page-by-page-guide)
6. [Connecting your data sources](#6-connecting-your-data-sources)
7. [Alerts and notifications](#7-alerts-and-notifications)
8. [Settings](#8-settings)
9. [Running a demonstration](#9-running-a-demonstration)
10. [Understanding the numbers](#10-understanding-the-numbers)
11. [Troubleshooting](#11-troubleshooting)
12. [Frequently asked questions](#12-frequently-asked-questions)
13. [Known limitations](#13-known-limitations)
14. [Glossary](#14-glossary)

---

## 1. What BrandShield AI does

BrandShield AI keeps an eye on what people say about your brand online, so you don't have to read every comment yourself.

It works in five steps, automatically and continuously:

1. **Collects** public comments about your brand from YouTube, Instagram, Google News and App Store reviews.
2. **Reads** every comment with an AI model and marks it as positive, neutral or negative. It understands English, Hinglish (Hindi written in English letters), Hindi and Marathi.
3. **Explains** what each comment is about, such as delivery, price, service or food quality. One comment can be positive about one thing and negative about another.
4. **Watches for trouble.** If complaints suddenly rise, it notices within minutes and calculates a risk score from 0 to 100.
5. **Alerts you** on the dashboard and, if you want, by email, Slack, Microsoft Teams or SMS.

**Who this manual is for**

| You are… | Read especially |
|---|---|
| A brand manager or analyst who uses the dashboard | Sections 4, 5, 7, 10 |
| The person who installs and runs the system (the operator) | Sections 2, 3, 6, 8, 11 |
| A faculty member or evaluator watching a demo | Sections 9 and 10 |

> **Tip:** Almost everything on the dashboard explains itself. Hover the mouse over any number, chart title (ⓘ icon), badge or menu item to see a short explanation.

---

## 2. Before you start

### 2.1 Computer requirements

| Item | Minimum | Recommended |
|---|---|---|
| Operating system | Windows 10/11, or Ubuntu 22.04/24.04 | Windows 11 or Ubuntu 24.04 |
| Processor | 2 cores, 64-bit | 4 cores or more |
| Memory (RAM) | 4 GB | 8 GB or more |
| Free disk space | 5 GB | 25 GB (server) |
| Graphics card (GPU) | Not needed | Not needed |
| Internet | Needed on first start and for live data | Broadband |
| Browser | Chrome, Edge, Firefox or Safari (recent version) | Chrome or Edge |

### 2.2 Software you need

- **Python 3.12 or later** — [python.org/downloads](https://www.python.org/downloads/). During installation on Windows, tick **"Add Python to PATH"**.
- **Node.js 20 or later** — [nodejs.org](https://nodejs.org/). Only needed the first time, to build the dashboard.

### 2.3 Accounts and keys (optional)

The system works without any keys: it can run on demo data and Google News straight away. For real social media data you will need:

| Source | What you need | Cost |
|---|---|---|
| YouTube | A YouTube Data API key | Free |
| Instagram | An Instagram Business or Creator account and a Meta developer app | Free |
| App Store reviews | Nothing | Free |
| Google News | Nothing | Free |
| Email alerts | An email account with SMTP access (e.g. a Gmail App Password) | Free |
| Slack / Teams alerts | An incoming webhook URL | Free |
| SMS alerts | A Twilio account | Paid |

---

## 3. Installing and starting the system

### 3.1 First-time start on Windows (recommended)

1. Copy the project folder to your computer, for example to the Desktop.
2. Open the folder and **double-click `start.bat`**.
3. Wait. The first start:
   - creates a Python environment and installs the required packages,
   - builds the dashboard,
   - downloads the AI models (about 1.6 GB),
   - generates 3 days of demo history.

   This takes **about 5–10 minutes** depending on your internet speed. Later starts take under a minute.
4. Your browser opens **http://127.0.0.1:8000** automatically. If it doesn't, type that address into the browser.

> **Keep the black command window open.** Closing it stops BrandShield AI.

`[Screenshot placeholder: command window during first start]`

### 3.2 What you see while it starts

At the top of the dashboard you may see temporary badges:

| Badge | Meaning | What to do |
|---|---|---|
| **Loading AI model…** | The AI models are loading (about 30–60 seconds) | Wait |
| **Generating history NN%** | Demo history is being created (first start only) | Wait until it disappears |

Pages still open during this time, but some numbers may be empty until loading finishes.

### 3.3 Stopping the system

Close the command window, or press **Ctrl + C** inside it. All your data is saved and will be there the next time you start.

### 3.4 Opening the dashboard on your phone

Double-click **`start-public.bat`** instead of `start.bat`. It creates a temporary public web address (shown in the window) that you can open on any phone or laptop. Anyone with the link can view the dashboard, so close the window when you are done.

### 3.5 Running on a server (always on)

To keep BrandShield AI running permanently on the internet, follow `deploy/DEPLOY.md`. On a fresh Ubuntu server a single command installs everything, including HTTPS:

```bash
sudo bash deploy/install.sh yourdomain.com you@email.com
```

---

## 4. A quick tour of the screen

`[Screenshot placeholder: full dashboard with numbered callouts 1–6]`

| # | Area | What it is |
|---|---|---|
| 1 | **Top menu** (under the BrandShield name) | Moves between pages. A red number on **Alerts** shows how many alerts are open. The **Night / Day** button next to LIVE switches between dark and light theme. |
| 2 | **Status box** (bottom left) | Green dot = live connection working. Also shows the AI model status and the total number of comments analysed. |
| 3 | **Top bar** | The brand being monitored and the green **LIVE** badge. A red **Simulated … crisis** badge appears while a demo crisis is running. |
| 4 | **Page intro strip** | A one-line explanation of the current page. Click **×** to hide it. |
| 5 | **Time window selector** (6h / 24h / 3d / 7d / 30d) | Changes the period used for every number and chart on the page. |
| 6 | **Pop-up notifications** (top right) | New alerts appear here as they happen. |

**The dashboard updates by itself.** New comments, risk changes and alerts arrive automatically. You never need to refresh the page.

**Colours mean the same thing everywhere:**

| Colour | Meaning |
|---|---|
| Green | Positive |
| Grey | Neutral |
| Red | Negative |
| Amber | Spam, or a warning |

---

## 5. Page-by-page guide

### 5.1 Dashboard

`[Screenshot placeholder: Dashboard]`

**Use it to answer:** "How are we doing right now?"

| Part | What it shows |
|---|---|
| **Six stat cards** | Brand health, number of mentions, positive %, negative %, spam filtered, and risk score. The small badge on each card compares with the previous period of the same length (▲ up, ▼ down). Green means the change is good, red means it is bad. |
| **Summary** | A few plain-English sentences describing the main changes. |
| **Sentiment over time** | Positive, neutral and negative comments over time. Red markers highlight unusual periods. |
| **Sentiment distribution** | The overall split between positive, neutral, negative and spam. |
| **Brand risk** | The risk gauge and the five signals that make up the score. Underneath, it shows how many comments the score is based on. |
| **Topic insights** | Topics people mention most and how they feel about each. |
| **Active alerts** | Alerts nobody has handled yet. |
| **Live mention feed** | The newest comments, a few seconds after they arrive. |
| **Trending words** | The most frequent words in recent comments. |

### 5.2 YouTube

**Use it to:** monitor the comments on a YouTube channel.

- Shows the channel's details and the overall sentiment of its audience.
- Lists recent videos with the sentiment of their comments. **Click a video** to read its analysed comments.
- **Sync now** fetches new comments immediately; otherwise the system checks every 5 minutes.

Setup is described in [Section 6.1](#61-youtube).

### 5.3 Instagram

**Use it to:** monitor comments on your own Instagram Business or Creator account.

- Shows the connected profile and each post with the sentiment of its comments. **Click a post** to read its comments.
- **Use only real data** removes all demo data, so the dashboard shows only your real comments.

Setup is described in [Section 6.2](#62-instagram).

### 5.4 Mentions

**Use it to:** find the exact comments behind a number or a spike.

1. Use the filters at the top: **search text or author**, sentiment, source, aspect (topic), language, spam, and real or demo data.
2. Results appear 30 per page, newest first.
3. **Click a comment** to see:
   - the probability of each sentiment class,
   - the topics found and the sentiment of each,
   - the reason it was marked as spam, if it was,
   - a link to the original post, where available.

> **Tip:** Many charts link here. Clicking an aspect on the Dashboard opens Mentions already filtered to that topic.

### 5.5 Trends & Forecast

**Use it to:** understand spikes, the risk score and where sentiment is heading.

| Part | What it shows |
|---|---|
| **Anomaly detection** | Comments in 15-minute intervals. Intervals where negativity jumped unusually are highlighted. |
| **Detected incidents** | Unusual intervals grouped into incidents, with start, end and peak negative share. |
| **Risk breakdown** | Each of the five risk signals and its points. Hover over a signal for an explanation. |
| **Forecast** | The expected sentiment, negative share and volume for the next 12 hours, with a shaded band showing the uncertainty. |
| **Languages** | Languages detected in the comments. |

### 5.6 Topics

**Use it to:** see *why* people are happy or unhappy.

- One card per topic, showing the number of mentions, average score (−1 to +1), number of complaints, and the change compared with the previous period.
- **Sentiment by aspect** compares all topics side by side.
- **Top complaint terms** and **Top praise terms** list the words used most in negative and positive comments.

### 5.7 Alerts

**Use it to:** work through problems the system detected.

1. Use the filter to show **Open**, **Acknowledged**, **Dismissed** or all alerts.
2. Read the alert title and message. Each alert has a severity: **low**, **medium**, **high** or **critical**.
3. Choose an action:
   - **Acknowledge** — "I've seen it and I'm handling it."
   - **Dismiss** — "Not a real problem."
   - **Reopen** — bring back a dismissed or acknowledged alert.
4. Click **Enable browser notifications** on this page, so high and critical alerts pop up even when the tab is in the background.

See [Section 7](#7-alerts-and-notifications) for the types of alerts.

### 5.8 Analyze Text

**Use it to:** test the AI on any comment, or import a file of comments.

**Analyse one comment**
1. Type or paste a comment (up to 5,000 characters) in English, Hinglish, Hindi or Marathi.
2. Click **Analyze**.
3. The result shows every step: cleaned text, words, language, spam check, the probability of each sentiment, the final label, and the sentiment for each topic with the part of the sentence it came from.
4. Tick **Save to dashboard** if you want the comment saved and counted in the dashboards.

> **Tip:** The small example buttons under the text box fill in sample comments for you.

**Try these examples:**

| Comment | What you will see |
|---|---|
| `Food was great but delivery was late` | Food: positive, delivery: negative |
| `khana bahut badhiya tha, service bhi achhi thi` | Positive (Hinglish) |
| `खाना बहुत बढ़िया था` | Positive (Hindi) |
| `Ordered at 8 pm, it arrived at 9 pm` | Neutral (a fact, not an opinion) |

**Import comments from a CSV file**
1. Under **Bulk import**, click **Choose CSV** and select your file.
2. File requirements:
   - CSV format, saved as **UTF-8**,
   - at most **20 MB** and **50,000 rows**,
   - one column named `text` or `comment` containing the comment,
   - optional columns: `timestamp`, `author`, `source`, `engagement` (likes).
3. The system queues the rows and analyses them in the background. They appear in the dashboards with their own dates.
4. Uploading the same file twice is safe: duplicates are ignored.

### 5.9 Performance

**Use it to:** check that the system is fast and accurate.

| Part | What it shows |
|---|---|
| **Throughput, latency, inference time** | How many comments per second are processed, and how long each one takes. |
| **Queue depth, errors** | Comments waiting to be processed, and any processing errors. Both should normally be 0 or close to it. |
| **Evaluation results** | Accuracy, precision, recall and F1 of the AI model, measured on comments labelled by people. Includes a confusion matrix. |
| **Run on domain set** | Re-runs the accuracy test on the labelled comments (takes about a minute). |

### 5.10 Settings

See [Section 8](#8-settings).

---

## 6. Connecting your data sources

> **Important:** Saving API keys and starting the secure address only works from the computer running BrandShield AI (the browser address must be `127.0.0.1`). This stops other people from changing your keys through a public link.

### 6.1 YouTube

**You need:** a free YouTube Data API key.

**Get the key (about 3 minutes, no payment card needed):**
1. Go to [console.cloud.google.com](https://console.cloud.google.com/) and sign in with a Google account.
2. Create a project (any name).
3. Open **APIs & Services → Library**, search for **YouTube Data API v3** and click **Enable**.
4. Open **APIs & Services → Credentials → Create credentials → API key**, then copy the key.

**Add a channel:**
1. Open the **YouTube** page in BrandShield AI.
2. Paste the key and click **Save key**.
3. In **Add a channel**, type a handle (e.g. `@mkbhd`), a channel URL, a channel ID or a channel name, then click **Monitor channel**.
4. The system imports the channel's recent videos and their comments. This takes about a minute.

After that, new comments are collected every 5 minutes.

> **Quota:** a free key allows 10,000 units a day, which is plenty for one channel. If the quota runs out, the page tells you when it resets (12:30 PM IST). The system only re-downloads comments for videos that changed, to save quota.

### 6.2 Instagram

**You need:**
- an Instagram **Business** or **Creator** account (free to switch: Instagram app → Settings → Account type),
- a Meta developer app (free).

The Instagram page guides you through these steps:

1. **Create a Meta app** at [developers.facebook.com/apps](https://developers.facebook.com/apps). Choose the use case *Manage messaging and content on Instagram* and the type **Business**. Open **Instagram → API setup with Instagram login** and copy the **Instagram app ID** and **app secret**.
2. **Save the keys:** paste both into the Instagram page and click **Save keys**.
3. **Start the secure address:** click **Start secure address**. Instagram only accepts secure (https) addresses, so BrandShield creates a temporary one. Copy the **redirect URI** shown on the page into your Meta app under *Business login settings → OAuth redirect URIs*. It must match **exactly**.
4. **Allow your account:** in the Meta app, add your Instagram account under **App roles → Roles** as an **Instagram Tester**, then accept the invitation in Instagram (Settings → Website permissions → Apps and websites).
5. **Connect:** click **Continue with Instagram**, log in on instagram.com, and click **Allow**.

Your profile, posts and comments are imported within about a minute. After that, new comments are collected every 3 minutes.

> **Your password is safe.** You log in on instagram.com itself; BrandShield never sees or stores your password. It only receives an access token, which is stored encrypted and renewed automatically.

> **What Instagram allows:** comments on *your own* account's posts only. You cannot monitor another brand's Instagram through the official API.

### 6.3 App Store reviews and Google News

These need no keys.

1. Open **Server setup → Data sources** (link at the bottom of the Settings page) and switch on **App Store reviews** and/or **News / RSS**.
2. For App Store reviews, you can optionally set the country code (e.g. `in`) and the app ID under **Server setup → API keys**. If you leave the app ID empty, the system finds the app by your brand name.

### 6.4 Pushing data from another system (for developers)

Other software can send comments directly:

```http
POST http://127.0.0.1:8000/api/ingest
Content-Type: application/json

{"items": [{"text": "Great service today!", "source": "website", "author": "Asha"}]}
```

Full interactive API documentation is available at **http://127.0.0.1:8000/docs**.

---

## 7. Alerts and notifications

### 7.1 Types of alerts

| Alert | When it is raised |
|---|---|
| **Sudden spike in negative sentiment** | The share of negative comments jumps far above normal. |
| **Brand risk score reached N/100** | The risk score crosses your alert threshold (default 60). |
| **Negative sentiment increased** | Negative comments stay above the set share (default 35%). |
| **Multiple [topic] complaints detected** | Complaints about one topic, e.g. delivery, suddenly increase. |
| **Sentiment forecast declining** | The forecast predicts sentiment will fall below the set level. |
| **Spam wave** | An unusual number of spam comments arrive within an hour. |
| **Negative post is going viral** | A single negative comment gets a lot of likes or engagement. |

The same problem does not create repeated alerts. After an alert, the same type of alert waits **30 minutes** (adjustable) before it can be raised again.

### 7.2 Severity levels

| Severity | Meaning |
|---|---|
| **Low** | Worth knowing; no action needed yet. |
| **Medium** | Keep an eye on it. |
| **High** | Should be looked at soon. |
| **Critical** | Likely PR problem; respond now. |

### 7.3 Getting alerts outside the dashboard

Alerts always appear on the dashboard. To also receive them by email, Slack, Teams or SMS:

1. Open `backend/.env` in a text editor (copy it from `backend/.env.example` if it doesn't exist) and fill in the details for the channels you want:

   | Channel | Settings in `backend/.env` |
   |---|---|
   | Email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `ALERT_EMAIL_TO` (for Gmail use `smtp.gmail.com` and an App Password) |
   | Slack | `SLACK_WEBHOOK_URL` |
   | Microsoft Teams | `TEAMS_WEBHOOK_URL` |
   | SMS | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` |

2. Restart BrandShield AI.
3. Open **Settings → Notifications**, switch on the channels you want, and choose the **minimum severity** to send (default: high).
4. Click **Send test** to check that messages arrive.

---

## 8. Settings

All settings take effect immediately. You don't need to restart.

| Section | What you can change |
|---|---|
| **Brand** | The brand name and the keywords used to find mentions of it. Type a keyword and press **Enter** to add it. |
| **Crisis simulation** | Moved to **Server setup → Demo tools** (see [Section 9](#9-running-a-demonstration)). |
| **Data sources** | Switch each source on or off. Sources that need a key say so. |
| **API keys** | Keys for YouTube, Reddit, Twitter/X and App Store options. Saved keys are never shown again, only marked as set. |
| **Alert thresholds** | When alerts are raised (see the table below). |
| **Notifications** | Which channels receive alerts and the minimum severity. |
| **Aspects** | The topics the system looks for and the keywords for each topic. Add a new topic (e.g. *parking*) or new keywords at any time. |
| **Danger zone** | **Reset data & regenerate demo history** deletes all comments and alerts and creates fresh demo data. This cannot be undone. |

**Alert thresholds**

| Setting | Default | Meaning |
|---|---|---|
| Risk score alert | 60 | Raise an alert when the risk score reaches this value. |
| Negative share alert | 0.35 | Raise an alert when 35% or more of recent comments are negative. |
| Min. negatives before alerting | 5 | Ignore spikes with fewer negative comments than this. |
| Isolation Forest contamination | 0.05 | Roughly what fraction of periods the anomaly model may treat as unusual. Lower values mean fewer, stronger alerts. |
| Adaptive z-score threshold | 2.5 | How far above normal negativity must rise to count as a spike. Higher values mean fewer alerts. |
| Viral post engagement | 500 | Likes/engagement at which a negative comment counts as going viral. |
| Spam wave (per hour) | 40 | Spam comments per hour that trigger a spam-wave alert. |
| Alert cool-down (minutes) | 30 | Waiting time before the same alert can repeat. |
| Forecast sentiment floor | 0.0 | Alert if the forecast falls below this sentiment score. |

> **Tip:** If you get too many alerts, raise the risk score alert or the z-score threshold first.

---

## 9. Running a demonstration

### 9.1 Recommended setup

Double-click **`start-demo.bat`**. It starts two copies side by side:

| Address | Contains | Use it for |
|---|---|---|
| **http://127.0.0.1:8000** | Your real data | Showing real YouTube, news and App Store comments |
| **http://127.0.0.1:8001** | A fresh demo dataset with 3 days of history | Showing a live crisis being detected |

Wait about **5 minutes** for the demo copy to finish generating its history (watch the progress badge). The demo copy never changes your real data.

### 9.2 Showing a live crisis

1. In the **8001** tab, open **Server setup → Demo tools** (link at the bottom of the Settings page) and make sure **Live simulator** is switched on under Data sources.
2. Choose the aspect **Delivery**, set **intensity 1.0** and **20 minutes**, then click **Start crisis**.
3. Go to the **Dashboard** and talk through what is happening while it builds up:
   - within about **1–2 minutes**, a *"Multiple delivery complaints detected"* alert pops up;
   - within about **3 minutes**, the risk score rises to **High** and *"Sudden spike in negative sentiment"* appears.
4. Open **Trends & Forecast** to show the highlighted spike and the incident.
5. Click **Stop** in Settings when done, or let it end by itself.

If no alert appears after a few minutes, a previous crisis on the same topic may still be in its 30-minute cool-down. Choose **Service** instead.

### 9.3 Suggested 10-minute demo

| Minutes | Show |
|---|---|
| 0–1 | The problem: brands find out about complaint waves too late, and existing tools don't explain why. |
| 1–3 | Real data (8000): Dashboard, YouTube page, Mentions filtered to negative comments. |
| 3–7 | Live crisis (8001), as in Section 9.2. |
| 7–9 | Analyze Text, using the examples in Section 5.8. |
| 9–10 | Performance page: accuracy and the confusion matrix. |

---

## 10. Understanding the numbers

### 10.1 Sentiment label and score

Every comment gets:
- a **label**: positive, neutral or negative,
- a **confidence**: how sure the AI is (0–100%),
- a **score** from **−1** (very negative) to **+1** (very positive).

### 10.2 Brand health (0–100)

The average mood of all comments in the selected window. **50 is neutral.** Above 50 means people are mostly positive, below 50 mostly negative.

### 10.3 Risk score (0–100)

How likely a PR problem is right now. It adds up five signals:

| Signal | Max points | Measures |
|---|---|---|
| Negativity | 35 | How negative recent comments are, and how much more negative than usual |
| Velocity | 20 | How quickly negative comments are increasing |
| Anomaly | 25 | Whether the anomaly detector flagged an abnormal spike |
| Forecast | 10 | Whether sentiment is predicted to fall over the next hours |
| Concentration | 10 | Whether most complaints are about one topic |

| Score | Level |
|---|---|
| 0–29 | Low |
| 30–54 | Medium |
| 55–74 | High |
| 75–100 | Critical |

Because no single signal can give more than 35 points, a high score only appears when several signals agree. This avoids false alarms.

**Quiet channels:** the score is based on at least 20 recent comments. On a busy brand that is the last hour; on a quiet channel the system looks further back, up to 24 hours. The dashboard always shows how many comments the score is based on, for example *"Based on 22 mentions in the last 7 h"*.

### 10.4 Aspects (topics)

The default topics are **food quality, service, delivery, price, ambience, hygiene, app experience and packaging**. You can change them in **Settings → Aspects**. A comment is split at words like *but*, *however*, *lekin* and *par*, and each part is judged separately.

### 10.5 Model accuracy terms

| Term | Meaning |
|---|---|
| Accuracy | Share of test comments where the AI's label matched the human label |
| Precision | When the AI says "negative", how often it is right |
| Recall | Of all truly negative comments, how many the AI found |
| F1 | A balance of precision and recall (higher is better) |
| Confusion matrix | A table of true labels (rows) against predicted labels (columns); the diagonal is correct |

---

## 11. Troubleshooting

| Problem | Likely cause | Solution |
|---|---|---|
| Browser says "This site can't be reached" | The system is not running, or is still starting | Check that the command window is open. Wait 30 seconds and refresh. |
| "Loading AI model…" doesn't go away | The model is downloading on the first start | Wait. On a slow connection the first download can take 10+ minutes. |
| Numbers are empty or show "–" | No comments in the selected time window | Choose a longer window (e.g. 7d), or check that a data source is switched on. |
| Status box shows "Reconnecting…" | The live connection dropped | It reconnects by itself within seconds. If not, refresh the page. |
| YouTube: "quota is used up" | The daily free limit was reached | Wait until it resets (12:30 PM IST), or use another key. |
| YouTube: "channel not found" | Typo in the handle | Use the exact handle with `@`, or paste the channel URL. |
| Instagram: "Invalid redirect_uri" | The redirect URI in the Meta app doesn't match exactly | Copy it again from the Instagram page and paste it into the Meta app, including `https://`. |
| Instagram: "Only Business or Creator accounts…" | A personal account was used | Switch the account type in the Instagram app (free). |
| Saving keys gives "403" or "not allowed" | You are using the public link or another device | Open `http://127.0.0.1:8000` on the computer running BrandShield. |
| CSV upload fails | Wrong encoding or no text column | Save the file as **CSV UTF-8** and make sure one column contains the comment text. |
| No crisis alert in the demo | Alert cool-down from a previous run | Choose a different aspect, or wait 30 minutes. |
| Email/Slack alerts don't arrive | Missing or wrong settings in `backend/.env` | Check the values, restart, then use **Send test** in Settings. |

If a problem continues, look at the messages in the command window. They usually say what went wrong.

---

## 12. Frequently asked questions

**Does it need a GPU or an expensive computer?**
No. It runs on an ordinary laptop processor and uses about 2 GB of memory.

**Which languages does it understand?**
English, Hinglish, Hindi and Marathi (in both English and Devanagari letters) are specifically supported. Comments in many other languages are also classified by the multilingual model, without the extra Indian-language word list.

**Can it monitor a competitor?**
On YouTube, App Store and Google News, yes: these are public. On Instagram, no: the official API only gives access to your own account.

**Is my data shared with anyone?**
No. Everything is stored in a database file on your own computer (`backend/data/brandshield.db`). Comments are only fetched from the platforms, never posted.

**Does it reply to customers?**
No. It informs you; replying is up to you.

**How accurate is it?**
About 78% on our multilingual test set, and 81% agreement with App Store star ratings. See [Section 13](#13-known-limitations) for its weak spots.

**Can I add my own topics?**
Yes. Go to **Settings → Aspects** and add a topic name and its keywords.

---

## 13. Known limitations

- **Mixed comments** such as *"tasty food but late delivery"* usually get an overall **negative** label. The topic-level result (food positive, delivery negative) is correct, so use the topic view for these.
- **Some Hinglish slang and price complaints** are not always recognised, e.g. *"bahut mehenga hai"*.
- **Topics are found by keywords.** Words not in the topic list are missed until you add them in Settings.
- **Instagram** is limited to your own account's posts.
- **Twitter/X** needs a paid API plan; **Reddit** needs its own API keys.
- **One brand per installation**, and there are no user logins yet. Anyone who can open the dashboard can use it, so don't share the public link widely.
- The accuracy figures come from a **small test set** (83 comments) and should be treated as preliminary.

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **Mention** | Any comment, review or article that talks about the brand. |
| **Sentiment** | Whether a comment is positive, neutral or negative. |
| **Aspect** | A topic a comment talks about, e.g. delivery or price. |
| **Hinglish** | Hindi written in English letters, often mixed with English words. |
| **Spam** | Promotional or bot comments; excluded from all statistics. |
| **Anomaly** | A time period that looks very different from normal. |
| **Incident** | Several unusual periods in a row, grouped together. |
| **Isolation Forest** | The machine-learning method used to spot unusual periods. |
| **Forecast** | The system's prediction of sentiment for the next few hours. |
| **Risk score** | A 0–100 summary of how likely a PR problem is right now. |
| **Cool-down** | Waiting time before the same alert can be raised again. |
| **API key** | A password-like code that lets the system read data from a platform. |
| **Webhook** | A web address that Slack or Teams provides so the system can post messages to a channel. |
| **Live data / demo data** | Real comments from connected sources / simulated comments used for demonstrations. |

---

*BrandShield AI · Department of Artificial Intelligence and Data Science · K. K. Wagh Institute of Engineering Education and Research, Nashik*
