# OpenAI TTS MCP Server

This repository contains a Model Context Protocol (MCP) server for text-to-speech
using OpenAI's API. The server exposes a set of tools that allow clients to
generate speech audio, play it back, and manage presets for different voices.

## Features

- Generate speech from text through the OpenAI TTS API
- Streaming playback using the OpenAI audio helper
- Optional caching of generated files
- Support for multiple voices and audio formats

The code in `src/` implements the server and helpers. See
`DEVELOPMENT_PLAN.md` for the original phased development notes.
