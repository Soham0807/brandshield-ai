from flask import Blueprint, render_template
import pandas as pd
import ast

dashboard = Blueprint("dashboard", __name__)


@dashboard.route("/")
def index():

        # Use live comments if available
    try:
        comments = pd.read_csv(
            "data/processed/live_comments.csv"
        )
    except FileNotFoundError:
        comments = pd.read_csv(
            "data/processed/processed_comments.csv"
        )

    risk = pd.read_csv(
        "data/processed/hourly_risk.csv"
    )

    # -------------------------
    # Basic sentiment metrics
    # -------------------------

    total_comments = len(comments)

    positive = int(
        (comments["sentiment"] == "POSITIVE").sum()
    )

    negative = int(
        (comments["sentiment"] == "NEGATIVE").sum()
    )

    neutral = int(
        (comments["sentiment"] == "NEUTRAL").sum()
    )

    # -------------------------
    # Aspect analysis
    # -------------------------

    aspect_counts = {}

    for value in comments["aspects"].dropna():

        try:
            aspects = ast.literal_eval(value)

            for aspect in aspects:
                aspect_counts[aspect] = (
                    aspect_counts.get(aspect, 0) + 1
                )

        except (ValueError, SyntaxError):
            continue

    aspect_labels = list(aspect_counts.keys())
    aspect_values = list(aspect_counts.values())

    # -------------------------
    # Risk chart
    # -------------------------

    risk["timestamp"] = pd.to_datetime(
        risk["timestamp"]
    )

    chart_labels = risk["timestamp"].dt.strftime(
        "%d %b %H:%M"
    ).tolist()

    risk_scores = (
        risk["risk_score"]
        .fillna(0)
        .astype(int)
        .tolist()
    )

    negative_percentages = (
        risk["negative_percentage"]
        .fillna(0)
        .tolist()
    )
    # -------------------------
    # Recent analyzed comments
    # -------------------------

    recent_comments = []

    for _, row in comments.tail(10).iterrows():

        try:
            aspects = ast.literal_eval(
                row["aspects"]
            )
        except (ValueError, SyntaxError):
            aspects = []

        recent_comments.append({
            "comment": row["comment"],
            "sentiment": row["sentiment"],
            "confidence": round(
                float(row["confidence"]) * 100,
                2
            ),
            "aspects": ", ".join(aspects)
        })
    latest_risk = risk.iloc[-1]

    # -------------------------
    # Crisis / anomaly alerts
    # -------------------------

    anomalies = risk[
        risk["is_anomaly"] == True
    ].copy()

    alerts = []

    for _, row in anomalies.iterrows():

        alerts.append({
            "timestamp": row["timestamp"].strftime(
                "%d %b %Y %H:%M"
            ),
            "negative_percentage": round(
                row["negative_percentage"], 2
            ),
            "negative_comments": int(
                row["negative_comments"]
            ),
            "risk_score": int(
                row["risk_score"]
            ),
            "risk_level": row["risk_level"]
        })

    return render_template(
        "dashboard.html",

        total_comments=total_comments,
        positive=positive,
        negative=negative,
        neutral=neutral,
        alerts=alerts,
        recent_comments=recent_comments,

        risk_score=int(
            latest_risk["risk_score"]
        ),

        risk_level=latest_risk["risk_level"],

        chart_labels=chart_labels,
        risk_scores=risk_scores,
        negative_percentages=negative_percentages,

        aspect_labels=aspect_labels,
        aspect_values=aspect_values
    )