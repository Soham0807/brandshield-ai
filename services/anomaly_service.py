from sklearn.ensemble import IsolationForest


class AnomalyDetector:

    def __init__(self):
        self.model = IsolationForest(
            contamination=0.15,
            random_state=42
        )

    def detect(self, hourly_data):

        data = hourly_data.copy()

        # Only analyze periods where comments actually occurred
        data = data[
            data["total_comments"] > 0
        ].copy()

        features = data[
            [
                "total_comments",
                "negative_comments",
                "negative_percentage"
            ]
        ]

        # Not enough observations for reliable anomaly detection
        if len(data) < 5:
            data["anomaly"] = 1
            data["is_anomaly"] = False
            return data

        data["anomaly"] = self.model.fit_predict(
            features
        )

        data["is_anomaly"] = (
            data["anomaly"] == -1
        )

        return data