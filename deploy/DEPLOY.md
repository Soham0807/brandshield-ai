# Deploying BrandShield AI (DigitalOcean + free student domain)

Everything below uses the **GitHub Student Developer Pack**: $200 DigitalOcean credit and a
free `.me` domain from Namecheap. Total cost during college: ₹0.

The result is a permanent HTTPS address you can open from any phone or laptop, anywhere.

---

## What the server needs

| | Minimum | Why |
|---|---|---|
| RAM | **4 GB** | DistilBERT + PyTorch hold ~1.8 GB; 2 GB droplets get killed by the OOM killer |
| Disk | **25 GB** | Python packages 1.5 GB + model cache 3.4 GB + data |
| CPU | 2 vCPU | Sentiment analysis is CPU-bound (~9 ms per comment) |

On DigitalOcean that is the **$24/month Basic droplet (4 GB / 2 vCPU / 80 GB)** — your $200
credit covers it for the whole credit window.

---

## 1. Claim the offers

1. **DigitalOcean** — [education.github.com/pack](https://education.github.com/pack) → DigitalOcean →
   *Get access* → sign in, add the credit (a card is required for verification; the credit pays the bill).
2. **Namecheap** — same pack → Namecheap → free `.me` domain for one year.
   Pick something like `brandshield-ai.me`.

## 2. Create the droplet

DigitalOcean → **Create → Droplets**

- Region: **Bangalore (BLR1)** — lowest latency from Nashik
- Image: **Ubuntu 24.04 LTS**
- Size: **Basic → Regular → $24/mo (4 GB / 2 vCPU / 80 GB)**
- Authentication: **SSH key** (safer) or password
- Hostname: `brandshield`

Note the droplet's **IPv4 address** when it finishes.

## 3. Point the domain at it

In Namecheap → *Domain List* → **Manage** → **Advanced DNS**, add two records:

| Type | Host | Value | TTL |
|---|---|---|---|
| A record | `@` | `your.droplet.ip` | Automatic |
| A record | `www` | `your.droplet.ip` | Automatic |

DNS usually propagates in 5–30 minutes. Check with `ping yourdomain.me`.

## 4. Put the code on the server

Push the project to GitHub first (private repo is fine), then on the droplet:

```bash
ssh root@your.droplet.ip

apt update && apt install -y git
git clone https://github.com/<you>/BRANDSHIELDAI.git /root/brandshield
cd /root/brandshield
```

> `backend/.env` and `frontend/dist` are gitignored on purpose — the installer creates both.

## 5. Run the installer

```bash
sudo bash deploy/install.sh yourdomain.me you@email.com
```

It takes 10–15 minutes and does everything: system packages, 2 GB swap, a locked-down
`brandshield` user, Python environment, the DistilBERT download, the dashboard build,
a systemd service, and Caddy with automatic HTTPS from Let's Encrypt.

It will ask you to choose a **dashboard password**. Because the app has no user accounts yet,
that password is what keeps your data private — anyone with the link would otherwise see
everything and be able to change settings.

When it finishes:

**https://yourdomain.me** — username `admin`, plus the password you chose.

## 6. Add your keys

Open the site → **Settings → API keys** (or the YouTube page) and paste:

- **YouTube API key** — free from [console.cloud.google.com](https://console.cloud.google.com/)
- Instagram app ID/secret, if you want the Instagram login

They are written to `/opt/brandshield/backend/.env` and applied without a restart.

For Instagram, set the redirect URI in your Meta app to:
`https://yourdomain.me/api/auth/instagram/callback` — a real domain, so you no longer need the
Cloudflare tunnel, and the URI never changes again.

---

## Running it

```bash
systemctl status brandshield        # is it up?
journalctl -u brandshield -f        # live logs
systemctl restart brandshield       # restart
```

**Deploying an update:**

```bash
cd /root/brandshield && git pull
sudo bash deploy/install.sh yourdomain.me you@email.com   # safe to re-run
```

**Backups** (the whole database is one SQLite file):

```bash
# copy it to your laptop
scp root@your.droplet.ip:/opt/brandshield/backend/data/brandshield.db ./backup.db
```

A nightly backup, if you want one:

```bash
echo '0 2 * * * cp /opt/brandshield/backend/data/brandshield.db /root/backup-$(date +\%u).db' | crontab -
```

---

## Cost after the credit runs out

| Option | Monthly | Notes |
|---|---|---|
| DigitalOcean 4 GB | ~₹2,000 | simplest, Bangalore region |
| **Hetzner CX22** | **~₹360** | same specs, best value, Singapore region |
| Oracle Cloud Always Free | ₹0 | 24 GB ARM, free forever, but ARM capacity is often unavailable |

Moving hosts later is just: run the same installer on the new box and copy `brandshield.db` across.

---

## Before you open it to real users

The password gate is a stopgap. Real multi-user use still needs:

1. User accounts and per-user data isolation (every mention, channel and alert scoped to an owner)
2. PostgreSQL instead of SQLite (SQLite is fine for one user, not for concurrent writers)
3. A separate background worker so a slow sync never blocks the dashboard
4. Per-user quota limits on the shared YouTube API key
