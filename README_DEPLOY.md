# CBIO204 Biobank — Render deployment

## Render settings
- Service type: Web Service
- Runtime: Python 3
- Build Command: leave blank (or `pip install -r requirements.txt`)
- Start Command: `python app.py`
- Health Check Path: `/`

The application reads Render's `PORT` environment variable and binds to `0.0.0.0`.
