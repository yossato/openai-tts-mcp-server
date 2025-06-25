# OpenAI TTS MCP Server

This repository contains a Model Context Protocol (MCP) server for text-to-speech
using OpenAI's API. The server exposes a set of tools that allow clients to
generate speech audio, play it back, and manage presets for different voices.

## Features

- Generate speech from text through the OpenAI TTS API
- Streaming playback using the OpenAI audio helper
- Optional caching of generated files
- Support for multiple voices and audio formats

## Quick start

1. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file containing your API key:

   ```bash
   OPENAI_API_KEY=sk-...
   ```

3. Run the server

   ```bash
   python -m src.main
   ```

The original development notes are available in
`DEVELOPMENT_PLAN.md`.
