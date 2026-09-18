"""Outbound alert channels: Email (SMTP), Slack, Microsoft Teams, SMS (Twilio).
The dashboard itself receives every alert over WebSocket (and shows a browser
push notification)."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

import httpx

logger = logging.getLogger("brandshield.notify")

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
SEVERITY_EMOJI = {"low": "🔵", "medium": "🟡", "high": "🟠", "critical": "🔴"}


class Notifier:
    def __init__(self, settings):
        self.settings = settings

    def channels_status(self) -> dict:
        s = self.settings
        return {
            "dashboard": True,
            "email": bool(s.smtp_host and s.alert_email_to),
            "slack": bool(s.slack_webhook_url),
            "teams": bool(s.teams_webhook_url),
            "sms": bool(s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number and s.alert_sms_to),
        }

    async def send(self, alert: dict, prefs: dict, brand: str, force: bool = False) -> dict:
        """Deliver to every enabled + configured channel. Returns per-channel results."""
        if not force and SEVERITY_RANK[alert["severity"]] < SEVERITY_RANK[prefs.get("min_severity", "high")]:
            return {}
        status = self.channels_status()
        tasks = {}
        for channel, func in (("email", self._email), ("slack", self._slack),
                              ("teams", self._teams), ("sms", self._sms)):
            if (prefs.get(channel) or force) and status[channel]:
                tasks[channel] = func(alert, brand)
        if not tasks:
            return {}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        out = {}
        for channel, result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.warning("Alert delivery via %s failed: %s", channel, result)
                out[channel] = f"error: {result}"
            else:
                out[channel] = "sent"
        return out

    @staticmethod
    def _headline(alert: dict, brand: str) -> str:
        return f"{SEVERITY_EMOJI[alert['severity']]} [{alert['severity'].upper()}] {brand}: {alert['title']}"

    async def _email(self, alert, brand):
        s = self.settings
        msg = EmailMessage()
        msg["Subject"] = self._headline(alert, brand)
        msg["From"] = s.smtp_from or s.smtp_user
        msg["To"] = s.alert_email_to
        msg.set_content(f"{alert['message']}\n\nOpen the BrandShield AI dashboard to investigate.")

        def deliver():
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
                smtp.starttls()
                if s.smtp_user:
                    smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(msg)

        await asyncio.to_thread(deliver)

    async def _slack(self, alert, brand):
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.settings.slack_webhook_url, json={
                "text": f"*{self._headline(alert, brand)}*\n{alert['message']}"})
            resp.raise_for_status()

    async def _teams(self, alert, brand):
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.settings.teams_webhook_url, json={
                "text": f"**{self._headline(alert, brand)}**<br>{alert['message']}"})
            resp.raise_for_status()

    async def _sms(self, alert, brand):
        s = self.settings
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages.json",
                data={"From": s.twilio_from_number, "To": s.alert_sms_to,
                      "Body": f"{self._headline(alert, brand)} - {alert['message']}"[:320]},
                auth=(s.twilio_account_sid, s.twilio_auth_token),
            )
            resp.raise_for_status()
