import pandas as pd
from datetime import datetime

from services.preprocessing import clean_text
from services.sentiment_service import SentimentAnalyzer
from services.aspect_service import detect_aspect


class CommentIngestion:

    def __init__(self):

        self.analyzer = SentimentAnalyzer()

        self.output_file = (
            "data/processed/live_comments.csv"
        )

    def process_comment(self, comment, brand="BeanTheory"):

        cleaned = clean_text(comment)

        sentiment = self.analyzer.analyze(
            cleaned
        )

        aspects = detect_aspect(
            cleaned
        )

        result = {
            "comment": comment,
            "cleaned_comment": cleaned,
            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "brand": brand,
            "sentiment": sentiment["sentiment"],
            "confidence": sentiment["confidence"],
            "aspects": aspects
        }

        new_row = pd.DataFrame([result])

        try:

            existing = pd.read_csv(
                self.output_file
            )

            updated = pd.concat(
                [existing, new_row],
                ignore_index=True
            )

        except FileNotFoundError:

            updated = new_row

        updated.to_csv(
            self.output_file,
            index=False
        )

        return result