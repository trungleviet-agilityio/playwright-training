#!/bin/bash

echo "🚀 Setting up Playwright Auth POC with uv..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Create virtual environment with uv
echo "📦 Creating virtual environment..."
uv venv

# Install dependencies using uv
echo "📥 Installing dependencies..."
uv pip install -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
uv run playwright install chromium

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️ Creating .env file..."
    cp .env.example .env
    echo "📝 Please edit .env file with your test credentials"
fi

echo "✅ Setup complete!"
echo "🎯 To run the application:"
echo "   uv run python -m src.main"
echo ""
echo "🧪 To run tests:"
echo "   uv run pytest tests/ -v"