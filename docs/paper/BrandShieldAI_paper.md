# BrandShield AI: A Real-Time Multilingual Pipeline for Aspect-Based Brand Sentiment Analysis and Crisis Detection on Social Media

**Soham Borse, Tanish Bantwal, Aryan Baakle, Omsingh Rajput**
Department of Artificial Intelligence and Data Science
K. K. Wagh Institute of Engineering Education and Research, Nashik, Maharashtra, India

**Guide:** Dr. Darshan Medhane

---

## Abstract

Online brand reputation can deteriorate within hours, yet most organisations still monitor social
platforms manually or with tools that report sentiment only after the fact. This paper presents
**BrandShield AI**, an end-to-end system that ingests public social-media conversation in real time,
classifies it with a multilingual transformer, decomposes opinion by aspect, and detects reputation
crises before they escalate. The system combines four stages in a single streaming pipeline:
(i) collection from YouTube, Instagram, news feeds and app-store reviews through official APIs;
(ii) a hybrid classifier that averages two BERT-family encoders fine-tuned on social-media text (RoBERTa
and multilingual XLM-RoBERTa) and blends them with a code-mixed opinion lexicon
and a confidence-margin rule for the neutral class; (iii) clause-level aspect-based sentiment analysis
over a configurable aspect lexicon; and (iv) crisis detection that couples an Isolation Forest over
time-bucketed features with an adaptive median/MAD threshold on the *negative share*, followed by
Prophet-based forecasting and a five-signal risk score.

On a hand-labelled multilingual benchmark of 83 brand comments spanning English, Hinglish, Hindi and
Marathi, the hybrid classifier reaches **83.1% accuracy and 81.7% macro-F1**, while aspect detection
attains **F1 = 0.806**. On 200 real comments sampled at random from the live system it reaches
**74.0% accuracy**, against 66.5% for the DistilBERT model we first deployed — a gap our team-written
benchmark had hidden. Against an independent external signal — 483 App Store reviews with
user-assigned star ratings — predictions agree **79.7%** of the time. The deployed system analysed
**12,174 real comments** collected from YouTube, Instagram, news feeds and app stores on commodity CPU
hardware, with no GPU. In a controlled crisis experiment, the detector raised its first alert **24 seconds** after a negative-sentiment surge began, driving the brand-risk score from 20 to 79 out of 100.

**Keywords:** brand reputation management, sentiment analysis, aspect-based sentiment analysis,
BERT, RoBERTa, XLM-RoBERTa, anomaly detection, Isolation Forest, time-series forecasting, code-mixed text, real-time
systems

---

## I. Introduction

Social platforms have become the primary channel through which customers express satisfaction and
dissatisfaction with brands. A single complaint can reach millions of viewers within hours, and the
window in which an organisation can respond effectively is correspondingly short. Traditional
reputation monitoring — staff reading mentions manually, or dashboards that summarise sentiment
retrospectively — is poorly matched to this timescale.

Three limitations recur in existing practice. **First**, most deployed tools report *polarity* but not
*cause*: knowing that 30% of mentions are negative does not tell a manager whether the problem is
delivery, pricing, or product quality. **Second**, commercial monitoring suites are priced for large
enterprises, placing them out of reach of the small and medium businesses that are most exposed to a
viral complaint. **Third**, sentiment models are typically trained and evaluated on monolingual English
corpora, whereas real conversation in markets such as India is heavily code-mixed, with Hinglish and
Devanagari-script comments appearing alongside English in the same thread.

This paper describes BrandShield AI, a system built to address these three gaps simultaneously. The
contributions are:

1. **A complete streaming architecture** in which collection, natural-language processing, analytics
   and alerting are decoupled through a message bus, allowing a slow or rate-limited platform API to
   degrade without stalling classification.
2. **A hybrid sentiment classifier** that averages two BERT-family encoders fine-tuned on tweets
   (RoBERTa and XLM-RoBERTa) and augments them with a Hinglish, Hindi and Marathi opinion lexicon and a
   confidence-margin rule for the neutral class, evaluated both on a team-written benchmark and on
   randomly sampled real comments.
