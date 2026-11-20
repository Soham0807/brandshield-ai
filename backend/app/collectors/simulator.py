"""Realistic social-media stream simulator.

Real platform APIs are paid / rate limited, so this generator produces a
continuous stream of brand mentions for demos and evaluation:

* daily seasonality in volume (busy lunch / evening hours),
* a mix of positive, neutral and negative opinions across aspects,
* English, Hinglish, Hindi and Marathi comments, emojis and spam,
* on-demand "crisis mode" where complaints about one aspect spike,
* every generated text carries its intended label (``true_label``) so the
  live accuracy of the model can be measured.
"""

import math
import random
import uuid
from datetime import datetime, timedelta

SOURCES = [("instagram", 0.45), ("twitter", 0.30), ("reddit", 0.10), ("google_reviews", 0.15)]

FIRST = ["aarav", "priya", "rohan", "sneha", "arjun", "ananya", "kabir", "isha", "vikram", "neha",
         "aditya", "pooja", "rahul", "meera", "siddharth", "tanvi", "omkar", "shruti", "yash", "riya"]
SUFFIX = ["", "_", ".", "_official", "123", "_eats", "_vlogs", "07", "_nashik", "_pune", "x"]

ITEMS = ["cold coffee", "cappuccino", "masala chai", "paneer sandwich", "pasta", "brownie",
         "waffles", "cheese burger", "pizza", "hazelnut latte", "croissant", "filter coffee"]

# aspect -> sentiment -> templates. {brand}, {item}, {minutes} are filled in.
TEMPLATES = {
    "food_quality": {
        "positive": [
            "The {item} at {brand} was absolutely delicious 😍",
            "Best {item} in town, {brand} never disappoints!",
            "Tried the new {item} today, the taste is amazing 🔥",
            "{brand} {item} is so fresh and flavorful, loved it",
            "Their {item} is perfect every single time 👌",
            "{item} ekdum mast tha at {brand} 😋",
            "{brand} cha {item} khup bhari ahe!",
        ],
        "neutral": [
            "Had the {item} at {brand} today, it was okay.",
            "The {item} at {brand} tastes the same as before.",
            "Ordered a {item} from {brand} this afternoon.",
        ],
        "negative": [
            "The {item} at {brand} was stale and tasteless 🤢",
            "Very disappointed, my {item} was cold and bland",
            "{brand} quality has gone down, the {item} was terrible",
            "Found the {item} undercooked today. Not acceptable {brand}",
            "{item} bilkul bekar tha, total waste of money",
            "Worst {item} I have ever had, never ordering from {brand} again 😡",
        ],
    },
    "service": {
        "positive": [
            "The staff at {brand} are so friendly and helpful 🙂",
            "Great service today, the barista remembered my order!",
            "Loved the hospitality at {brand}, very polite staff",
            "Staff ka behaviour bahut accha tha, great service",
        ],
        "neutral": [
            "Service at {brand} was normal today.",
            "The staff took my order at the counter.",
        ],
        "negative": [
            "Waited {minutes} minutes and nobody took our order at {brand} 😤",
            "The staff at {brand} were extremely rude to us today",
            "Terrible service, we were ignored for {minutes} minutes",
            "Manager at {brand} was so rude, very bad attitude",
            "Service bahut slow hai, {minutes} minute wait kiya 😡",
        ],
    },
    "delivery": {
        "positive": [
            "Delivery from {brand} arrived super quick and hot 👍",
            "Order was delivered on time, thanks {brand}!",
            "Swiggy order from {brand} came early, impressed",
        ],
        "neutral": [
            "My {brand} order is out for delivery.",
            "Ordered {item} for delivery from {brand}.",
        ],
        "negative": [
            "My {brand} delivery is {minutes} minutes late and still not here 😡",
            "Delivery was delayed by an hour and the {item} arrived cold",
            "Wrong order delivered again {brand}, missing item too",
            "Order never arrived and {brand} is not responding. Worst delivery experience",
            "Delivery bahut late tha, bekar service {brand}",
            "{minutes} minutes late delivery and cold food, very disappointed 👎",
        ],
    },
    "price": {
        "positive": [
            "{brand} is great value for money, loved the combo",
            "Affordable prices and big portions at {brand} 🙌",
        ],
        "neutral": [
            "{brand} changed the prices on the menu.",
            "The {item} costs around 250 at {brand}.",
        ],
        "negative": [
            "{brand} is so overpriced now, 400 for a {item}? 🙄",
            "Too expensive for such small portions, not worth it",
            "Prices increased again at {brand}, bahut mehenga hai",
        ],
    },
    "ambience": {
        "positive": [
            "Such a cozy vibe at {brand}, perfect place to work ✨",
            "Loved the music and decor at {brand} 😍",
            "{brand} ambience is beautiful, great for dates",
        ],
        "neutral": [
            "{brand} has new seating arrangements.",
            "Sitting at {brand} working on my laptop.",
        ],
        "negative": [
            "{brand} was too crowded and noisy today",
            "The music at {brand} is way too loud, could not talk",
        ],
    },
    "hygiene": {
        "positive": [
            "Very clean and hygienic kitchen at {brand}, love it",
        ],
        "neutral": [
            "{brand} washroom is on the first floor.",
        ],
        "negative": [
            "Found a hair in my {item} at {brand}. Disgusting 🤮",
            "Tables were dirty and there were flies everywhere",
            "Got food poisoning after eating at {brand}, very unhygienic",
        ],
    },
    "app_experience": {
        "positive": [
            "The new {brand} app makes ordering so easy 👍",
            "Loyalty points on the {brand} app are a nice touch",
        ],
        "neutral": [
            "Placed an online order on the {brand} app.",
        ],
        "negative": [
            "{brand} app crashed during payment and money got deducted 😡",
            "Still waiting for my refund from {brand}, the app shows nothing",
            "Coupon not working on the {brand} app, checkout keeps failing",
        ],
    },
    "packaging": {
        "positive": [
            "Loved the eco friendly packaging from {brand} ✨",
        ],
        "neutral": [
            "{brand} uses paper boxes for takeaway.",
        ],
        "negative": [
            "The {item} spilled everywhere, packaging was terrible",
            "Container leaked and the bag was a mess, fix your packaging {brand}",
        ],
    },
}

