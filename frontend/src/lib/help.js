// Plain-English explanations shown in hover pop-ups and page intro strips.
// Cards are matched by title, stat tiles by label, pages by route.

export const PAGE_HELP = {
  '/': {
    title: 'Brand overview',
    text: 'A live summary of what people are saying about the brand. Every comment is read by an AI model and tagged positive, neutral or negative. Hover over any number or chart to see what it means.',
  },
  '/youtube': {
    title: 'YouTube monitoring',
    text: 'Real comments from a YouTube channel, collected through the official YouTube API every 5 minutes. Each video shows how its audience feels; click a video to read its analysed comments.',
  },
  '/instagram': {
    title: 'Instagram monitoring',
    text: 'Type any public Instagram handle and BrandShield reads the latest posts and their comments every 15 minutes – no Instagram login needed. Each post shows how its audience feels; click a post to read its analysed comments.',
  },
  '/mentions': {
    title: 'Every analysed comment',
    text: 'The raw data behind every chart. Filter by sentiment, topic or source, and click a comment to see exactly how the AI classified it.',
  },
  '/analytics': {
    title: 'Trends, anomalies and forecast',
    text: 'Looks for unusual spikes in negative comments (possible PR crises), explains the risk score, and predicts where sentiment is heading over the next hours.',
  },
  '/aspects': {
    title: 'What people are talking about',
    text: 'Each comment is split into parts and matched to business topics such as delivery, price or service, so you can see what people like and what they complain about.',
  },
  '/alerts': {
    title: 'Automatic alerts',
    text: 'Problems the system detected on its own, such as a sudden rise in complaints or a negative post going viral. The same alerts can be sent by email, Slack, Teams or SMS.',
  },
  '/analyze': {
    title: 'Try the AI yourself',
    text: 'Type any comment (English, Hinglish, Hindi or Marathi) and see every step the system takes: cleaning, language detection, spam check, sentiment and topic-level sentiment.',
  },
  '/report': {
    title: 'Management summary',
    text: 'Risk, sentiment, topics, the worst complaints and recent alerts on one page. Print it or save it as a PDF; the CSV button downloads the underlying mentions.',
  },
  '/system': {
    title: 'How well and how fast it works',
    text: 'Live speed of the processing pipeline, plus the accuracy of the sentiment model measured on comments labelled by our team.',
  },
  '/settings': {
    title: 'Your preferences',
    text: 'Which brand to watch, which keywords count as a mention, the topics you care about, and where alerts are sent.',
  },
  '/setup': {
    title: 'Server setup',
    text: 'For the person running BrandShield: API keys, data sources, detection thresholds and the crisis simulation used in demos.',
  },
}

export const NAV_HELP = {
  Dashboard: 'Live overview: sentiment, risk score, alerts and newest comments',
  YouTube: 'Real comments from a monitored YouTube channel',
  Instagram: 'Comments on any public Instagram page',
  Mentions: 'Search and filter every analysed comment',
  'Trends & Forecast': 'Spike detection, risk breakdown and sentiment forecast',
  Topics: 'Sentiment per topic: delivery, price, service…',
  Alerts: 'Issues the system detected automatically',
  'Analyze Text': 'Type a comment and watch the AI analyse it step by step',
  Report: 'One-page brand summary to print, save as PDF or export as CSV',
  Performance: 'Speed of the pipeline and accuracy of the model',
  Settings: 'Brand, keywords, topics and alert notifications',
}

export const STAT_HELP = {
  'Brand health': 'Overall mood on a 0–100 scale. 50 is neutral, above 50 means people are mostly positive. The small badge shows the change versus the previous period of the same length.',
  Mentions: 'Number of comments about the brand in the selected time window, with the % change versus the previous window.',
  'Positive sentiment': 'Share of genuine comments the AI classified as positive. The badge shows the change in percentage points.',
  'Negative sentiment': 'Share of genuine comments classified as negative. A rising number here is the first sign of trouble, so an increase is shown in red.',
  'Spam filtered': 'Promotional or bot comments that were detected and excluded from every statistic, so they do not distort the results.',
  'Risk score': '0–100 estimate of how likely a PR problem is right now. It combines five signals (see the Brand risk card). Below 30 is low, 55+ is high, 75+ is critical.',
  'Throughput (msg/s, 1 min)': 'How many comments the pipeline processed per second over the last minute.',
  'Latency p50 (ingest → stored)': 'Typical time from a comment arriving to it being analysed and saved. Half of all comments are faster than this.',
  'Latency p95': 'Worst-case time for 95% of comments, from arrival to being analysed and saved.',
  'Model inference / text': 'Average time the AI model needs to classify one comment, on an ordinary laptop CPU with no GPU.',
  'Queue depth': 'Comments waiting to be processed. Close to 0 means the system is keeping up in real time.',
  Errors: 'Batches that failed during processing since the server started.',
}