3. **Clause-level aspect-based sentiment analysis** driven by a user-editable aspect lexicon, so that
   a mixed opinion such as *"the food was great but delivery was late"* contributes positively to one
   aspect and negatively to another.
4. **A two-signal crisis detector** that combines an unsupervised Isolation Forest with a robust
   median/MAD z-score computed on the *share* of negative mentions rather than their raw count, which
   we show removes the false positives that daily traffic seasonality otherwise induces.
5. **An evaluation on real data**, including an external validity check against user-assigned star
   ratings, and a controlled crisis-injection experiment that measures detection latency end to end.

The system runs without a GPU: the complete pipeline occupies about 2 GB of resident memory and
classifies a comment in 32–120 ms on a laptop CPU, which makes deployment on a commodity virtual machine costing a few
hundred rupees per month practical.

---

## II. Related Work

**Transformer-based sentiment classification.** BERT [1] established fine-tuned bidirectional
transformers as the standard approach to sentence-level sentiment classification. DistilBERT [2]
reduces parameters by approximately 40% and increases inference speed by approximately 60% while
retaining most of the accuracy. RoBERTa keeps the BERT architecture but improves pre-training, and
XLM-RoBERTa extends it to 100 languages; Cardiff NLP fine-tuned both on tweets (XLM-T, TimeLMs), which
matters for short, informal, emoji-heavy comments. Comparative studies of BERT, DistilBERT and RoBERTa for sentiment
tasks report modest accuracy differences relative to the large gap in computational cost.

**Lexicon and hybrid methods.** VADER [3] is a rule- and lexicon-based analyser tuned for social media
that remains competitive on short informal text and is markedly cheaper than a transformer. Recent
dashboards combine the two, using a lexicon for speed and a transformer for context. Our work differs
in *where* the lexicon is applied: rather than ensembling two general-purpose classifiers, we use a
narrow lexicon restricted to romanised Indian-language opinion words, applied as a corrective prior
where the multilingual transformer is weakest.

**Code-mixed sentiment.** Sentiment analysis of Hindi-English code-mixed text is an established
sub-problem [4], [5], with shared tasks demonstrating that models trained on monolingual corpora
degrade substantially on romanised, transliterated input. This motivates the lexicon component of our
classifier.

**Aspect-based sentiment analysis.** The SemEval ABSA tasks [6] formalised the extraction of aspect
terms and their polarities. Fully supervised neural ABSA requires aspect-annotated training data,
which is unavailable for an arbitrary brand's vocabulary. We therefore adopt a lightweight
lexicon-and-clause approach that a non-technical user can extend at runtime, trading some recall for
zero annotation cost and immediate configurability.

**Anomaly detection and forecasting.** Isolation Forest [7] isolates anomalies through random
partitioning and is well suited to unlabelled, multivariate, low-dimensional telemetry such as
per-interval mention statistics. Prophet [8] provides decomposable trend-and-seasonality forecasting
that is robust to missing data and interpretable by non-specialists. Both have been applied to social
data individually; our contribution is their combination with a direction-aware adaptive threshold
inside a single risk score.

**Research gap.** Prior systems typically deliver sentiment classification *or* forecasting *or*
anomaly detection. Few integrate aspect-level attribution with crisis detection in a live pipeline,
and fewer still are evaluated on code-mixed Indian-language brand conversation. BrandShield AI targets
precisely that intersection.

---

## III. System Architecture

The system is organised in six layers (Fig. 1).

**A. Collection layer.** Five collectors implement a common interface (`configured()`, `status()`,
`poll()`). Each returns raw mentions and is polled on its own schedule: YouTube every 300 s, Instagram
every 180 s, news and app-store feeds every 180 s. Adding a platform requires implementing the
interface only; the orchestrator is unchanged. All access is read-only and uses official APIs:
the YouTube Data API v3 (API key), the Instagram API with Instagram Login (OAuth 2.0, user consent),
Google News RSS, and the Apple App Store customer-review RSS feed.

