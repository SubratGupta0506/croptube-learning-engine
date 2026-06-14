# CropTube Learning Engine

An automated pipeline that curates crop-specific farming tutorial videos from YouTube, ranks them by relevance and popularity, filters out non-farming content (gaming, dairy, livestock, etc.), and serves them through a REST API for use in mobile/web apps.

## Overview

1. A form trigger (via n8n) accepts a crop name and target language.
2. The workflow searches YouTube Data API for relevant farming videos.
3. Videos are scored based on view count, title relevance, and duration, then ranked.
4. The top results are split into an "initial" batch (first 4) and a "load more" batch.
5. Results are uploaded as JSON to an S3 bucket, keyed by crop and language.
6. A FastAPI backend serves this data to client apps, with an additional content filter to strip out gaming/livestock videos that slip through the initial ranking.

## Architecture

```
Form Submission (crop_name, language)
        |
        v
YouTube Search API  ----->  YouTube Videos API (stats/details)
        |
        v
Scoring & Ranking (JS)
        |
        v
Format & Batch Split (JS)
        |
        v
Upload to S3 (learning-videos/<crop>_<language>.json)
        |
        v
FastAPI endpoints (filter + serve to client)
```

## Tech Stack

- **n8n** — workflow automation / orchestration
- **YouTube Data API v3** — video search and metadata
- **AWS S3** — storage for generated video lists
- **FastAPI** — backend API serving filtered video data
- **Python (boto3, re)** — content filtering and S3 access

## Project Structure

```
croptube-learning-engine/
├── README.md
├── workflows/
│   └── croptube_learning_workflow.json   # n8n workflow export
├── api/
│   └── learning_videos.py                # FastAPI router
└── .env.example                          # required environment variables
```

## Setup

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```
YOUTUBE_API_KEY=your_youtube_api_key_here
AWS_REGION=ap-south-1
S3_BUCKET_NAME=your-bucket-name
```

### 2. n8n Workflow

1. Import `workflows/croptube_learning_workflow.json` into your n8n instance.
2. Replace `YOUR_YOUTUBE_API_KEY` placeholders with your YouTube Data API key (or set up an n8n credential/env variable).
3. Replace `your-s3-bucket-name` with your actual S3 bucket name.
4. Configure an AWS S3 credential in n8n for the "Upload a file" node.
5. Activate the workflow and submit the form with a crop name and language.

### 3. API

1. Install dependencies: `pip install fastapi boto3 uvicorn`
2. Set environment variables (`S3_BUCKET_NAME`, `AWS_REGION`).
3. Mount `learning_videos.py` as a router in your FastAPI app.
4. Ensure `config/auth.py` provides a `verify_token` dependency for JWT auth.

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/learning/videos` | GET | Returns the initial batch (4 videos) for a crop + language |
| `/learning/videos/more` | GET | Returns the remaining videos ("load more" batch) |
| `/learning/languages` | GET | Returns supported languages for the selector |
| `/learning/check` | GET | Checks whether a video set exists for a crop + language before fetching |

All endpoints require a valid auth token (JWT) via `verify_token`.

## Content Filtering

The API applies a regex-based filter (`is_real_farming_video`) on top of the curated dataset to remove videos that are actually about gaming (Minecraft, Farming Simulator, etc.) or unrelated livestock/dairy topics, ensuring only genuine crop-farming content reaches the end user.

## License

MIT
