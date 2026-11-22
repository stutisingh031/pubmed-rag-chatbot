# BRCA1 Research Assistant — Frontend

This is the standalone React/Vite client. It communicates with the FastAPI backend over HTTP; it does not contain scientific source data or model credentials.

## Configure and run

```powershell
Copy-Item .env.example .env
npm install
npm run dev
```

Set `VITE_API_URL` in `.env` to the backend base URL (default `http://127.0.0.1:8000`). No API key is used. The backend must allow the Vite origin in `CORS_ORIGINS`.

The app provides two working views: **Research chat** and a searchable **Source library** with links to the PubMed records. Chat suggestions submit directly, and **New chat** clears the current conversation.