**B. Streaming layer.** Collectors publish to a message bus rather than calling the classifier
directly. The bus has two interchangeable implementations — Apache Kafka [9] for distributed
deployment and an in-process asynchronous queue for single-node deployment — behind one interface.
This decoupling means an API stall or a burst of several thousand comments changes queue depth rather
than blocking ingestion.

**C. NLP processing layer.** A consumer drains the bus in batches of up to 32 messages and applies
preprocessing, sentiment classification and aspect extraction, then persists results.

**D. Analytics layer.** Every 30 s the system aggregates stored mentions into fixed time buckets,
scores them for anomalies, and recomputes the brand-risk score; forecasts are refreshed every 5 min.

**E. Alerting layer.** Six rules convert analytic state into alerts, each with a cool-down to prevent
duplicates. Alerts are pushed to connected dashboards over WebSocket and optionally to email, Slack,
Microsoft Teams or SMS.

**F. Presentation layer.** A React single-page application renders live dashboards; updates arrive by
WebSocket push rather than polling.

---

## IV. Methodology

### A. Preprocessing

Each mention passes through a deterministic pipeline: removal of URLs, @-mentions and HTML; hashtag
unwrapping (`#latedelivery` → `latedelivery`); collapsing of character runs (`sooooo` → `soo`);
mapping of 30 frequent emoji to their lexical equivalents (😡 → *angry*), since the model's tokenizer
represents most emoji as unknown tokens; tokenisation; stop-word removal with negation terms
explicitly retained; WordNet lemmatisation; and language identification.

A rule-based spam filter flags promotional and bot content using pattern families (follower-exchange
phrases, link-heavy posts, hashtag stuffing, all-caps with links). Spam is stored but excluded from
all sentiment statistics; spam is filtered before any statistic is computed.

### B. Hybrid Sentiment Classification

The base classifier averages two BERT-family encoders fine-tuned on tweets: XLM-RoBERTa
(multilingual) and RoBERTa (English). Each yields a distribution over positive, neutral and negative;
let $p_m = (p^+, p^0, p^-)$ denote their mean. If neither model can be loaded, a multilingual
DistilBERT with five ordinal classes, folded into three, is used as a fallback.

For code-mixed input we compute a lexicon polarity $\ell \in [-1, 1]$ as the mean signed weight of
matched opinion terms from a curated Hinglish, Hindi and Marathi lexicon, with negation inversion
inside a ±2-token window. When at least one term matches, the distributions are blended:

$$p = (1 - \lambda)\, p_m + \lambda \, p_\ell, \qquad \lambda = 0.35$$

where $p_\ell = (\max(\ell,0),\; 1 - |\ell|,\; \max(-\ell,0))$.

A neutral-margin rule then addresses the model's tendency to assign weak polarity to factual
statements. Let $p_{(1)} \ge p_{(2)}$ be the two largest class probabilities. If the top class is not
neutral, no lexicon term matched, and

$$p_{(1)} - p_{(2)} < \delta, \qquad \delta = 0.20$$

the prediction is reassigned to neutral. Finally a continuous sentiment score is defined as
$s = p^+ - p^- \in [-1, 1]$, which is the quantity aggregated in all downstream analytics.

Predictions are cached by normalised text, which matters because social streams contain many repeated
and near-duplicate comments.

### C. Aspect-Based Sentiment Analysis

Each mention is split into clauses at sentence delimiters and contrastive conjunctions (*but*,
*however*, *lekin*, *magar*, *par*). Aspects are detected per clause with whole-word matching against a
configurable lexicon of eight default aspects (food quality, service, delivery, price, ambience,
hygiene, app experience, packaging); whole-word matching avoids the substring errors that arise with
naive containment (e.g. *late* inside *chocolate*). Each aspect-bearing clause is then classified
independently by the same sentiment model, so a mixed opinion yields opposite polarities for different
aspects. Users can add, remove or extend aspects at runtime without redeployment.

### D. Crisis Detection

Mentions are aggregated into fixed $b$-minute buckets ($b = 15$ by default). For each bucket we
compute total volume, per-class counts, mean sentiment score, and the negative share
$r_t = n^-_t / n_t$.

