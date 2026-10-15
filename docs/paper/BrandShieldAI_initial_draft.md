# BrandShield AI: Real-Time Brand Sentiment Monitoring and Crisis Detection on Social Media

Soham Borse, Tanish Bantwal, Aryan Baakle, Omsingh Rajput
Department of Artificial Intelligence and Data Science
K. K. Wagh Institute of Engineering Education and Research, Nashik

Guide: Dr. Darshan Medhane

*Initial draft (for internal review)*

---

## Abstract

Customers today share their opinions about brands openly on platforms like YouTube, Instagram and
app stores. A few negative posts can spread quickly and damage a brand's image within hours. Most
small and medium businesses still track this manually, or use costly tools that only show overall
sentiment after the damage is done. In this project we are building BrandShield AI, a system that
collects public comments about a brand in real time, finds out whether they are positive, negative
or neutral, identifies what exactly people are talking about (delivery, price, service and so on),
and warns the brand when negative sentiment suddenly rises. The system uses a multilingual
DistilBERT model for sentiment classification, a small Hinglish/Hindi/Marathi word list to handle
code-mixed comments, and Isolation Forest for detecting unusual spikes. Early tests on a small
labelled set of comments give around 78% accuracy, and the system is able to run on a normal laptop
CPU without a GPU.

**Keywords:** sentiment analysis, brand monitoring, aspect-based sentiment, DistilBERT, anomaly
detection, code-mixed text

---

## 1. Introduction

Social media has become the first place where people go to praise or complain about a product. If a
food delivery app delivers late or a phone has a defect, users usually post about it on YouTube
comments, Instagram, or app store reviews before contacting customer care. These posts are public,
and other customers read them before making their own decisions. Because of this, the way a brand is
seen online can change very quickly.

Large companies have social media teams and paid tools to keep track of this. Smaller businesses
usually do not. Even when tools are available, they mostly give a single number like "30% negative",
which does not tell the business what the actual problem is. Is it delivery? Pricing? Quality of the
product? Without that detail it is hard to take action.

Another problem we noticed is language. In India, a large share of comments are written in Hinglish
or in Hindi and Marathi, sometimes in Roman script and sometimes in Devanagari. For example, a
comment like "delivery bahut late thi, khana thanda ho gaya" is clearly negative, but many English
sentiment models fail to understand it properly.

Our project, BrandShield AI, tries to address these issues together. The idea is to build one system
that:

- collects brand-related comments from social platforms automatically,
- classifies the sentiment of each comment, including code-mixed ones,
- breaks down the opinion by topic (aspect), and
- detects when negative sentiment is rising unusually fast, so the brand can respond early.

The rest of this draft covers the related work we studied, the problem statement and objectives, and
the overall approach we are following.

---

## 2. Literature Survey

**Transformer models for sentiment.** BERT [1] showed that pre-trained transformer models can be
fine-tuned to give strong results on text classification tasks, including sentiment. DistilBERT [2]
is a smaller version of BERT that is about 40% lighter and 60% faster while keeping most of its
accuracy. Since our system needs to process a continuous stream of comments without expensive
hardware, DistilBERT is a practical choice for us.

**Lexicon-based methods.** VADER [3] is a rule-based tool that uses a dictionary of words with
sentiment scores. It works well on short, informal social media text and is very fast. However, it
does not understand context the way transformer models do. Some recent works combine both approaches.
We use a similar idea, but only use a small word list for Hindi, Hinglish and Marathi words where the
main model is weak.

**Code-mixed sentiment analysis.** Joshi et al. [4] studied sentiment in Hindi-English code-mixed
text and showed that standard models struggle with it. The SemEval-2020 shared task [5] on code-mixed
tweets confirmed this, with most systems performing noticeably worse than on clean English text.

**Aspect-based sentiment analysis (ABSA).** The SemEval-2014 ABSA task [6] defined the problem of
finding which aspect of a product a sentence talks about and what the opinion is on that aspect.
Most modern ABSA models need a lot of labelled training data, which is not available for every brand.
So we are going with a simpler keyword-based method that a user can update on their own.

**Anomaly detection and forecasting.** Isolation Forest [7] is an unsupervised method that finds
unusual data points by randomly splitting the data. It does not need labelled examples of a
"crisis", which suits our problem. Prophet [8], developed at Facebook, is a time-series forecasting
tool that handles trends and daily patterns and is easy to interpret.

**Gap identified.** Most of the work we found focuses on one of these parts: either sentiment
classification, or forecasting, or anomaly detection. We did not find many systems that combine
aspect-level analysis with live crisis detection, especially for Indian code-mixed comments. This is
the gap our project tries to fill.

