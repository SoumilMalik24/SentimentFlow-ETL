# SentimentFlow

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![HuggingFace](https://img.shields.io/badge/Model-HuggingFace-orange?logo=huggingface&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?logo=github-actions&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

**SentimentFlow** is an end-to-end **Data Engineering + NLP pipeline** that autonomously gathers and analyzes news sentiment for a curated list of startups.

It performs a **daily sync** by fetching global articles via NewsAPI, detecting which startups are mentioned using a high-speed **Aho-Corasick** automaton, running **zero-shot NLI sentiment analysis** per startup, and storing results in a PostgreSQL database.

A **Streamlit Admin Dashboard** manages tracked startups, and a **Plotly Analytics Dashboard** visualizes live sentiment trends across sectors.

---

## Tech Stack

| Layer | Technology | Purpose |
| :-- | :-- | :-- |
| **Language** | Python 3.11 | Core logic & scripting |
| **Database** | PostgreSQL | Relational data storage |
| **Data Fetching** | NewsAPI | Source for global news articles |
| **ML Model** | [Soumil24/zero-shot-startup-sentiment-v2](https://huggingface.co/Soumil24/zero-shot-startup-sentiment-v2) | Zero-Shot NLI model |
| **NLP Libraries** | `transformers`, `torch` | Model inference |
| **Core Libraries** | `psycopg2`, `pyahocorasick` | DB connection & high-speed text matching |
| **Visualization** | `plotly`, `pandas` | Interactive charts |
| **Admin UI** | Streamlit | Web-based admin & analytics dashboards |
| **Container** | Docker + Docker Compose | Reproducible deployment |
| **Automation** | GitHub Actions | Scheduled ETL runs (3× daily) |

---

## Core Features

- **Automated 3×/Day Pipeline** — runs via GitHub Actions at 7 AM, 1 PM, 7 PM IST
- **Dynamic Fetch Logic** — 30-day _backfill_ for new startups, 1-day _maintenance_ for existing ones
- **Keyword-Driven Queries** — auto-builds NewsAPI queries using `findingKeywords`
- **High-Performance Search** — Aho-Corasick automaton detects 30+ startups in a single text pass
- **Bulk AI Analysis** — Zero-Shot sentiment inference in mini-batches for GPU efficiency
- **Analytics Dashboard** — Plotly charts: sentiment breakdown, sector comparison, trend over time
- **Admin Dashboard** — add/update startups through the browser (single form or bulk JSON)
- **Transactional Integrity** — all DB operations occur in atomic transactions

---

## Project Structure

```
SentimentFlow/
├── .github/workflows/
│   └── main_pipeline.yml       # CI/CD — runs ETL 3× daily
├── notebooks/
│   ├── 01_DatasetSetup.ipynb   # Dataset preparation for model training
│   └── 02_ModelTraining.ipynb  # Fine-tuning the NLI sentiment model
├── scripts/
│   └── seed_sector.py          # Seeds Sector table with 30 sectors
├── src/
│   ├── core/
│   │   ├── config.py           # Loads environment via Pydantic Settings
│   │   └── logger.py           # Rotating file + console logging
│   ├── constants/
│   │   └── __init__.py         # Global constants (batch size, timeouts)
│   ├── pipeline/
│   │   └── __init__.py         # Main ETL orchestrator (Steps 1–8)
│   └── utils/
│       ├── api_utils.py        # NewsAPI calls, key rotation, threading
│       ├── db_utils.py         # PostgreSQL reads/writes & dashboard queries
│       ├── sentiment_utils.py  # Zero-shot model & mini-batch inference
│       └── text_utils.py       # Aho-Corasick engine & ID generator
├── ARCHITECTURE.md             # System design & data flow diagram
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Multi-service setup (DB + pipeline + dashboards)
├── main.py                     # Pipeline entry point
├── requirements.txt            # Python dependencies
├── streamlit_admin.py          # Admin dashboard (port 8501)
└── streamlit_dashboard.py      # Analytics dashboard (port 8502)
```

---

## Database Design

A **4-table relational model** links startups to articles and sentiments.

| Table | Key Columns |
| :-- | :-- |
| `Sector` | `id` (PK), `name` |
| `Startups` | `id` (PK), `name`, `sectorId` (FK), `description`, `findingKeywords` |
| `Articles` | `id` (PK), `title`, `content`, `url` (UNIQUE), `publishedAt` |
| `ArticlesSentiment` | `id` (PK), `articleId` (FK), `startupId` (FK), `positiveScore`, `negativeScore`, `neutralScore`, `sentiment` |

---

## Sentiment Analysis Logic

The project uses a **Zero-Shot NLI** model — not a conventional sentiment classifier — allowing startup-specific sentiment detection even in multi-company articles.

**Model:** [`Soumil24/zero-shot-startup-sentiment-v2`](https://huggingface.co/Soumil24/zero-shot-startup-sentiment-v2)

For each article × startup pair, 3 hypotheses are evaluated:
```
Premise:    "Swiggy's revenue jumps, but Zomato's losses widen…"
Hypothesis: "the news for Swiggy is positive"  → 0.87 ✅
            "the news for Swiggy is neutral"   → 0.09
            "the news for Swiggy is negative"  → 0.04
```
The label with the **highest entailment probability** becomes the final sentiment.

---

## Getting Started

### Option A — Docker (Recommended)

The fastest way to run everything at once:

```bash
# 1. Clone the repo
git clone https://github.com/SoumilMalik24/SentimentFlow.git
cd SentimentFlow

# 2. Create your .env file (see Environment section below)
cp .env.example .env   # then fill in your values

# 3. Start all services
docker compose up
```

This spins up:
- PostgreSQL on port `5432`
- Admin Dashboard on [http://localhost:8501](http://localhost:8501)
- Analytics Dashboard on [http://localhost:8502](http://localhost:8502)

To run the pipeline manually:
```bash
docker compose run pipeline python main.py
```

---

### Option B — Local Setup

```bash
# 1. Create virtual environment
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
# Create .env with the variables shown below
```

---

## Environment Variables

Create a `.env` file in the project root:

```
DB_URL=postgresql://user:pass@host:port/dbname
NEWS_API_KEYS=["key1","key2"]
HF_TOKEN=your_huggingface_token
MODEL_PATH=Soumil24/zero-shot-startup-sentiment-v2
```

---

## Running the Project

### 1. Seed Sectors (first-time setup)
```bash
python scripts/seed_sector.py
```

### 2. Admin Dashboard
```bash
streamlit run streamlit_admin.py
```
Open [http://localhost:8501](http://localhost:8501) → Add startups via the form or bulk JSON upload.

### 3. Main Pipeline
```bash
python main.py
```

### 4. Analytics Dashboard
```bash
streamlit run streamlit_dashboard.py
```
Open [http://localhost:8502](http://localhost:8502) → View sentiment charts and trends.

---

## CI/CD Automation

Configured to run automatically via **GitHub Actions**.

| Setting | Value |
| :-- | :-- |
| **Workflow File** | `.github/workflows/main_pipeline.yml` |
| **Schedule** | Runs 3× per day — 7 AM, 1 PM, and 7 PM (IST) |
| **Required Secrets** | `DB_URL`, `NEWS_API_KEYS`, `HF_TOKEN`, `MODEL_PATH` |

---

## Notebooks

The `notebooks/` directory contains the full model development story:

| Notebook | Description |
| :-- | :-- |
| `01_DatasetSetup.ipynb` | Converts financial news into NLI format for training |
| `02_ModelTraining.ipynb` | Fine-tunes the zero-shot NLI model on the prepared dataset |

---

## License

This project is released under the **MIT License**.  
Feel free to **fork**, **adapt**, and **build upon it** — credit is appreciated!

---

## Developer

**Soumil Malik**  
🔗 [GitHub @SoumilMalik24](https://github.com/SoumilMalik24)  
🤗 [HuggingFace Model](https://huggingface.co/Soumil24/zero-shot-startup-sentiment-v2)