Two detectors run in parallel. An **Isolation Forest** [7] is fitted over the trailing window using the
feature vector $\langle n_t,\, n^-_t,\, r_t,\, \bar{s}_t,\, \Delta n^-_t \rangle$, with anomaly scores
normalised to $[0,1]$. In parallel, a **robust z-score** is computed against a trailing baseline using
the median and median absolute deviation:

$$z_t = \frac{x_t - \operatorname{med}(x_{t-w:t-1})}{1.4826 \cdot \operatorname{MAD}(x_{t-w:t-1})}$$

A bucket is flagged only when the anomaly is *harmful* — that is, when the negative **share** deviates
upward, confirmed by the negative **count**:

$$\text{crisis}_t = (n^-_t \ge n_{\min}) \wedge \Big[ \big(\text{IF}_t \wedge z^r_t \ge \tau \wedge z^{n^-}_t \ge 0.6\tau\big) \vee \big(z^r_t \ge 1.6\tau \wedge z^{n^-}_t \ge \tau\big) \Big]$$

with $\tau = 2.5$ and $n_{\min} = 5$. Using the negative *share* as the primary signal is the design
decision that makes the detector usable: raw negative counts rise every day at lunch and evening peaks,
and a count-based threshold flags those normal peaks as crises (Section VI-F).

### E. Forecasting and Risk Scoring

Hourly series of mean sentiment, negative share and volume are forecast with Prophet [8]; when fewer
than 36 hourly observations are available, or Prophet fails to converge, the system falls back to Holt
linear smoothing with an empirical prediction interval.

The brand-risk score $R \in [0, 100]$ combines five bounded components:

$$R = \underbrace{35\,f_1}_{\text{negativity}} + \underbrace{20\,f_2}_{\text{velocity}} + \underbrace{25\,f_3}_{\text{anomaly}} + \underbrace{10\,f_4}_{\text{forecast}} + \underbrace{10\,f_5}_{\text{concentration}}$$

where $f_1$ measures the recent negative share and its lift over baseline, $f_2$ the negative-count
z-score, $f_3$ the Isolation Forest score when a bucket is flagged, $f_4$ the forecast decline over the
next six hours, and $f_5$ the share of complaints attributable to a single aspect. Scores map to four
levels (low, medium, high, critical). Requiring several independent signals to coincide before a high
score is reported is what suppresses single-signal false alarms.

A complementary **brand health** index is reported for readability as $H = 50 + 50\,\bar{s}$, where
$\bar{s}$ is mean sentiment over the selected window.

### F. Alerting

Six rules raise alerts: negative spike (anomaly confirmed), risk threshold crossed, sustained negative
ratio, aspect surge, forecast decline, spam wave, and virality of an individual negative post. Each
rule has a deduplication key and cool-down (default 30 min) so that one incident produces one alert
rather than a stream.

---

## V. Experimental Setup

### A. Hardware and Software

| Component | Development | Deployment (minimum) |
|---|---|---|
| Processor | AMD Ryzen 7 7435HS, 8C/16T, 3.1 GHz | 2 vCPU x86-64 |
| Memory | 24 GB | 4 GB (measured working set about 2 GB) |
| Storage | SSD | 25 GB (models 1.6 GB) |
| GPU | RTX 4050 (**unused**) | none required |
| OS | Windows 11 | Ubuntu 24.04 LTS |

Software: Python 3.14, FastAPI 0.141, PyTorch 2.14 (CPU build), Transformers 5.17, scikit-learn 1.9.1,
Prophet 1.4, NLTK 3.10, pandas 3.0.5, SQLite 3; React 19 with Chart.js 4.5 for the interface.

### B. Datasets

**D1 — Annotated benchmark (83 comments).** Brand comments hand-labelled as positive, neutral or
negative, deliberately constructed to include English, Hinglish, romanised and Devanagari Hindi,
Marathi, sarcasm, mixed opinions and spam. Aspect labels accompany 47 of the comments. The set is
small and single-annotator, which we treat as a limitation (Section VII).

