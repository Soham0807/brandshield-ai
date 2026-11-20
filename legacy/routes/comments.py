from flask import Blueprint, render_template, request

from services.preprocessing import clean_text
from services.sentiment_service import SentimentAnalyzer
from services.aspect_service import detect_aspect
from services.risk_service import calculate_risk
from services.ingestion_service import CommentIngestion


comments = Blueprint(
    "comments",
    __name__
)


analyzer = SentimentAnalyzer()

ingestion = CommentIngestion()


@comments.route(
    "/analyze",
    methods=["GET", "POST"]
)
def analyze():

    result = None

    if request.method == "POST":

        comment = request.form.get(
            "comment",
            ""
        ).strip()

        if comment:

            cleaned = clean_text(
                comment
            )

            sentiment_result = analyzer.analyze(
                cleaned
            )

            aspects = detect_aspect(
                cleaned
            )

            negative_percentage = (
                100
                if sentiment_result["sentiment"]
                == "NEGATIVE"
                else 0
            )

            negative_comments = (
                1
                if sentiment_result["sentiment"]
                == "NEGATIVE"
                else 0
            )

            risk = calculate_risk(
                negative_percentage,
                negative_comments,
                False
            )

            # Store the new comment
            ingestion.process_comment(
                comment
            )

            result = {

                "comment": comment,

                "sentiment":
                    sentiment_result["sentiment"],

                "confidence":
                    round(
                        sentiment_result["confidence"]
                        * 100,
                        2
                    ),

                "aspects": aspects,

                "risk_score":
                    risk["risk_score"],

                "risk_level":
                    risk["risk_level"]
            }

    return render_template(
        "analyze.html",
        result=result
    )