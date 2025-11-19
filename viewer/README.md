# Drama JSON Viewer

A Streamlit-based debugging interface for viewing and interacting with dramas from the Drama Generation API.

## Features

- **Drama Overview**: View drama metadata, premise, themes, and statistics
- **Character Viewer**: Display character portraits, descriptions, and details
- **Episode/Scene Browser**: Navigate through episodes and scenes with collapsible sections
- **Asset Gallery**: Browse all generated assets (images, videos) with filtering
- **Job Tracking**: Monitor generation jobs and their status
- **Interactive Actions**: Generate assets, improve dramas, get AI critiques
- **Auto-refresh**: Optional 30-second auto-refresh for monitoring long-running jobs

## Setup

### Prerequisites

1. API server must be running (default: `http://localhost:8000`)
2. Install dependencies:

```bash
pip install -r requirements.txt
```

This will install Streamlit and all required dependencies.

### Environment Variables (Optional)

Create a `.env` file in the project root if you need to customize:

```bash
# API Configuration
API_BASE_URL=http://localhost:8000
API_KEY=your-api-key-if-required
```

## Usage

### Start the Viewer

```bash
# From project root
streamlit run viewer/app.py

# Or specify port
streamlit run viewer/app.py --server.port 8501
```

The viewer will open in your browser at `http://localhost:8501`.

### Navigate the Interface

1. **Enter Drama ID**: Type or paste a drama ID in the sidebar
2. **Or Browse**: Click "Browse Dramas" to select from existing dramas
3. **View Tabs**:
   - **Overview**: Drama metadata and statistics
   - **Characters**: Character cards with portraits
   - **Episodes**: Hierarchical episode/scene structure
   - **Assets**: Gallery of all generated assets
   - **Jobs**: Generation job history and status

### Actions

The sidebar provides quick actions:

- **Generate Full Drama**: Trigger hierarchical DAG generation for all assets
- **Improve Drama**: Submit feedback to improve the drama structure
- **Get AI Critique**: Request AI-powered critique of the drama
- **Delete Drama**: Remove drama and all associated assets (danger zone)

### Character Generation

In the Characters tab, you can:
- View character portraits (if generated)
- Click "Generate Portrait" button to create missing portraits
- View character details and descriptions

### Auto-Refresh

Enable "Auto-refresh (30s)" in the sidebar to automatically reload the page every 30 seconds. Useful for monitoring:
- Long-running generation jobs
- Asset upload progress
- Job status updates

## Development

### Project Structure

```
viewer/
├── app.py                      # Main Streamlit application
├── utils.py                    # API client utilities
├── components/                 # UI components
│   ├── character_view.py      # Character display logic
│   ├── episode_view.py        # Episode/scene display logic
│   └── asset_view.py          # Asset gallery and jobs
└── README.md                   # This file
```

### Adding New Features

**Add a new tab:**

1. Create component in `viewer/components/`
2. Import in `app.py`
3. Add tab in the `st.tabs()` call
4. Call your render function in the tab context

**Add new API endpoints:**

1. Update `viewer/utils.py` - add method to `DramaAPIClient`
2. Use the method in your component

**Customize styling:**

Edit the CSS in `app.py` within the `st.markdown()` block.

## API Client

The viewer uses a custom API client (`viewer/utils.py`) with methods for:

- `get_drama(drama_id)` - Fetch drama by ID
- `list_dramas(skip, limit)` - List all dramas with pagination
- `get_job(drama_id, job_id)` - Get job status
- `list_jobs(drama_id)` - List all jobs for drama
- `generate_full_drama(drama_id)` - Trigger full DAG generation
- `generate_character(drama_id, character_id)` - Generate character portrait
- `improve_drama(drama_id, feedback)` - Submit improvement feedback
- `critique_drama(drama_id)` - Get AI critique
- `delete_drama(drama_id)` - Delete drama
- `list_assets(user_id, project_name, ...)` - List assets from asset library

## Troubleshooting

### "Failed to load drama"

- Ensure API server is running: `python main.py`
- Check drama ID is correct
- Verify API server is accessible at `http://localhost:8000`

### "Failed to load assets"

- Assets are stored in R2 - check R2 configuration in API server
- Verify `R2_PUBLIC_URL` is set correctly
- Check asset library has assets for the drama

### Authentication errors

- If API requires authentication, set `API_KEY` environment variable
- Or update `API_KEYS` in API server `.env` to allow unauthenticated access during development

### Port already in use

```bash
# Use a different port
streamlit run viewer/app.py --server.port 8502
```

## Tips

1. **Quick debugging**: Keep the viewer open while developing - use auto-refresh to monitor changes
2. **Testing generation**: Use the "Generate Full Drama" button to test the entire DAG pipeline
3. **Asset verification**: Check the Assets tab to verify all assets uploaded correctly to R2
4. **Job monitoring**: The Jobs tab shows detailed history - useful for debugging failed generations
5. **Raw JSON**: Every section has a "Raw JSON" expander for detailed inspection

## Differences from Web Viewer

This Python viewer is designed for **debugging**, not production use:

- **Simpler UI**: Focus on functionality over aesthetics
- **Direct API access**: No client-side state management complexity
- **Co-located**: Shares codebase with API server
- **Quick iterations**: Hot reload for rapid development
- **Built-in tools**: Streamlit provides JSON viewer, image/video display out of the box

For production user-facing drama viewing, use the Next.js web app in `../drama-json-viewer-web`.

## Future Enhancements

Potential features to add:

- [ ] Compare dramas side-by-side
- [ ] Export drama to different formats (PDF, Markdown)
- [ ] Inline editing of drama fields
- [ ] Batch operations (generate multiple characters at once)
- [ ] Visual DAG graph of generation dependencies
- [ ] Real-time job progress with WebSocket updates
- [ ] Asset preview with lightbox/modal
- [ ] Search/filter across all dramas
- [ ] Analytics dashboard (total assets, generation time, etc.)

## License

Same as parent project.