**D2 — Live corpus (12,174 mentions).** Collected by the deployed system: 11,063 YouTube comments,
135 Instagram comments, 491 Google News articles, 483 Apple App Store reviews and 2 rows imported from
CSV. Language identification reports English alongside Indonesian, Spanish, Portuguese, Italian and
Arabic, confirming that a multilingual model is required in practice rather than in principle.

**D4 — Real-comment benchmark (200 comments).** Comments sampled at random from the live database
(110 YouTube, 60 Instagram, 30 news) and labelled by hand: 47 negative, 91 neutral, 62 positive.
Unlike D1, they were neither written nor selected by the team.

**D3 — External validation (483 reviews).** App Store reviews carry a user-assigned 1–5 star rating,
which we map to three classes (1–2 negative, 3 neutral, 4–5 positive) and treat as an independent
label produced by the reviewer rather than by the research team.

---

## VI. Results and Discussion

### A. Sentiment Classification and Ablation

| Configuration | Accuracy | Precision (macro) | Recall (macro) | F1 (macro) | F1 (weighted) |
|---|---|---|---|---|---|
| *D1, team-written benchmark* | | | | | |
| DistilBERT only | 0.7831 | 0.7735 | 0.7595 | 0.7647 | 0.7815 |
| DistilBERT hybrid | 0.7831 | 0.7838 | 0.7738 | 0.7764 | 0.7870 |
| Ensemble only | 0.8072 | 0.7918 | 0.7952 | 0.7904 | 0.8124 |
| **Ensemble hybrid (deployed)** | **0.8313** | **0.8174** | **0.8238** | **0.8174** | **0.8352** |
| *D4, random real comments* | | | | | |
| DistilBERT hybrid | 0.6650 | – | – | 0.6520 | – |
| **Ensemble hybrid (deployed)** | **0.7400** | **0.7844** | **0.7050** | **0.7276** | **0.7362** |

On D1 the lexicon-and-margin layer adds 2.4 points of accuracy and 2.7 points of macro-F1 to the
ensemble; the transformer does most of the work and the lexicon corrects a specific, identifiable
failure mode. The more consequential finding is the D1–D4 gap for DistilBERT: 78.3% on the
team-written benchmark but 66.5% on random real comments, where fan slang, emoji-only replies and
non-English comments dominate its errors. The ensemble narrows this gap (83.1% and 74.0%).

An earlier candidate model (a distilled multilingual student model) reached only 49.4% accuracy and
40.6% macro-F1 on D1. Model selection, rather than architectural novelty, accounted for the single
largest improvements in this project, provided it is validated on unselected real data rather than
on benchmarks alone.

### B. Per-Class Performance

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Negative | 0.967 | 0.829 | 0.892 | 35 |
| Neutral | 0.652 | 0.750 | 0.698 | 20 |
| Positive | 0.833 | 0.893 | 0.862 | 28 |

Confusion matrix (rows = true, columns = predicted):

| | Negative | Neutral | Positive |
|---|---|---|---|
| **Negative** | 29 | 5 | 1 |
| **Neutral** | 1 | 15 | 4 |
| **Positive** | 0 | 3 | 25 |

Only one of 35 negative comments on D1 (and two of 47 on D4) was classified as positive, and
negative precision is 0.97 on D1 and 0.87 on D4, so the system rarely reports a satisfied customer
where a dissatisfied one exists — the error direction that matters for a reputation-monitoring tool.
The commoner error on real data is a mild complaint labelled neutral (19 of 47 negatives on D4). The
neutral class is weakest on D1 (F1 = 0.698), consistent with the difficulty of separating factual
statements from mild opinion.

### C. Aspect Detection

Against the aspect-annotated subset of D1, lexicon-based aspect detection achieves **precision 0.900,
recall 0.730, F1 0.806**. Precision substantially exceeds recall, which is the desirable asymmetry
here: an aspect attributed to a complaint is almost always correct, while some complaints are recorded
without an aspect. Recall is bounded by vocabulary coverage, and the lexicon is user-extensible for
exactly this reason.

