#!/bin/bash
# Quick start script for Drama JSON Viewer

echo "Starting Drama JSON Viewer..."
echo "Make sure the API server is running at http://localhost:8000"
echo ""

# Check if API server is running
if ! curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "⚠️  Warning: API server doesn't seem to be running"
    echo "Start it with: python main.py"
    echo ""
fi

# Start Streamlit
streamlit run viewer/app.py
