from services.sentiment_service import SentimentAnalyzer


analyzer = SentimentAnalyzer()


comments = [
    "The coffee was absolutely amazing!",
    "The delivery was horrible and extremely late.",
    "The staff were friendly and helpful."
]


for comment in comments:

    result = analyzer.analyze(comment)

    print("\nComment:", comment)
    print("Sentiment:", result["sentiment"])
    print("Confidence:", result["confidence"])