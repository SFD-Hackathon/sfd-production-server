# Quick Start Guide - Drama JSON Viewer

## 1. Install Dependencies

```bash
# From project root
pip install streamlit
# Or install all dependencies
pip install -r requirements.txt
```

## 2. Start API Server

```bash
# Terminal 1
python main.py
```

The API server should be running at `http://localhost:8000`.

## 3. Start Viewer

```bash
# Terminal 2
streamlit run viewer/app.py

# Or use the quick start script
./run_viewer.sh
```

The viewer will open in your browser at `http://localhost:8501`.

## 4. Load a Drama

### Option A: Enter Drama ID
1. Type or paste a drama ID in the sidebar input
2. Press Enter

### Option B: Browse Existing Dramas
1. Click "Browse Dramas" in the sidebar
2. Select a drama from the dropdown
3. Click "Load Selected"

### Option C: Create a New Drama First
```bash
# Create drama via API
curl -X POST http://localhost:8000/dramas \
  -H "Content-Type: application/json" \
  -d '{"premise": "A detective in a cyberpunk city solves crimes using AI"}'

# Copy the drama ID from response
# Paste into viewer sidebar
```

## 5. Explore Features

- **Overview Tab**: See drama metadata and statistics
- **Characters Tab**: View/generate character portraits
- **Episodes Tab**: Browse episode and scene hierarchy
- **Assets Tab**: View all generated images and videos
- **Jobs Tab**: Monitor generation job status

## 6. Generate Assets

### Generate Full Drama
1. Click "🎬 Generate Full Drama" in sidebar
2. Wait for DAG execution (5-15 minutes)
3. Check Jobs tab for progress

### Generate Single Character
1. Go to Characters tab
2. Click "Generate Portrait" on any character without a portrait
3. Poll Jobs tab for completion

## 7. Improve Drama

1. Expand "💡 Improve Drama" in sidebar
2. Enter feedback (e.g., "Make the detective more cynical")
3. Click "Submit Improvement"
4. Wait for improvement job to complete
5. Refresh to see updated drama

## Troubleshooting

### Viewer won't start
```bash
# Make sure streamlit is installed
pip install streamlit

# Check version
streamlit version
```

### Can't load drama
- Verify API server is running: `curl http://localhost:8000/docs`
- Check drama ID is correct
- Look at API server logs for errors

### Assets not showing
- Check R2 configuration in API server `.env`
- Verify `R2_PUBLIC_URL` is accessible
- Check Assets tab filters aren't hiding results

### Jobs stuck in "running"
- Check API server logs for errors
- Verify Gemini/Sora API keys are valid
- Check `./jobs/` directory has job files

## Next Steps

See `viewer/README.md` for full documentation including:
- Architecture details
- API client reference
- Development guide
- Advanced features

Happy debugging! 🎬
