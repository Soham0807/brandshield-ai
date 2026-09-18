ASPECT_KEYWORDS = {
    "delivery": [
        "delivery",
        "delivered",
        "late",
        "waiting",
        "arrived"
    ],

    "service": [
        "service",
        "staff",
        "employee",
        "support"
    ],

    "food_quality": [
        "food",
        "taste",
        "tasty",
        "coffee",
        "cappuccino",
        "cold"
    ],

    "price": [
        "price",
        "expensive",
        "cost",
        "cheap",
        "value"
    ],

    "ambience": [
        "ambience",
        "atmosphere",
        "cafe",
        "place"
    ]
}


def detect_aspect(text):

    text = text.lower()

    detected_aspects = []

    for aspect, keywords in ASPECT_KEYWORDS.items():

        for keyword in keywords:

            if keyword in text:
                detected_aspects.append(aspect)
                break

    if not detected_aspects:
        detected_aspects.append("general")

    return detected_aspects