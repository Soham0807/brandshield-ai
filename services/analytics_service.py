import pandas as pd


def calculate_sentiment_metrics(df):

    total_comments = len(df)

    positive_count = (df["sentiment"] == "POSITIVE").sum()
    negative_count = (df["sentiment"] == "NEGATIVE").sum()
    neutral_count = (df["sentiment"] == "NEUTRAL").sum()

    negative_percentage = (
        negative_count / total_comments * 100
        if total_comments > 0
        else 0
    )

    return {
        "total_comments": int(total_comments),
        "positive": int(positive_count),
        "negative": int(negative_count),
        "neutral": int(neutral_count),
        "negative_percentage": round(negative_percentage, 2)
    }


def calculate_hourly_metrics(df):

    df = df.copy()

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    hourly = (
        df.groupby(pd.Grouper(key="timestamp", freq="h"))
        .agg(
            total_comments=("comment", "count"),
            negative_comments=(
                "sentiment",
                lambda x: (x == "NEGATIVE").sum()
            )
        )
        .reset_index()
    )

    # Avoid division by zero
    hourly["negative_percentage"] = 0.0

    mask = hourly["total_comments"] > 0

    hourly.loc[mask, "negative_percentage"] = (
        hourly.loc[mask, "negative_comments"]
        / hourly.loc[mask, "total_comments"]
        * 100
    )

    hourly["negative_percentage"] = (
        hourly["negative_percentage"].round(2)
    )

    return hourly