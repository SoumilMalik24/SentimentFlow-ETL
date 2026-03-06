# SentimentFlow — Notebooks

This folder contains the complete ML model development story behind SentimentFlow.

## Notebooks

| File | Description |
|---|---|
| `01_DatasetSetup.ipynb` | Prepares the training dataset by converting financial news headlines into NLI (Natural Language Inference) format with positive / neutral / negative hypothesis pairs |
| `02_ModelTraining.ipynb` | Fine-tunes the `facebook/bart-large-mnli` base model on the prepared dataset, evaluates performance (precision / recall / F1), and saves the fine-tuned model to HuggingFace |

## Model

The resulting model is hosted publicly on HuggingFace:  
👉 [Soumil24/zero-shot-startup-sentiment-v2](https://huggingface.co/Soumil24/zero-shot-startup-sentiment-v2)

## How to Run

These notebooks are designed to run on **Google Colab** (GPU recommended).

1. Open the notebook in Colab
2. Set your `HF_TOKEN` in the secrets panel
3. Run all cells top-to-bottom