### D. External Validation Against Star Ratings

On D3, model predictions agree with reviewer-assigned star ratings for **385 of 483 reviews (79.7%)**; the DistilBERT model we first deployed agreed on 74.7%.
Because these labels are produced by the reviewers themselves and were never seen during development,
this is an independent check that the accuracy measured on D1 is not an artefact of the annotation
process.

### E. Throughput and Latency

Measured on the development CPU with batches of 32, the two-model ensemble needs **32.4 ms per
comment** on D1 and 120 ms on the longer D4 comments, about three times DistilBERT's cost;
single-comment interactive requests complete in approximately 140 ms including HTTP
overhead. The full pipeline occupies about 2 GB resident memory. The system processed a backlog of
more than 10,000 YouTube comments without a GPU, and repeated synchronisation of unchanged videos issues **zero** additional comment-API calls, a
quota optimisation without which the daily free quota would be exhausted within hours.

### F. Crisis Detection

**Controlled experiment.** In a controlled test, we injected a burst of delivery complaints into the live stream using the crisis simulator, on top of the real data. The first alert (*sudden spike in negative sentiment*) was raised 24 seconds after the burst began, at critical severity, and the risk score rose from 20 to 79 out of 100. In the same evaluation cycle the system also raised a risk-threshold alert, a negative-share alert and an aspect-surge alert for delivery, and Isolation Forest gave the window an anomaly score of 1.00, with 84% of its mentions negative. When the test was repeated while earlier alerts of the same types were less than 30 minutes old, those alerts were held back by the cool-down as intended, so one incident did not produce a stream of repeated alerts.

**Threshold ablation.** With the naive count-based rule, the detector flagged four additional
intervals over a three-day window in which the negative *share* was near baseline (approximately 30%
against a 20% baseline) and only the absolute count had risen with normal daily traffic. Switching the
primary signal to the negative share while retaining the count as confirmation eliminated all four
false positives and retained the true incident — the single most consequential tuning decision in the
detector.

### G. Discussion

Three observations stand out. First, aspect attribution changes what the operator sees: an overall
negative share is actionable only when the dashboard also reports *which* aspect is responsible.
Second, direction-awareness matters more than detector sophistication — the Isolation Forest alone was
not the difference between a usable and an unusable alarm; the share-based harmful-direction gate was.
Third, the CPU-only design is not a compromise imposed by budget but a consequence of model choice:
base-size BERT-family encoders keep the entire deployment within a 4 GB virtual machine while still
analysing several hundred comments per minute.

---

## VII. Limitations

We state limitations explicitly rather than in passing.

1. **Benchmark size.** D1 contains 83 comments annotated by the project team and D4 contains 200
   annotated by one person. Confidence intervals are wide (about ±6 points on D4), and the gain from
   the lexicon layer is not statistically established. A larger, multi-annotator set with inter-annotator agreement is the
   first priority for the extended version of this work.
