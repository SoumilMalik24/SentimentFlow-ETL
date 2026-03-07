# SentimentFlow

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![HuggingFace](https://img.shields.io/badge/Model-HuggingFace-orange?logo=huggingface&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Hub-2496ED?logo=docker&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?logo=github-actions&logoColor=white)
![Streamlit](https://img.shields.io/badge/Admin-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Cloudinary](https://img.shields.io/badge/Images-Cloudinary-3448C5?logo=cloudinary&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What Is SentimentFlow?

**SentimentFlow** is a fully automated, end-to-end **Data Engineering + NLP pipeline** that tracks real-time news sentiment for a curated portfolio of startups.

Every day, it:
1. Queries **NewsAPI** for articles relevant to tracked startups
2. Confirms startup mentions using **context-aware regex** word-boundary matching
3. Runs **zero-shot NLI sentiment analysis** per article × startup pair
4. Stores all results in a **PostgreSQL database**
5. Makes data available to any connected analytics frontend

A **Streamlit Admin Dashboard** lets you add/manage startups and upload company images (with 1:1 crop via Cloudinary). A **GitHub Actions** workflow runs the pipeline 3× daily without any manual intervention.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SENTIMENTFLOW PIPELINE                      │
│                                                                     │
│   ┌──────────┐    ┌────────────────┐    ┌──────────────────────┐   │
│   │ Startups │───▶│  Query Builder │───▶│ NewsAPI (threaded)   │   │
│   │   (DB)   │    │ (sector+key-   │    │ excludeDomains filter│   │
│   └──────────┘    │  words, 1-day/ │    └──────────┬───────────┘   │
│                   │  30-day logic) │               │               │
│                   └────────────────┘    ┌──────────▼───────────┐   │
│                                         │ Deduplicate by URL   │   │
│                                         │ Merge candidates     │   │
│                                         └──────────┬───────────┘   │
│                                                    │               │
│                                         ┌──────────▼───────────┐   │
│                                         │  Context-Aware Regex  │   │
│                                         │  (\b word boundary)  │   │
│                                         └──────────┬───────────┘   │
│                                                    │               │
│                                         ┌──────────▼───────────┐   │
│                                         │   NLI Sentiment Model │   │
│                                         │   (mini-batch, CPU)   │   │
│                                         └──────────┬───────────┘   │
│                                                    │               │
│                                         ┌──────────▼───────────┐   │
│                                         │   PostgreSQL          │   │
│                                         │   (atomic commit)     │   │
│                                         └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|:--|:--|:--|
| **Language** | Python 3.11 | Core logic and scripting |
| **Database** | PostgreSQL | Relational data storage |
| **Data Fetching** | NewsAPI | Source for global news articles |
| **ML Framework** | `transformers`, `torch` | NLI model inference |
| **Sentiment Model** | [Soumil24/zero-shot-startup-sentiment-v2](https://huggingface.co/Soumil24/zero-shot-startup-sentiment-v2) | Custom fine-tuned zero-shot NLI |
| **Text Matching** | Python `re` (regex) | Context-aware word-boundary matching |
| **Admin UI** | Streamlit | Startup management + image upload |
| **Image Storage** | Cloudinary | Startup logo hosting with CDN |
| **Config** | `pydantic-settings` | Type-safe `.env` loading |
| **Container** | Docker | Reproducible pipeline deployment |
| **Automation** | GitHub Actions | Scheduled ETL (3× daily) |

---

## Core Features

### Pipeline
- **3× Daily Automation** — GitHub Actions cron at 7 AM, 1 PM, 7 PM IST
- **Smart Fetch Logic** — new startups get a 30-day backfill; existing ones get 1-day incremental updates
- **Thread-Safe API Key Rotation** — round-robin across multiple NewsAPI keys using a `threading.Lock`
- **Domain Filtering** — `excludeDomains` sent directly to NewsAPI to block GitHub, PyPI, Reddit, StackOverflow, etc. at the source
- **Context-Propagation Matching** — each article is tagged with its query's 1–3 candidate startups and confirmed with `\b` regex word boundaries. Prevents false positives like `"StripeAPI"` matching `"Stripe"`
- **Zero-Shot NLI Sentiment** — 3 hypotheses per startup ("the news for X is positive/neutral/negative"), highest entailment probability wins
- **Mini-Batch Inference** — model runs in batches of 32 to stay within CPU/RAM limits
- **Atomic Transactions** — all DB writes commit together; failure triggers a full rollback
- **Deduplication** — articles deduplicated by URL before DB insert; candidates merged when same URL appears in multiple queries

### Admin Dashboard
- **3-Tab Interface** — Add/Edit startup, Bulk JSON upload, and dedicated Image Upload
- **Deterministic IDs** — startup IDs generated as `{name}-{6hex}-{4hex}` (e.g. `swiggy-911365-81d2`) — re-adding the same startup safely upserts without duplication
- **Cloudinary Integration** — upload logo, crop to 1:1 square with interactive handles, push to Cloudinary CDN, URL auto-saved to DB
- **Image-Missing Filter** — Image Upload tab shows only startups that don't have a logo yet
- **Session-Managed Image Flow** — uploaded Cloudinary URL persists in `st.session_state` until the startup form is saved

---

## Project Structure

```
SentimentFlow/
│
├── .github/
│   └── workflows/
│       └── main_pipeline.yml       # GitHub Actions — runs ETL 3× daily
│
├── admin/                          # Streamlit admin — modular package
│   ├── __init__.py
│   ├── cloudinary_utils.py         # Cloudinary init, upload, 1:1 crop widget
│   ├── db_loaders.py               # Cached @st.cache_data DB loaders
│   ├── startup_helpers.py          # Startup upsert logic, JSON batch processor
│   └── streamlit_admin.py          # Pure UI — imports from above modules
│
├── notebooks/
│   ├── 01_DatasetSetup.ipynb       # 5-source NLI dataset assembly
│   ├── 02_First_Model.ipynb        # Baseline model training
│   ├── 03_Model_Improvement.ipynb  # Final fine-tuning run
│   └── README.md                   # Notebook documentation
│
├── scripts/
│   └── seed_sector.py              # Seeds 30 sectors into the Sector table
│
├── src/
│   ├── constants/
│   │   └── __init__.py             # Global constants (batch size, timeouts, etc.)
│   ├── core/
│   │   ├── config.py               # pydantic-settings .env config loader
│   │   └── logger.py               # Rotating file + console logger
│   ├── pipeline/
│   │   └── __init__.py             # 8-step ETL orchestrator
│   └── utils/
│       ├── api_utils.py            # NewsAPI queries, threading, deduplication
│       ├── db_utils.py             # All PostgreSQL read/write functions
│       ├── sentiment_utils.py      # NLI model loader + bulk inference
│       └── text_utils.py          # Regex startup matching + ID generator
│
├── Dockerfile                      # Pipeline-only image (requirements-pipeline.txt)
├── docker-compose.yml              # Multi-service orchestration
├── main.py                         # ETL pipeline entry point
├── requirements.txt                # Full deps (pipeline + admin)
├── requirements-pipeline.txt       # Minimal deps for Docker (no Streamlit/Cloudinary)
└── .env                            # Local secrets (never committed)
```

---

## Database Schema

```
┌──────────┐          ┌────────────────────┐
│  Sector  │          │      Startups       │
│──────────│          │────────────────────│
│ id  (PK) │◄────────│ id           (PK)   │
│ name     │          │ name                │
└──────────┘          │ sectorId     (FK)   │
                      │ description         │
                      │ imageUrl            │
                      │ findingKeywords      │
                      │ createdAt           │
                      └────────┬───────────┘
                               │
                    ┌──────────▼──────────────┐
                    │    ArticlesSentiment     │
                    │─────────────────────────│
                    │ id            (PK)       │
                    │ startupId     (FK) ──────┘
                    │ articleId     (FK) ──┐
                    │ positiveScore        │
                    │ negativeScore        │
                    │ neutralScore         │
                    │ sentiment            │
                    │ createdAt            │
                    └──────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │       Articles      │
                    │─────────────────────│
                    │ id          (PK)    │
                    │ title               │
                    │ url         (UNIQUE)│
                    │ content             │
                    │ publishedAt         │
                    │ createdAt           │
                    └─────────────────────┘
```

---

## Sentiment Analysis — How It Works

The model used is **not a standard positive/negative classifier**. It is a **Zero-Shot Natural Language Inference (NLI)** model fine-tuned on financial and startup news.

**Why NLI?** NLI lets the model reason about sentiment *in the context of a specific entity*. The same article can be simultaneously positive for one startup and negative for another — NLI handles this correctly, a standard classifier cannot.

### Inference Flow

For every `(article, startup)` pair, three hypothesis–premise pairs are evaluated:

```
Premise:
  "Swiggy's revenue jumped 40% YoY while Zomato posted wider losses..."

Hypothesis 1: "the news for Swiggy is positive"  → entailment score: 0.87 ✅
Hypothesis 2: "the news for Swiggy is neutral"   → entailment score: 0.09
Hypothesis 3: "the news for Swiggy is negative"  → entailment score: 0.04

→ Final sentiment: POSITIVE (argmax)
```

```
Same article, different startup:
Hypothesis 1: "the news for Zomato is positive"  → 0.11
Hypothesis 2: "the news for Zomato is neutral"   → 0.21
Hypothesis 3: "the news for Zomato is negative"  → 0.68 ✅

→ Final sentiment: NEGATIVE (argmax)
```

### Model Training

The model (`Soumil24/zero-shot-startup-sentiment-v2`) was fine-tuned from `facebook/bart-large-mnli` on a custom dataset assembled from 5 financial news sources including Financial PhraseBank and Twitter Financial News. See `notebooks/` for the full training story.

---

## Startup Matching — Context-Propagation + Regex

### The Problem with Naive Search
A global scan of all 37+ startup names across every article creates false positives. For example, `"StripeAPI"` matches `"Stripe"`, or `"listo-mcp-ip-guard"` spuriously matches a short startup name embedded in a compound word.

### The Solution: Context-Propagation
Each NewsAPI query is built for **1–3 specific startups**. Instead of discarding this context after fetching, SentimentFlow **propagates the candidate startup list with each article** through the entire pipeline:

```python
# api_utils.py — article is tagged with its query's candidates
(article_dict, [{"id": "stripe-...", "name": "Stripe"}])

# text_utils.py — only those 1–3 candidates are checked
pattern = r'\b' + re.escape(startup['name']) + r'\b'
re.search(pattern, article_text, re.IGNORECASE)
```

`\b` enforces word boundaries — `"Stripe"` matches in `"Stripe raised $1B"` but not in `"StripeAPI"`.

---

## Getting Started

### Prerequisites
- Python 3.11
- PostgreSQL database (local or cloud, e.g. Neon, Supabase, Prisma Data Platform)
- NewsAPI key (free tier: [newsapi.org](https://newsapi.org))
- HuggingFace account (for model access)
- Cloudinary account (free tier, for admin image uploads)

---

### Option A — Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/SoumilMalik24/SentimentFlow-ETL.git
cd SentimentFlow-ETL

# 2. Create virtual environment
python -m venv myenv
# Windows
myenv\Scripts\activate
# Linux / macOS
source myenv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment — create a .env file in the project root:
```

```env
DB_URL=postgresql://user:password@host:5432/dbname
NEWS_API_KEYS=["your_key_1","your_key_2"]
HF_TOKEN=hf_your_huggingface_token
MODEL_PATH=Soumil24/zero-shot-startup-sentiment-v2
LOG_DIR=logs

CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

```bash
# 5. Seed the Sector table (first-time only)
python scripts/seed_sector.py

# 6. Launch the admin dashboard to add startups
streamlit run admin/streamlit_admin.py

# 7. Run the ETL pipeline
python main.py
```

---

### Option B — Docker (Pipeline Only)

The Docker image is built from `requirements-pipeline.txt` — it does **not** include Streamlit or Cloudinary to keep the image lean.

```bash
# Pull and run the pipeline
docker pull soumilmalik/sentimentflow:latest
docker run --env-file .env soumilmalik/sentimentflow:latest

# Build locally from source
docker build -t soumilmalik/sentimentflow:latest .
docker push soumilmalik/sentimentflow:latest
```

---

## Admin Dashboard

Run with:
```bash
streamlit run admin/streamlit_admin.py
```

### Tab 1 — Add / Edit Startup
Fill in name, sector, description, and optional keywords. Use the **Upload & Crop Image** expander to upload a logo directly — it gets cropped to 1:1, pushed to Cloudinary, and the URL is auto-filled when you save.

Startup IDs are **deterministic**: `{name-kebab}-{6hex}-{4hex}` (e.g. `swiggy-911365-81d2`). Re-submitting the same name + sector safely upserts without creating a duplicate.

### Tab 2 — Bulk Upload JSON
Upload a JSON array of startup objects. Each must have `name`, `sector`, `description`. Optional: `keywords` (list), `imageUrl`.

```json
[
  {
    "name": "Swiggy",
    "sector": "FoodTech",
    "description": "Indian online food ordering and delivery platform.",
    "keywords": ["food delivery", "quick commerce", "Sriharsha Majety"],
    "imageUrl": ""
  }
]
```

### Tab 3 — Upload Company Image
Shows **only startups that do not have an image URL**. Select from the dropdown, upload a file, drag the 1:1 crop handles, and click Upload. The cropped image is pushed to Cloudinary and the `secure_url` is saved to the DB instantly.

---

## CI/CD — GitHub Actions

The workflow `.github/workflows/main_pipeline.yml` triggers automatically:

| Trigger | Schedule |
|:--|:--|
| Cron 1 | `30 1 * * *` → 7:00 AM IST |
| Cron 2 | `30 7 * * *` → 1:00 PM IST |
| Cron 3 | `30 13 * * *` → 7:00 PM IST |
| Manual | `workflow_dispatch` from GitHub Actions UI |

### GitHub Secrets Required

Go to **Repo → Settings → Secrets and variables → Actions → New repository secret**:

| Secret Name | Description |
|:--|:--|
| `DB_URL` | PostgreSQL connection string |
| `NEWS_API_KEYS` | JSON array string: `["key1","key2"]` |
| `MODEL_PATH` | `Soumil24/zero-shot-startup-sentiment-v2` |
| `HF_TOKEN` | HuggingFace API token |

> Cloudinary secrets are **not needed** in GitHub — they are only used by the admin UI.

---

## Streamlit Cloud Deployment (Admin)

To host the admin dashboard publicly on [streamlit.io/cloud](https://streamlit.io/cloud):

1. Connect your GitHub repo
2. Set **Main file path**: `admin/streamlit_admin.py`
3. Set **Python version**: 3.11
4. Add secrets under **App Settings → Secrets** in TOML format:

```toml
DB_URL = "postgresql://user:pass@host/db"
NEWS_API_KEYS = '["key1","key2"]'
HF_TOKEN = "hf_..."
MODEL_PATH = "Soumil24/zero-shot-startup-sentiment-v2"
CLOUDINARY_CLOUD_NAME = "your_cloud"
CLOUDINARY_API_KEY = "your_key"
CLOUDINARY_API_SECRET = "your_secret"
```

---

## Environment Variables — Where Each Secret Goes

| Variable | GitHub Actions | Streamlit Cloud |
|:--|:--|:--|
| `DB_URL` | ✅ | ✅ |
| `NEWS_API_KEYS` | ✅ | ❌ |
| `HF_TOKEN` | ✅ | ❌ |
| `MODEL_PATH` | ✅ | ❌ |
| `CLOUDINARY_CLOUD_NAME` | ❌ | ✅ |
| `CLOUDINARY_API_KEY` | ❌ | ✅ |
| `CLOUDINARY_API_SECRET` | ❌ | ✅ |

---

## Research Notebooks

See `notebooks/README.md` for full documentation. Summary:

| # | Notebook | What It Does |
|:--|:--|:--|
| 01 | `01_DatasetSetup.ipynb` | Assembles NLI training data from 5 financial news datasets |
| 02 | `02_First_Model.ipynb` | Baseline training run on `facebook/bart-large-mnli` |
| 03 | `03_Model_Improvement.ipynb` | Final fine-tuning with improved tokenization + `[ENTITY]` handling |

**Final Model:** [Soumil24/zero-shot-startup-sentiment-v2](https://huggingface.co/Soumil24/zero-shot-startup-sentiment-v2)

---

## License

Released under the **MIT License** — fork, adapt, and build upon it freely. Credit appreciated.

---

## Developer

**Soumil Malik**
🔗 [GitHub @SoumilMalik24](https://github.com/SoumilMalik24)
🤗 [HuggingFace Model](https://huggingface.co/Soumil24/zero-shot-startup-sentiment-v2)
🐳 [DockerHub](https://hub.docker.com/r/soumilmalik/sentimentflow)
