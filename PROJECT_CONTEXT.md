# Bitcoin Transaction Analysis — Project Context

## Problem Statement
Build a system for Bitcoin transaction analysis that can ingest transaction
data, construct transaction/address relationships, engineer useful features,
detect/analyze suspicious activity, expose results through an API, and
visualize the results through a dashboard.

## Current Architecture

Dataset
   ↓
Ingestion
   ↓
Data Cleaning / Normalization
   ↓
Feature Engineering
   ↓
ML / Anomaly Detection
   ↓
Graph Analysis
   ↓
FastAPI
   ↓
Dashboard

## Current Dataset

Dataset version: v1

Current data:
- Synthetic Bitcoin transaction dataset
- Generated for development/testing
- Contains transaction-level information
- Used to test ingestion and downstream pipeline

Important:
Do not redesign the dataset schema without discussing it first.

## Dataset Schema

in the dataset file

## Completed

- Problem statement understood
- Initial architecture decided
- Synthetic dataset v1 generated
- Dataset reviewed for initial development
- Development pipeline defined

## Not Completed

- Production ingestion
- Feature engineering
- ML/anomaly detection
- Graph construction
- API integration
- Dashboard
- Explainability
- Final polish

## Tech Stack

- Python
- Pandas
- NetworkX
- Scikit-learn
- FastAPI
- React
- Tailwind CSS
- [Other technologies actually being used]

## Design Decisions

- Use modular pipeline architecture
- Keep ingestion separate from feature engineering
- Keep ML separate from graph analysis
- API acts as bridge between backend analysis and dashboard
- Do not unnecessarily rewrite completed components

## Known Issues

- Dataset is synthetic
- Real Bitcoin data integration is pending
- Some assumptions in synthetic data may need validation
- Dataset schema should remain stable unless a concrete requirement requires modification

## Current Task

Build the ingestion pipeline for Dataset v1.

The next developer should:
1. Inspect the current dataset.
2. Validate its schema and data types.
3. Build the ingestion module.
4. Add validation and basic cleaning.
5. Produce a clean internal representation.
6. Do NOT start feature engineering yet.
7. Update this file when the task is completed.