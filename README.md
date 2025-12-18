# Discord Music Bot (Python + Lavalink)

A production-ready Discord music bot built with Python, leveraging `discord.py`, `Wavelink`, and `Lavalink` to deliver high-quality audio playback with reliable queue management and modern slash command support.

---

## Overview

This project implements a scalable Discord music bot designed for stable deployment on cloud platforms such as Railway or VPS environments.  
Audio streaming is handled by an external Lavalink server to ensure performance and reliability.

---

## Key Features

- Slash command–based interface
- High-quality audio playback via Lavalink
- Queue and playlist management
- Spotify track integration
- Interactive message components (buttons)
- Modular and maintainable codebase
- Suitable for production deployment

---

## Technology Stack

- **Python 3.12**
- **discord.py**
- **Wavelink**
- **Lavalink (Java 17)**
- **Spotify Web API**

---

## Project Structure

music-bot-lavalink/
├── lava.py
├── requirements.txt
├── Procfile
├── runtime.txt
└── README.md

yaml
Copy code

---

## Prerequisites

- Python 3.12 or newer
- Java 17 (for Lavalink)
- A Discord bot application and token
- An externally hosted Lavalink server
- Spotify Developer credentials (optional)

---

## Environment Configuration

Set the following environment variables on your hosting platform:

DISCORD_TOKEN=your_discord_bot_token
LAVALINK_HOST=your_lavalink_server_ip
LAVALINK_PORT=2333
LAVALINK_PASSWORD=youshallnotpass
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

yaml
Copy code

> Security note:  
> Do not commit environment variables or `.env` files to version control.

---

## Local Development

Clone the repository and install dependencies:

```bash
git clone https://github.com/arkabarua69/music-bot-lavalink.git
cd music-bot-lavalink

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
python lava.py
Deployment
Railway
Push the project to GitHub

Create a new project on https://railway.app

Deploy from the GitHub repository

Set the start command:

nginx
Copy code
python lava.py
Configure environment variables

Deploy the service