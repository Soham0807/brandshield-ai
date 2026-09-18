from transformers import pipeline


class SentimentAnalyzer:

    def __init__(self):
        print("Loading sentiment model...")

        self.model = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english"
        )

        print("Sentiment model loaded!")

    def analyze(self, text):

        result = self.model(text)[0]

        return {
            "sentiment": result["label"],
            "confidence": round(float(result["score"]), 4)
        }