---

## 3. Problem Statement

To design and develop a real-time system that monitors public social media conversation about a
brand, classifies sentiment in English as well as code-mixed Indian languages, identifies the specific
aspects behind customer opinions, and alerts the brand early when there is a sudden rise in negative
sentiment.

---

## 4. Objectives

1. To collect brand-related comments automatically from platforms such as YouTube, Instagram, news
   feeds and app store reviews using their official APIs.
2. To classify each comment as positive, negative or neutral using a multilingual transformer model,
   with extra handling for Hinglish, Hindi and Marathi text.
3. To identify the aspects (like delivery, price, service, food quality) mentioned in each comment
   and the sentiment towards each aspect.
4. To detect sudden negative spikes using anomaly detection and raise alerts.
5. To display all results on a simple live dashboard that a non-technical user can understand.
6. To keep the system light enough to run on a normal CPU without needing a GPU.

---

## 5. Proposed Approach

The system works as a pipeline with the following main steps.

**Data collection.** Separate collectors fetch comments from each platform at regular intervals. For
YouTube we use the YouTube Data API, for Instagram the official Instagram API, and for news and app
reviews we use their public RSS feeds. The collectors send the comments to a message queue so that a
slow API does not hold up the rest of the system.

**Preprocessing.** Each comment is cleaned by removing links, usernames and HTML. Repeated letters
like "sooooo" are shortened, common emojis are converted to words (for example 😡 becomes "angry"),
and the language of the comment is detected. A simple rule-based filter removes obvious spam and
promotional comments.

**Sentiment classification.** We use a multilingual DistilBERT model to get the sentiment of each
comment. For code-mixed comments, we also check a small list of Hindi, Hinglish and Marathi opinion
words (like "bekar", "mast", "bakwas") and combine this with the model's output. If the model is not
confident between two classes, the comment is marked as neutral.

**Aspect extraction.** A comment is first split into smaller parts at words like "but", "however",
"lekin" and "par". Each part is then checked for aspect keywords. This way, a comment like "food was
great but delivery was late" gives a positive score for food and a negative score for delivery
instead of one mixed label.

**Crisis detection.** Comments are grouped into 15-minute time windows. For every window we calculate
the number of comments, number of negative comments and the share of negative comments. Isolation
Forest is used to find windows that look unusual compared to recent history. An alert is raised only
when the share of negative comments goes up, not just the count, since the count naturally rises
during busy hours of the day.

**Dashboard and alerts.** The results are shown on a web dashboard built with React, which updates
live. Alerts can also be sent by email or Slack.

---

## 6. Current Progress

So far we have completed the data collection for YouTube, news and app store reviews, the
preprocessing and sentiment classification modules, and a first version of aspect extraction and
crisis detection. On a small hand-labelled set of 83 comments in English, Hinglish, Hindi and
Marathi, the sentiment classifier gives about 78% accuracy. The system has been tested on close to
10,000 real comments and processes each comment in under 10 ms on a laptop CPU.

The next steps are to build a larger labelled dataset, test crisis detection more carefully, and
complete the remaining sections of the paper (detailed methodology, results and conclusion).

---

## References

[1] J. Devlin, M.-W. Chang, K. Lee and K. Toutanova, "BERT: Pre-training of deep bidirectional
transformers for language understanding," in *Proc. NAACL-HLT*, 2019, pp. 4171–4186.

[2] V. Sanh, L. Debut, J. Chaumond and T. Wolf, "DistilBERT, a distilled version of BERT: smaller,
faster, cheaper and lighter," *arXiv:1910.01108*, 2019.

[3] C. J. Hutto and E. Gilbert, "VADER: A parsimonious rule-based model for sentiment analysis of
social media text," in *Proc. ICWSM*, 2014.

[4] A. Joshi, A. Prabhu, M. Shrivastava and V. Varma, "Towards sub-word level compositions for
sentiment analysis of Hindi-English code mixed text," in *Proc. COLING*, 2016, pp. 2482–2491.

[5] P. Patwa et al., "SemEval-2020 Task 9: Overview of sentiment analysis of code-mixed tweets," in
*Proc. SemEval*, 2020, pp. 774–790.

[6] M. Pontiki et al., "SemEval-2014 Task 4: Aspect based sentiment analysis," in *Proc. SemEval*,
2014, pp. 27–35.

[7] F. T. Liu, K. M. Ting and Z.-H. Zhou, "Isolation Forest," in *Proc. IEEE ICDM*, 2008,
pp. 413–422.

[8] S. J. Taylor and B. Letham, "Forecasting at scale," *The American Statistician*, vol. 72, no. 1,
pp. 37–45, 2018.
