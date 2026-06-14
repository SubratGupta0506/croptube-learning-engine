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

You can run n8n in two ways: using **n8n Cloud / an existing instance**, or **self-hosting it for free with Docker + ngrok**.

#### Option A: Existing / Cloud n8n instance

1. Import `workflows/croptube_learning_workflow.json` into your n8n instance.
2. Replace `YOUR_YOUTUBE_API_KEY` placeholders with your YouTube Data API key (or set up an n8n credential/env variable).
3. Replace `your-s3-bucket-name` with your actual S3 bucket name.
4. Configure an AWS S3 credential in n8n for the "Upload a file" node.
5. Activate the workflow and submit the form with a crop name and language.

#### Option B: Self-hosted n8n with Docker + ngrok (free)

This setup runs n8n locally for free and exposes the form trigger's webhook URL to the internet via ngrok, so it can be reached from anywhere.

1. **Run n8n with Docker:**
   ```bash
   docker run -it --rm \
     --name n8n \
     -p 5678:5678 \
     -v n8n_data:/home/node/.n8n \
     docker.n8n.io/n8nio/n8n
   ```
   n8n will now be available at `http://localhost:5678`.

2. **Expose it with ngrok:**

   Install ngrok from [ngrok.com](https://ngrok.com) and authenticate it with your token (`ngrok config add-authtoken <your_token>`), then run:
   ```bash
   ngrok http 5678
   ```
   ngrok will give you a public URL like `https://abcd1234.ngrok-free.app`.

3. **Set the webhook URL so n8n generates correct links:**

   Stop the container and re-run it with the `WEBHOOK_URL` environment variable set to your ngrok URL:
   ```bash
   docker run -it --rm \
     --name n8n \
     -p 5678:5678 \
     -v n8n_data:/home/node/.n8n \
     -e WEBHOOK_URL=https://abcd1234.ngrok-free.app/ \
     -e N8N_EDITOR_BASE_URL=https://abcd1234.ngrok-free.app/ \
     docker.n8n.io/n8nio/n8n
   ```
   This makes the "On form submission" node generate a public form URL using your ngrok domain instead of `localhost`.

4. **Import and configure the workflow:**
   - Open `http://localhost:5678` (or your ngrok URL) in a browser.
   - Import `workflows/croptube_learning_workflow.json`.
   - Replace `YOUR_YOUTUBE_API_KEY` placeholders with your YouTube Data API key.
   - Replace `your-s3-bucket-name` with your actual S3 bucket name.
   - Add an AWS credential in n8n (Settings → Credentials → AWS) for the "Upload a file" node.
   - Activate the workflow.

5. **Share the form:**
   - Open the "On form submission" node and copy the **Production URL** — it will now use your ngrok domain, e.g. `https://abcd1234.ngrok-free.app/form/<webhook-id>`.
   - Anyone with this link can submit crop name + language to trigger the workflow, as long as your Docker container and ngrok tunnel are running.

> **Note:** The free ngrok URL changes every time you restart ngrok (unless you set up a reserved domain on a paid ngrok plan). If the URL changes, update `WEBHOOK_URL` / `N8N_EDITOR_BASE_URL` and re-share the new form link.

### 3. API

1. Install dependencies: `pip install fastapi boto3 uvicorn`
2. Set environment variables (`S3_BUCKET_NAME`, `AWS_REGION`).
3. Mount `learning_videos.py` as a router in your FastAPI app.
4. Ensure `config/auth.py` provides a `verify_token` dependency for JWT auth.

## How to Use

### Step 1: Generate a video set (n8n workflow)

1. Open your n8n instance and activate the **CropTube_Learning_Workflow**.
2. Open the form trigger's production URL (n8n shows this on the "On form submission" node):
   - If using **n8n Cloud / an existing instance**: `https://<your-n8n-domain>/form/<webhook-id>`
   - If using **self-hosted Docker + ngrok**: `https://<your-ngrok-subdomain>.ngrok-free.app/form/<webhook-id>` — make sure the Docker container and ngrok tunnel are both running.
3. Fill in the form:
   - **crop_name** — e.g. `Rice`, `Chilli`, `Cashew`, `Tulsi`
   - **language** — select from the dropdown (English, Kannada, Telugu, Tamil, Malayalam, Hindi)
4. Submit the form. The workflow runs automatically:
   - Searches YouTube for `<crop_name> farming <language>`
   - Fetches statistics and duration for each result
   - Scores and ranks videos (higher score for title relevance, view count, and farming-related keywords; videos under 2 min or over 30 min are discarded)
   - Splits the top 15 into 4 "initial" + up to 11 "load more" videos
   - Uploads the result as `learning-videos/<crop_name>_<language>.json` to your S3 bucket
5. Repeat this for each crop + language combination you want to support (e.g. `rice_english.json`, `rice_kannada.json`, `chilli_tamil.json`, etc.).

### Step 2: Run the API

1. Install dependencies:
   ```bash
   pip install fastapi boto3 uvicorn python-jose
   ```
2. Set environment variables (from `.env`):
   ```bash
   export S3_BUCKET_NAME=your-bucket-name
   export AWS_REGION=ap-south-1
   ```
   Make sure your environment also has AWS credentials available (via `~/.aws/credentials`, IAM role, or `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` env vars) so `boto3` can read from S3.
3. Mount the router in your FastAPI app, e.g. in `main.py`:
   ```python
   from fastapi import FastAPI
   from api.learning_videos import router as learning_router

   app = FastAPI()
   app.include_router(learning_router, prefix="/api")
   ```
4. Make sure `config/auth.py` exists and exports a `verify_token` function (a FastAPI dependency that validates a JWT and returns a user ID). This project assumes you already have user authentication set up; plug in your own implementation.
5. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

### Step 3: Call the API from your app

Once the server is running (e.g. on `http://localhost:8000`), and assuming videos were generated for "Rice" in "Kannada":

1. **Check availability before fetching** (optional but recommended):
   ```
   GET /api/learning/check?crop_name=Rice&language=Kannada
   Authorization: Bearer <your_jwt_token>
   ```
   Response:
   ```json
   {
     "status": "ok",
     "available": true,
     "message": "Videos available for Rice in Kannada"
   }
   ```

2. **Fetch the initial batch** (first 4 videos, shown on page load):
   ```
   GET /api/learning/videos?crop_name=Rice&language=Kannada
   Authorization: Bearer <your_jwt_token>
   ```
   Response:
   ```json
   {
     "status": "ok",
     "data": {
       "meta": { "crop": "Rice", "language": "Kannada", "generated_at": "2026-06-14", ... },
       "videos": [ /* up to 4 video objects */ ],
       "has_more": true,
       "total_initial": 4
     }
   }
   ```

3. **Fetch more videos** when the user taps "Load More":
   ```
   GET /api/learning/videos/more?crop_name=Rice&language=Kannada
   Authorization: Bearer <your_jwt_token>
   ```
   Response:
   ```json
   {
     "status": "ok",
     "data": {
       "videos": [ /* remaining video objects */ ],
       "has_more": false
     }
   }
   ```

4. **Get the list of supported languages** (e.g. to populate a dropdown in your UI):
   ```
   GET /api/learning/languages
   Authorization: Bearer <your_jwt_token>
   ```
   Response:
   ```json
   {
     "status": "ok",
     "data": {
       "languages": [
         { "code": "english", "label": "English", "native": "English" },
         { "code": "kannada", "label": "Kannada", "native": "ಕನ್ನಡ" },
         ...
       ]
     }
   }
   ```

### Each video object looks like:

```json
{
  "id": 1,
  "batch": "initial",
  "title": "Rice Farming Techniques for Beginners",
  "channel": "AgriTips Channel",
  "duration": "12:34",
  "thumbnail": {
    "url": "https://i.ytimg.com/vi/.../hqdefault.jpg",
    "alt": "Rice Farming Techniques for Beginners - AgriTips Channel"
  },
  "description": "Learn the basics of rice cultivation...",
  "link": {
    "label": "Watch on YouTube",
    "url": "https://www.youtube.com/watch?v=..."
  }
}
```

### Notes

- If a crop + language combination hasn't been generated yet via the n8n workflow, `/learning/videos` and `/learning/videos/more` will return a `404` with a helpful message — run Step 1 for that combination first.
- The `language` parameter is case-insensitive but must match one of: `english`, `kannada`, `telugu`, `tamil`, `malayalam`, `hindi`.
- All four endpoints require a valid JWT — make sure your client sends `Authorization: Bearer <token>` on every request.

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
