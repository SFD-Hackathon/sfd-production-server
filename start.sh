#!/bin/bash

# Start script for Drama API Server

echo "🚀 Starting Drama API Server..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "⚙️  Please edit .env with your credentials before running."
    exit 1
fi

# Start server
echo "✅ Starting server on port ${PORT:-8000}..."
python main.py
