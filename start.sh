#!/bin/bash
# Start script for MCP server
# Install dependencies if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    deactivate
fi

# Run the service
source venv/bin/activate
python3 main.py