MIXED = [
    ("The {item} was great but the service was painfully slow", "neutral"),
    ("Loved the ambience but the {item} was overpriced", "neutral"),
    ("Food was tasty but delivery was {minutes} minutes late", "neutral"),
]

GENERAL = {
    "positive": [
        "{brand} is my favourite place ❤️",
        "Can't wait to visit {brand} again this weekend!",
        "Shoutout to {brand} for making my day 🙌",
        "{brand} ekdum zabardast hai 🔥",
        "{brand} बहुत शानदार है, मुझे बहुत पसंद आया",
        "{brand} मस्त आहे, नक्की भेट द्या",
    ],
    "neutral": [
        "Is {brand} open on Sunday?",
        "Heading to {brand} with friends.",
        "Does {brand} have a branch in Pune?",
        "{brand} posted a new menu today.",
        "Anyone tried {brand} recently?",
    ],
    "negative": [
        "Really disappointed with {brand} lately 😞",
        "{brand} used to be good, not anymore",
        "Never going back to {brand}, horrible experience",
        "{brand} bilkul bakwas hai, paisa barbaad",
    ],
}

SPAM = [
    "Get 10k free followers now!!! Check my profile 🔥🔥 {link}",
    "Earn $500 daily working from home, DM for details {link}",
    "Crypto investment opportunity 100% guaranteed returns whatsapp me",
    "Follow me and I follow back instantly #f4f #l4l #follow #instagood #like4like #followme",
    "Giveaway!!! click the link in my bio to win an iPhone {link} {link}",
]

ASPECT_WEIGHTS = {
    "food_quality": 0.30, "service": 0.18, "delivery": 0.16, "price": 0.10, "ambience": 0.10,
    "hygiene": 0.04, "app_experience": 0.07, "packaging": 0.05,
}
BASE_SENTIMENT = {"positive": 0.62, "neutral": 0.24, "negative": 0.14}


def seasonal_factor(dt: datetime) -> float:
    """Relative volume by local (IST) hour of day: quiet at night, peaks at lunch/evening."""
    hour = (dt.hour + 5.5) % 24
    lunch = math.exp(-((hour - 13.5) ** 2) / 6)
    evening = 1.2 * math.exp(-((hour - 19.5) ** 2) / 8)
    return 0.25 + lunch + evening


class CrisisState:
    def __init__(self):
        self.aspect: str | None = None
        self.until: datetime | None = None
        self.intensity = 0.0

    def active(self, now: datetime) -> bool:
        return self.until is not None and now < self.until

    def to_dict(self, now: datetime) -> dict:
        return {
            "active": self.active(now),
            "aspect": self.aspect if self.active(now) else None,
            "ends_at": self.until.strftime("%Y-%m-%dT%H:%M:%SZ") if self.active(now) else None,
            "intensity": self.intensity if self.active(now) else 0,
        }


