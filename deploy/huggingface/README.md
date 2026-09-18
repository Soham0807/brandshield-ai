# Deploying BrandShield AI on Hugging Face Spaces (free)

No credit card, no server to manage, 2 vCPU and 16 GB RAM — more memory than a ₹2,000/month
droplet. You get a permanent HTTPS link that opens on any phone or laptop.

**Trade-offs, so nothing surprises you:**
- The Space **sleeps after ~48 h of inactivity** and wakes on the next visit (~30 s).
- Without paid storage ($5/mo), the database **resets when the Space restarts**. Your connected
  YouTube channels and their comments are re-synced automatically, so a demo still works.
- CPU inference is a bit slower than your laptop (~15–20 ms per comment instead of 9 ms).

---

## 1. Create the Space

1. Sign in at [huggingface.co](https://huggingface.co) (free account).
2. **New → Space**.
   - Owner: you
   - Space name: `brandshield-ai`
   - License: any
   - **SDK: Docker** → *Blank*
   - **Visibility: Private** ← important: the app has no login yet, so a private Space is what
     keeps your data yours. You can flip it to Public for the demo and back afterwards.
3. Create.

## 2. Push the project

The Space is a git repo. From your project folder:

```bash
# one-time: the Dockerfile has to sit at the repo root
cp deploy/huggingface/Dockerfile ./Dockerfile
cp deploy/huggingface/space.md ./README.md      # Spaces reads its settings from this file

git init                                        # if the project isn't a git repo yet
git add -A
git commit -m "BrandShield AI"

git remote add space https://huggingface.co/spaces/<your-username>/brandshield-ai
git push space main
```

When git asks for a password, use a **write token** from
[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (not your account password).

> Pushing replaces the repo `README.md` with the Space settings file. If you'd rather keep the
> project README, rename the copied file's contents into the top of your existing README — the
> YAML block at the very top is the only part Spaces needs.

## 3. Wait for the build

The **Logs** tab shows progress. First build takes 10–20 minutes because it installs PyTorch and
bakes the DistilBERT model into the image. Later pushes are much faster.

When it says `Application startup complete`, open the Space URL:

```
https://huggingface.co/spaces/<your-username>/brandshield-ai
```

## 4. Configure it

In the Space → **Settings → Variables and secrets**:

| Type | Name | Value | Why |
|---|---|---|---|
| Secret | `YOUTUBE_API_KEY` | your key | so channels can sync |
| Variable | `ENABLE_SIMULATOR` | `false` | real data only (set `true` for a full demo dashboard) |
| Variable | `SEED_HISTORY_DAYS` | `0` | skip generating demo history |
| Variable | `PUBLIC_BASE_URL` | your Space URL | needed only for Instagram login |

Secrets are never visible in logs or to visitors. Restart the Space after changing them
(**Settings → Factory reboot** is not needed; *Restart this Space* is enough).

You can also paste the YouTube key straight into the app's YouTube page — but on a Space without
persistent storage it is lost on restart, so the secret above is the better place.

## 5. Optional: keep your data

**Settings → Persistent storage → Small ($5/mo, 20 GB)** mounts `/data`, and the app switches to it
automatically — the database, model cache and settings then survive restarts and sleep.

---

## Updating

```bash
git add -A && git commit -m "update" && git push space main
```

The Space rebuilds itself.

## If the build fails

- **`no space left on device`** — the image is large; remove the model-baking line from the
  Dockerfile (`RUN python -c "from transformers import pipeline; ..."`) and it downloads on first
  boot instead.
- **Build timeout** — same fix; baking the model is what takes the longest.
- **Port errors** — the Space must be Docker SDK with `app_port: 7860` in the README front matter.