2. **Mixed-opinion bias.** Comments combining praise and complaint (*"food was tasty but delivery was
   late"*) are labelled neutral in D1 but usually classified negative. Aspect-level output is correct
   in these cases even when the sentence-level label is not.
3. **Code-mixed price expressions.** Complaints such as *"bahut mehenga hai"* remain under-detected;
   the lexicon covers the term but the blending weight is insufficient to overturn a confident model
   prediction.
4. **Aspect recall.** Lexicon-based detection recovers 73% of annotated aspects; genuinely novel
   vocabulary is missed until a user extends the lexicon.
5. **Platform constraints.** The official Instagram API returns comments only for the connected
   account's own content. Public pages of other brands are therefore read through a third-party data
   service (Apify), which is limited to public accounts, returns about 15 newest comments per post, and
   is subject to that provider's quotas.
6. **Single-tenant deployment.** The current system serves one brand workspace without user accounts;
   multi-tenancy and per-user data isolation are engineering work, not research work, but are required
   before public deployment.
7. **Crisis-experiment realism.** Detection latency was measured on an injected surge with known onset
   time. Real crises have gradual onsets, so the reported 24 s should be read as a lower bound under
   favourable conditions.

---

## VIII. Conclusion and Future Work

We presented BrandShield AI, a real-time brand-risk system that unifies multilingual sentiment
classification, aspect-level attribution, unsupervised crisis detection, forecasting and alerting in a
single streaming pipeline running on commodity CPU hardware. On a hand-labelled multilingual benchmark
the hybrid classifier attains 83.1% accuracy and 81.7% macro-F1 and 74.0% accuracy on randomly
sampled real comments, aspect detection attains F1 = 0.806, and predictions agree with independent
star ratings 79.7% of the time. The deployed system analysed 12,174 real comments on a laptop CPU and
detected an injected crisis in under half a minute.

Future work follows directly from the limitations. We intend to (i) expand the benchmark with multiple
annotators and report agreement statistics; (ii) replace lexicon-based aspect detection with a
few-shot or prompt-based extractor to improve recall on unseen vocabulary; (iii) fine-tune the
classifier on domain-specific code-mixed comments rather than correcting it post hoc; (iv) evaluate
crisis-detection latency on historically documented brand incidents instead of injected ones; and
(v) extend the system to multi-tenant operation with per-workspace isolation.

---

## Acknowledgement

The authors thank Dr. Darshan Medhane for supervision and guidance throughout this project, and the
Department of Artificial Intelligence and Data Science, K. K. Wagh Institute of Engineering Education
and Research, Nashik, for providing the facilities used in this work.

---

## References

[1] J. Devlin, M.-W. Chang, K. Lee and K. Toutanova, "BERT: Pre-training of deep bidirectional
transformers for language understanding," in *Proc. NAACL-HLT*, 2019, pp. 4171–4186.

[2] V. Sanh, L. Debut, J. Chaumond and T. Wolf, "DistilBERT, a distilled version of BERT: smaller,
faster, cheaper and lighter," *arXiv:1910.01108*, 2019.

[3] C. J. Hutto and E. Gilbert, "VADER: A parsimonious rule-based model for sentiment analysis of
social media text," in *Proc. 8th Int. AAAI Conf. Weblogs and Social Media (ICWSM)*, 2014.

[4] A. Joshi, A. Prabhu, M. Shrivastava and V. Varma, "Towards sub-word level compositions for
sentiment analysis of Hindi-English code mixed text," in *Proc. COLING*, 2016, pp. 2482–2491.

[5] P. Patwa et al., "SemEval-2020 Task 9: Overview of sentiment analysis of code-mixed tweets," in
*Proc. 14th Workshop on Semantic Evaluation (SemEval)*, 2020, pp. 774–790.

[6] M. Pontiki, D. Galanis, J. Pavlopoulos, H. Papageorgiou, I. Androutsopoulos and S. Manandhar,
"SemEval-2014 Task 4: Aspect based sentiment analysis," in *Proc. 8th Int. Workshop on Semantic
Evaluation (SemEval)*, 2014, pp. 27–35.

[7] F. T. Liu, K. M. Ting and Z.-H. Zhou, "Isolation Forest," in *Proc. 8th IEEE Int. Conf. Data
Mining (ICDM)*, 2008, pp. 413–422.

[8] S. J. Taylor and B. Letham, "Forecasting at scale," *The American Statistician*, vol. 72, no. 1,
pp. 37–45, 2018.

[9] J. Kreps, N. Narkhede and J. Rao, "Kafka: A distributed messaging system for log processing," in
*Proc. NetDB Workshop*, 2011.

[10] F. Barbieri, J. Camacho-Collados, L. Espinosa-Anke and L. Neves, "TweetEval: Unified benchmark
and comparative evaluation for tweet classification," in *Findings of EMNLP*, 2020, pp. 1644–1650.

[11] A. Vaswani et al., "Attention is all you need," in *Proc. Advances in Neural Information
Processing Systems (NeurIPS)*, 2017, pp. 5998–6008.

[12] A. Conneau et al., "Unsupervised cross-lingual representation learning at scale," in *Proc. ACL*,
2020, pp. 8440–8451.
