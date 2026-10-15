"""Static configuration loaded from environment variables / backend/.env.

Values that users can change at runtime from the dashboard (brand name,
keywords, thresholds, source toggles ...) live in ``app.runtime`` instead and
only take their *initial* defaults from here.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Brand defaults -------------------------------------------------
    brand_name: str = "Saffron Cafe"
    brand_keywords: str = "Saffron Cafe,SaffronCafe,saffron_cafe"

    # ---- Storage --------------------------------------------------------
    database_path: Path = BASE_DIR / "data" / "brandshield.db"
    evaluation_path: Path = BASE_DIR / "data" / "evaluation.json"

    # ---- NLP models -----------------------------------------------------
    # Ensemble (comma-separated, probabilities averaged): multilingual XLM-RoBERTa + English
    # RoBERTa, both trained on tweets by Cardiff NLP. 74% on 200 real labelled comments.
    sentiment_model: str = ("cardiffnlp/twitter-xlm-roberta-base-sentiment,"
                            "cardiffnlp/twitter-roberta-base-sentiment-latest")
    # Tried in order if no ensemble member loads: the earlier multilingual DistilBERT, then binary SST-2
    fallback_sentiment_model: str = ("tabularisai/multilingual-sentiment-analysis,"
                                     "distilbert-base-uncased-finetuned-sst-2-english")
    model_batch_size: int = 32
    model_max_length: int = 256

    # ---- Streaming ------------------------------------------------------
    bus_backend: str = "memory"  # "memory" or "kafka"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_raw: str = "brandshield.raw_mentions"
    kafka_group_id: str = "brandshield-processor"

    # ---- Data sources ---------------------------------------------------
    enable_simulator: bool = True
    simulator_rate_per_min: float = 8.0
    seed_history_days: int = 3

    enable_reddit: bool = False
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "BrandShieldAI/1.0 (academic project)"

    enable_rss: bool = False
    rss_feeds: str = ""  # extra comma separated feed URLs

    enable_twitter: bool = False
    twitter_bearer_token: str = ""

    # ---- Public sources for brands you do not own -----------------------
    # YouTube Data API v3 (free key from console.cloud.google.com)
    enable_youtube: bool = False
    youtube_api_key: str = ""
    youtube_api_base: str = "https://www.googleapis.com/youtube/v3"
    youtube_max_videos: int = 5          # videos tracked per brand (search costs quota)
    youtube_comment_pages: int = 2       # up to 100 comments per page, per video
    youtube_search_interval_hours: float = 6
    youtube_poll_seconds: int = 300      # how often connected channels are re-checked

    # Apple App Store customer reviews (public RSS, no key)
    enable_appstore: bool = False
    appstore_country: str = "in"
    appstore_app_id: str = ""            # leave empty to find the app by brand name
    appstore_pages: int = 3              # 50 reviews per page

    # Public Instagram pages of ANY brand, read through Apify (no Instagram login).
    # One token from console.apify.com -> Settings -> API & Integrations.
    apify_token: str = ""
    apify_base: str = "https://api.apify.com/v2"
    apify_timeout_seconds: int = 300
    instagram_pages_posts: int = 6               # latest posts tracked per page
    instagram_pages_comments_per_post: int = 40  # newest comments fetched per changed post
    instagram_pages_poll_seconds: int = 900      # each sync costs Apify credit, so not too often

    # Instagram API with Instagram Login (OAuth). Create an app at developers.facebook.com
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_graph_version: str = "v23.0"
    instagram_media_limit: int = 25          # recent posts whose comments are analysed
    instagram_poll_seconds: int = 180
    # overridable only for testing against a mock server
    instagram_auth_base: str = "https://www.instagram.com"
    instagram_api_base: str = "https://api.instagram.com"
    instagram_graph_base: str = "https://graph.instagram.com"

    # Public URL of this backend. Instagram redirects the browser to
    # {public_base_url}/api/auth/instagram/callback after login.
    public_base_url: str = "http://127.0.0.1:8000"
    # Where the browser is sent after login (defaults to public_base_url)
    frontend_url: str = ""
    # Fernet key used to encrypt access tokens (generated into data/secret.key if empty)
    secret_key: str = ""

    poll_interval_seconds: int = 180

    # ---- Analytics ------------------------------------------------------
    bucket_minutes: int = 15
    analytics_interval_seconds: int = 30
    forecast_refresh_seconds: int = 300
    forecast_horizon_hours: int = 12

    # ---- Notifications --------------------------------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    alert_email_to: str = ""

    slack_webhook_url: str = ""
    teams_webhook_url: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    alert_sms_to: str = ""

    # ---- Web ------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def keyword_list(self) -> list[str]:
        return [k.strip() for k in self.brand_keywords.split(",") if k.strip()]


settings = Settings()


def write_env(updates: dict[str, str]) -> Path:
    """Create or update keys in backend/.env so they survive a restart."""
    path = BASE_DIR / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for key, value in updates.items():
        key = key.upper()
        entry = f"{key}={value}"
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = entry
                break
        else:
            lines.append(entry)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
