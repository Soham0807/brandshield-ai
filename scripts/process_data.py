import pandas as pd

from services.preprocessing import clean_text
from services.sentiment_service import SentimentAnalyzer
from services.aspect_service import detect_aspect
from services.analytics_service import (
    calculate_sentiment_metrics,
    calculate_hourly_metrics
)
from services.anomaly_service import AnomalyDetector
from services.risk_service import calculate_risk


def process_data():

    print("Loading dataset...")

    df = pd.read_csv("data/raw/comments.csv")

    # -----------------------------
    # 1. PREPROCESSING
    # -----------------------------

    df["cleaned_comment"] = df["comment"].apply(clean_text)

    # -----------------------------
    # 2. SENTIMENT ANALYSIS
    # -----------------------------

    analyzer = SentimentAnalyzer()

    print(f"\nAnalyzing {len(df)} comments...\n")

    sentiments = []
    confidences = []

    for comment in df["cleaned_comment"]:

        result = analyzer.analyze(comment)

        sentiments.append(result["sentiment"])
        confidences.append(result["confidence"])

    df["sentiment"] = sentiments
    df["confidence"] = confidences

    # -----------------------------
    # 3. ASPECT DETECTION
    # -----------------------------

    df["aspects"] = df["cleaned_comment"].apply(detect_aspect)

    # -----------------------------
    # 4. OVERALL METRICS
    # -----------------------------

    metrics = calculate_sentiment_metrics(df)

    print("\nOverall Metrics:")
    print(metrics)

    # -----------------------------
    # 5. HOURLY ANALYTICS
    # -----------------------------

    hourly_metrics = calculate_hourly_metrics(df)

    print("\nHourly Metrics:")
    print(hourly_metrics.to_string(index=False))

    # -----------------------------
    # 6. ANOMALY DETECTION
    # -----------------------------

    detector = AnomalyDetector()

    hourly_metrics = detector.detect(hourly_metrics)

    print("\nAnomaly Detection:")

    print(
        hourly_metrics[
            [
                "timestamp",
                "total_comments",
                "negative_comments",
                "negative_percentage",
                "is_anomaly"
            ]
        ].to_string(index=False)
    )

    # -----------------------------
    # 7. RISK ANALYSIS
    # -----------------------------

    risk_results = []

    for _, row in hourly_metrics.iterrows():

        risk = calculate_risk(
            row["negative_percentage"],
            row["negative_comments"],
            row["is_anomaly"]
        )

        risk_results.append(risk)

    hourly_metrics["risk_score"] = [
        result["risk_score"]
        for result in risk_results
    ]

    hourly_metrics["risk_level"] = [
        result["risk_level"]
        for result in risk_results
    ]

    print("\nBrand Risk Analysis:")

    print(
        hourly_metrics[
            [
                "timestamp",
                "negative_percentage",
                "is_anomaly",
                "risk_score",
                "risk_level"
            ]
        ].to_string(index=False)
    )

    # Save hourly risk analysis
    risk_output_path = "data/processed/hourly_risk.csv"

    hourly_metrics.to_csv(
        risk_output_path,
        index=False
    )

    print(f"\nSaved risk analysis to: {risk_output_path}")

    # -----------------------------
    # 8. SAVE PROCESSED DATA
    # -----------------------------

    output_path = "data/processed/processed_comments.csv"

    df.to_csv(output_path, index=False)

    print("\nProcessing complete!")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    process_data()