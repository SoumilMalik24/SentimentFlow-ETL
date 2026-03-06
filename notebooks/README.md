# SentimentFlow — Experiment Notebooks

This folder contains the complete ML research and model development story behind SentimentFlow — from raw dataset assembly through to the final fine-tuned model deployed in the pipeline.

---

## Notebooks

| # | Notebook | Purpose |
|---|---|---|
| 01 | `01_DatasetSetup.ipynb` | Dataset sourcing and NLI formatting |
| 02 | `02_First_Model.ipynb` | Baseline model training and evaluation |
| 03 | `03_Model_Improvement.ipynb` | Improved tokenization and fine-tuning |

---

### `01_DatasetSetup.ipynb` — Dataset Sourcing & NLI Formatting

Assembles and prepares the training dataset by pulling from **5 public sources** and converting them into NLI (Natural Language Inference) format.

**Data sources used:**
1. `sweatSmile/news-sentiment-data` (HuggingFace)
2. Twitter Financial News Dataset
3. AG News Dataset
4. `news_sentiment_kaggle`
5. Financial PhraseBank Dataset

**Output format (NLI pairs):**
Each headline is converted into three hypothesis-entailment pairs:
```
Premise:    "Apple beats earnings estimates for Q3"
Hypothesis: "the news for Apple is positive"  → label: entailment
Hypothesis: "the news for Apple is neutral"   → label: neutral
Hypothesis: "the news for Apple is negative"  → label: contradiction
```
This format is what allows the model to do **zero-shot startup sentiment classification** at inference time.

---

### `02_First_Model.ipynb` — Baseline Model Training

First training attempt using the assembled NLI dataset. Loads and probes the dataset, runs initial inference to establish a baseline, and experiments with early loss behaviour.

**Base model:** `facebook/bart-large-mnli`
**Task:** Sequence classification (3-class NLI: entailment / neutral / contradiction)

---

### `03_Model_Improvement.ipynb` — Final Fine-Tuning

Improved training run with corrected tokenization, proper NLI dataset formatting with `[ENTITY]` token handling, and full `Trainer` API fine-tuning.

**Key steps:**
- `train_test_split` for reproducible evaluation
- `tokenize_fn` with padding and truncation
- `Trainer` + `TrainingArguments` from `transformers`
- Model saved and pushed to HuggingFace Hub

---

## Final Model

The model produced by Notebook 03 is publicly hosted on HuggingFace:

👉 **[Soumil24/zero-shot-startup-sentiment-v2](https://huggingface.co/Soumil24/zero-shot-startup-sentiment-v2)**

This is the model loaded by the production pipeline in `src/utils/sentiment_utils.py`.

---

## How to Run

These notebooks are designed to run on **Google Colab** (GPU strongly recommended — BART-large is too slow on CPU for training).

1. Open the notebook in Colab via **File → Open notebook → GitHub**
2. Set your `HF_TOKEN` in the **Colab Secrets panel** (🔑 icon on the left sidebar)
3. Run all cells top-to-bottom in order
4. Run notebooks in sequence: `01` → `02` → `03`

---

## Research Context

These notebooks document the **model selection and fine-tuning rationale** for the SentimentFlow minor project. The NLI-based zero-shot approach was chosen over a traditional positive/negative classifier because it allows the model to reason about sentiment *in the context of a specific startup* — e.g. the same article about "funding rounds" can be positive for a startup that raised money and negative for its competitor.