export const CARD_HELP = {
  // Dashboard
  'Sentiment over time': 'Number of positive, neutral and negative comments in each time interval. Red markers show intervals the anomaly detector flagged as unusual.',
  'Sentiment distribution': 'How all genuine comments in the window split between positive, neutral and negative. Spam is shown separately and is not counted in the percentages elsewhere.',
  'Brand risk': 'The risk score is built from five signals: how negative people are, how fast complaints are growing, whether the anomaly detector fired, whether the forecast predicts a decline, and whether complaints focus on one topic. Hover over each bar for details.',
  'Topic insights': 'Topics people mention most (delivery, price, service…) and how they feel about each one. This answers "why" people are unhappy, not just "how many".',
  'Active alerts': 'Problems detected automatically that nobody has acknowledged yet.',
  'Live mention feed': 'The newest comments, appearing here a few seconds after they are posted and analysed.',
  'Trending words': 'Most frequent words in recent comments, after removing common words and reducing words to their base form (e.g. "delivered" → "deliver").',
  // Trends & forecast
  'Anomaly detection': 'Each point is a 15-minute interval. The system flags an interval when the share of negative comments jumps far above normal, using an Isolation Forest model plus a statistical check.',
  'Detected incidents': 'Consecutive unusual intervals grouped into one incident, with its peak negative share.',
  'Risk breakdown': 'Exactly how the current risk score was calculated, signal by signal.',
  Languages: 'Language of each comment, detected automatically. The model is multilingual, so all of these are analysed.',
  // Aspects
  'Sentiment by topic': 'For each topic, the share of positive, neutral and negative mentions.',
  'Top complaint terms': 'Words that appear most often in negative comments.',
  'Top praise terms': 'Words that appear most often in positive comments.',
  // Analyze
  Input: 'Type or paste any comment. English, Hinglish (Hindi in Roman letters), Hindi and Marathi are supported.',
  Sentiment: 'The model gives a probability for each class; the highest one wins. "Score" runs from −1 (very negative) to +1 (very positive). A regional-language word list corrects the model for Hinglish words.',
  'Topic-level sentiment': 'The comment is split at words like "but" or "lekin", and each part is classified separately. That is how one comment can be positive about food and negative about delivery.',
  'Preprocessing pipeline': 'The cleaning steps applied before the AI sees the text: removing links and @mentions, converting emojis to words, splitting into words, reducing words to their base form and detecting the language.',
  // Performance
  'Streaming pipeline': 'Comments flow from collectors into a message queue, are processed in small batches, and are pushed live to this dashboard.',
  'Sentiment model': 'The AI model used to classify comments. It runs on the CPU; no GPU is needed.',
  // YouTube / Instagram
  Videos: 'Each video with the sentiment of its comments. Click a video to read its analysed comments.',
  Posts: 'Each post with the sentiment of its comments. Click a post to read its analysed comments.',
  'Add a channel': 'Start monitoring a YouTube channel by its handle, URL or name.',
  // Settings
  'Crisis simulation': 'Injects a burst of complaints about one topic into the demo stream so you can watch the system detect the crisis and raise alerts within a few minutes.',
  'Alert thresholds': 'When alerts are raised: minimum risk score, negative share, number of negative comments and the cool-down between repeated alerts.',
  Topics: 'The topics the system looks for and the keywords that identify each topic. Editable at any time.',
}

export const RISK_HELP = {
  negativity: 'Negativity (max 35): share of negative comments right now, and how much higher it is than usual.',
  velocity: 'Velocity (max 20): how quickly negative comments are increasing compared with the recent past.',
  anomaly: 'Anomaly (max 25): points are added only when the Isolation Forest model flags the current period as an abnormal spike.',
  forecast: 'Forecast (max 10): added when the forecasting model predicts sentiment will fall over the next few hours.',
  concentration: 'Concentration (max 10): added when most complaints are about one topic, e.g. delivery. A focused problem is easier to escalate.',
}

export const METRIC_HELP = {
  accuracy: 'Accuracy: share of test comments where the model\'s label matched the human label.',
  precision: 'Precision: when the model says "negative", how often it is right.',
  recall: 'Recall: of all truly negative comments, how many the model found.',
  f1: 'F1: balance of precision and recall in one number (higher is better).',
  f1_weighted: 'Weighted F1: F1 averaged with more weight on larger classes.',
  support: 'Number of test comments in this class.',
}

export const SENTIMENT_HELP = {
  positive: 'The AI judged this comment as positive (praise, satisfaction).',
  neutral: 'The AI judged this comment as neutral: factual, a question, or no clear opinion.',
  negative: 'The AI judged this comment as negative (complaint, frustration).',
  spam: 'Promotional or bot content; excluded from all statistics.',
}

export const SEVERITY_HELP = {
  low: 'Low severity: worth knowing, no action needed yet.',
  medium: 'Medium severity: keep an eye on it.',
  high: 'High severity: should be looked at soon.',
  critical: 'Critical: likely PR problem, respond now.',
}