class MentionSimulator:
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.crisis = CrisisState()

    def start_crisis(self, aspect: str, minutes: int, intensity: float, now: datetime) -> None:
        self.crisis.aspect = aspect
        self.crisis.until = now + timedelta(minutes=minutes)
        self.crisis.intensity = intensity

    def stop_crisis(self) -> None:
        self.crisis.until = None

    def opening_burst(self, brand: str, rate_per_min: float, now: datetime, minutes: float = 5) -> list[dict]:
        """Crisis mentions spread over the last few minutes, as if a complaint
        thread had been building before anyone noticed. Makes the demo crisis
        visible within one analytics tick instead of only after several minutes."""
        if not self.crisis.active(now):
            return []
        start = now - timedelta(minutes=minutes)
        lam = rate_per_min / 1.1 * (1 + 2.5 * self.crisis.intensity)
        mentions, t = [], start
        while True:
            t += timedelta(minutes=self.rng.expovariate(lam))
            if t >= now:
                return mentions
            mentions.append(self.generate(brand, t))

    def rate_multiplier(self, now: datetime, crisis: CrisisState | None = None) -> float:
        crisis = crisis or self.crisis
        factor = seasonal_factor(now)
        if crisis.active(now):
            factor *= 1 + 2.5 * crisis.intensity
        return factor

    def _author(self) -> str:
        return self.rng.choice(FIRST) + self.rng.choice(SUFFIX) + str(self.rng.randint(0, 99) if self.rng.random() < 0.3 else "")

    def _fill(self, template: str, brand: str) -> str:
        return template.format(
            brand=brand,
            item=self.rng.choice(ITEMS),
            minutes=self.rng.choice([25, 35, 40, 45, 50, 60, 75, 90]),
            link=f"https://bit.ly/{uuid.uuid4().hex[:6]}",
        )

    def generate(self, brand: str, created_at: datetime, crisis: CrisisState | None = None) -> dict:
        crisis = crisis or self.crisis
        rng = self.rng
        source = rng.choices([s for s, _ in SOURCES], weights=[w for _, w in SOURCES])[0]
        in_crisis = crisis.active(created_at)

        if rng.random() < 0.04:
            text, label = self._fill(rng.choice(SPAM), brand), None
        elif in_crisis and rng.random() < 0.55 + 0.35 * crisis.intensity:
            text = self._fill(rng.choice(TEMPLATES[crisis.aspect]["negative"]), brand)
            label = "negative"
        elif rng.random() < 0.05:
            template, label = rng.choice(MIXED)
            text = self._fill(template, brand)
        else:
            weights = dict(BASE_SENTIMENT)
            if in_crisis:
                weights = {"positive": 0.35, "neutral": 0.25, "negative": 0.40}
            label = rng.choices(list(weights), weights=list(weights.values()))[0]
            if rng.random() < 0.15:
                text = self._fill(rng.choice(GENERAL[label]), brand)
            else:
                aspect = rng.choices(list(ASPECT_WEIGHTS), weights=list(ASPECT_WEIGHTS.values()))[0]
                text = self._fill(rng.choice(TEMPLATES[aspect][label]), brand)

        engagement = int(rng.paretovariate(1.3) * 3)
        if label == "negative" and in_crisis and rng.random() < 0.03:
            engagement = rng.randint(600, 4000)  # a post going viral
        external_id = uuid.uuid4().hex
        return {
            "source": source,
            "external_id": external_id,
            "author": self._author(),
            "text": text,
            "url": None,
            "created_at": created_at,
            "engagement": engagement,
            "true_label": label,
            "origin": "simulated",
        }

    def history(self, brand: str, days: int, rate_per_min: float, now: datetime) -> list[dict]:
        """Generate past mentions, including one historical incident so the
        anomaly and forecast views have something meaningful to show."""
        start = now - timedelta(days=days)
        incident = CrisisState()
        incident.aspect = "delivery"
        incident_start = now - timedelta(hours=min(30, days * 24 * 0.4))
        incident.until = incident_start + timedelta(minutes=100)
        incident.intensity = 0.8

        mentions = []
        t = start
        base_per_min = rate_per_min / 1.1  # average seasonal factor is ~1.1
        while t < now:
            window = incident if incident_start <= t < incident.until else CrisisState()
            lam = base_per_min * self.rate_multiplier(t, window)
            t += timedelta(minutes=self.rng.expovariate(lam))
            if t >= now:
                break
            mentions.append(self.generate(brand, t, window))
        return mentions
