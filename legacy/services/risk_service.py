def calculate_risk(
    negative_percentage,
    negative_comments,
    is_anomaly
):
    """
    Calculate an MVP brand-risk score from 0 to 100.
    """

    # Negative sentiment contribution
    sentiment_score = min(
        negative_percentage * 0.5,
        50
    )

    # Negative volume contribution
    volume_score = min(
        negative_comments * 2,
        20
    )

    # Anomaly contribution
    anomaly_score = 30 if is_anomaly else 0

    # Final score
    risk_score = (
        sentiment_score
        + volume_score
        + anomaly_score
    )

    risk_score = min(
        round(risk_score),
        100
    )

    # Risk level
    if risk_score >= 70:
        risk_level = "HIGH"

    elif risk_score >= 40:
        risk_level = "MEDIUM"

    else:
        risk_level = "LOW"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level
    }