"""
Lycan Bot - Social Webhook Server
Handles Twitch EventSub and YouTube WebSub push notifications.
Runs on port 6100, exposed via Cloudflare tunnel.
"""

import os
import hmac
import hashlib
import logging
import asyncio
from datetime import datetime
from typing import Optional
import aiohttp

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import PlainTextResponse
import uvicorn

# Logger
logger = logging.getLogger("LYCAN.webhooks")

# Configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "lycan-webhook-secret-2024")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
CALLBACK_URL = os.getenv("WEBHOOK_CALLBACK_URL", "https://socials.powerbrigade.online")

# FastAPI app
app = FastAPI(title="Lycan Webhooks", docs_url=None, redoc_url=None)

# Reference to Discord bot (set by main.py)
discord_bot = None

def set_discord_bot(bot):
    """Set reference to Discord bot for sending notifications."""
    global discord_bot
    discord_bot = bot
    logger.info("Discord bot reference set for webhooks")


# ==================== TWITCH EVENTSUB ====================

@app.post("/twitch/callback")
async def twitch_eventsub_callback(request: Request):
    """Handle Twitch EventSub notifications."""
    body = await request.body()
    headers = request.headers
    
    # Verify signature
    message_id = headers.get("Twitch-Eventsub-Message-Id", "")
    timestamp = headers.get("Twitch-Eventsub-Message-Timestamp", "")
    signature = headers.get("Twitch-Eventsub-Message-Signature", "")
    
    if signature:
        message = message_id + timestamp + body.decode()
        expected = "sha256=" + hmac.new(
            WEBHOOK_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected):
            logger.warning("Invalid Twitch signature")
            raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Parse payload
    import json
    try:
        payload = json.loads(body)
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    message_type = headers.get("Twitch-Eventsub-Message-Type", "")
    
    # Handle verification challenge
    if message_type == "webhook_callback_verification":
        challenge = payload.get("challenge", "")
        logger.info(f"Twitch EventSub verification: {challenge[:20]}...")
        return PlainTextResponse(challenge)
    
    # Handle notification
    if message_type == "notification":
        subscription_type = payload.get("subscription", {}).get("type", "")
        event = payload.get("event", {})
        
        if subscription_type == "stream.online":
            await handle_stream_online(event)
        
        return Response(status_code=204)
    
    # Handle revocation
    if message_type == "revocation":
        logger.warning(f"Twitch subscription revoked: {payload}")
        return Response(status_code=204)
    
    return Response(status_code=204)


async def handle_stream_online(event: dict):
    """Handle stream.online event from Twitch."""
    broadcaster_id = event.get("broadcaster_user_id", "")
    broadcaster_name = event.get("broadcaster_user_name", "")
    broadcaster_login = event.get("broadcaster_user_login", "")
    
    logger.info(f"🔴 STREAM ONLINE: {broadcaster_name} ({broadcaster_login})")
    
    if not discord_bot:
        logger.warning("No Discord bot reference, cannot send notification")
        return
    
    # Get stream details from Twitch API
    stream_data = await get_twitch_stream_data(broadcaster_login)
    
    # Find feeds for this streamer
    feeds = await discord_bot.db.fetch(
        "SELECT * FROM social_feeds WHERE platform = 'twitch' AND LOWER(channel_id) = $1",
        broadcaster_login.lower()
    )
    
    for feed in feeds:
        guild = discord_bot.get_guild(feed['guild_id'])
        if not guild:
            continue
        
        channel = guild.get_channel(feed['discord_channel_id'])
        if not channel:
            continue
        
        # Create embed
        from modules.socials import SocialsCog
        cog = discord_bot.get_cog("SocialsCog")
        if cog and stream_data:
            embed = cog._create_twitch_embed(stream_data, broadcaster_login)
            custom_msg = feed.get('custom_message', '') or ''
            # Add @everyone before custom message
            full_msg = f"@everyone {custom_msg}".strip()
            await channel.send(content=full_msg, embed=embed)
            logger.info(f"Sent Twitch notification to {guild.name}#{channel.name}")
        
        # Update last_notified
        await discord_bot.db.execute(
            "UPDATE social_feeds SET last_notified_at = NOW() WHERE id = $1",
            feed['id']
        )


async def get_twitch_stream_data(login: str) -> Optional[dict]:
    """Get current stream data from Twitch API."""
    token = await get_twitch_token()
    if not token:
        return None
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.twitch.tv/helix/streams?user_login={login}",
            headers={
                "Client-ID": TWITCH_CLIENT_ID,
                "Authorization": f"Bearer {token}"
            }
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                streams = data.get("data", [])
                return streams[0] if streams else None
    return None


async def get_twitch_token() -> Optional[str]:
    """Get Twitch app access token."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials"
            }
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("access_token")
    return None


# ==================== YOUTUBE WEBSUB ====================

@app.get("/youtube/callback")
async def youtube_websub_verify(request: Request):
    """Handle YouTube WebSub subscription verification."""
    params = request.query_params
    
    mode = params.get("hub.mode", "")
    challenge = params.get("hub.challenge", "")
    topic = params.get("hub.topic", "")
    
    logger.info(f"YouTube WebSub verification: mode={mode}, topic={topic[:50]}...")
    
    if mode == "subscribe" and challenge:
        return PlainTextResponse(challenge)
    
    if mode == "unsubscribe" and challenge:
        return PlainTextResponse(challenge)
    
    raise HTTPException(status_code=400, detail="Invalid verification request")


@app.post("/youtube/callback")
async def youtube_websub_notification(request: Request):
    """Handle YouTube WebSub notifications (new video/update)."""
    body = await request.body()
    
    # Parse Atom XML
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(body)
    except:
        logger.error("Failed to parse YouTube notification XML")
        return Response(status_code=200)
    
    # Namespaces
    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'yt': 'http://www.youtube.com/xml/schemas/2015'
    }
    
    # Extract video info
    entry = root.find('atom:entry', ns)
    if entry is None:
        logger.warning("No entry in YouTube notification")
        return Response(status_code=200)
    
    video_id = entry.find('yt:videoId', ns)
    channel_id = entry.find('yt:channelId', ns)
    title = entry.find('atom:title', ns)
    author = entry.find('atom:author/atom:name', ns)
    
    if video_id is None or channel_id is None:
        return Response(status_code=200)
    
    video_id = video_id.text
    channel_id_text = channel_id.text
    title_text = title.text if title is not None else "New Video"
    author_text = author.text if author is not None else channel_id_text
    
    logger.info(f"📺 NEW VIDEO: {author_text} - {title_text}")
    
    await handle_youtube_video(channel_id_text, video_id, title_text, author_text)
    
    return Response(status_code=200)


async def handle_youtube_video(channel_id: str, video_id: str, title: str, author: str):
    """Handle new YouTube video notification."""
    if not discord_bot:
        logger.warning("No Discord bot reference")
        return
    
    video_url = f"https://youtube.com/watch?v={video_id}"
    
    # Find feeds for this channel
    feeds = await discord_bot.db.fetch(
        "SELECT * FROM social_feeds WHERE platform = 'youtube' AND channel_id = $1",
        channel_id
    )
    
    for feed in feeds:
        guild = discord_bot.get_guild(feed['guild_id'])
        if not guild:
            continue
        
        channel = guild.get_channel(feed['discord_channel_id'])
        if not channel:
            continue
        
        # Create embed
        cog = discord_bot.get_cog("SocialsCog")
        if cog:
            embed = cog._create_youtube_embed(title, author, video_url)
            custom_msg = feed.get('custom_message', '') or ''
            # Add @everyone before custom message
            full_msg = f"@everyone {custom_msg}".strip()
            await channel.send(content=full_msg, embed=embed)
            logger.info(f"Sent YouTube notification to {guild.name}#{channel.name}")
        
        # Update last_notified
        await discord_bot.db.execute(
            "UPDATE social_feeds SET last_notified_at = NOW() WHERE id = $1",
            feed['id']
        )


# ==================== SUBSCRIPTION MANAGEMENT ====================

async def subscribe_twitch_eventsub(broadcaster_login: str) -> bool:
    """Subscribe to stream.online event for a Twitch channel."""
    token = await get_twitch_token()
    if not token:
        logger.error("Failed to get Twitch token for EventSub subscription")
        return False
    
    # First get user ID from login
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.twitch.tv/helix/users?login={broadcaster_login}",
            headers={
                "Client-ID": TWITCH_CLIENT_ID,
                "Authorization": f"Bearer {token}"
            }
        ) as resp:
            if resp.status != 200:
                return False
            data = await resp.json()
            users = data.get("data", [])
            if not users:
                logger.error(f"Twitch user not found: {broadcaster_login}")
                return False
            broadcaster_id = users[0]["id"]
    
    # Create EventSub subscription
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            headers={
                "Client-ID": TWITCH_CLIENT_ID,
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "type": "stream.online",
                "version": "1",
                "condition": {
                    "broadcaster_user_id": broadcaster_id
                },
                "transport": {
                    "method": "webhook",
                    "callback": f"{CALLBACK_URL}/twitch/callback",
                    "secret": WEBHOOK_SECRET
                }
            }
        ) as resp:
            if resp.status in (200, 202):
                logger.info(f"✅ Subscribed to Twitch EventSub for {broadcaster_login}")
                return True
            else:
                error = await resp.text()
                logger.error(f"Failed to subscribe Twitch EventSub: {resp.status} - {error}")
                return False


async def subscribe_youtube_websub(youtube_channel_id: str) -> bool:
    """Subscribe to YouTube WebSub for a channel."""
    topic_url = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={youtube_channel_id}"
    hub_url = "https://pubsubhubbub.appspot.com/subscribe"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            hub_url,
            data={
                "hub.mode": "subscribe",
                "hub.topic": topic_url,
                "hub.callback": f"{CALLBACK_URL}/youtube/callback",
                "hub.verify": "async"
            }
        ) as resp:
            if resp.status == 202:
                logger.info(f"✅ Subscribed to YouTube WebSub for {youtube_channel_id}")
                return True
            else:
                error = await resp.text()
                logger.error(f"Failed to subscribe YouTube WebSub: {resp.status} - {error}")
                return False


# ==================== ADMIN ENDPOINTS ====================

@app.post("/admin/subscribe-all")
async def admin_subscribe_all():
    """Subscribe all existing feeds to EventSub/WebSub (for migration)."""
    if not discord_bot:
        return {"error": "No bot reference"}
    
    results = {"twitch": [], "youtube": []}
    
    # Get all Twitch feeds
    twitch_feeds = await discord_bot.db.fetch(
        "SELECT DISTINCT channel_id FROM social_feeds WHERE platform = 'twitch'"
    )
    
    for feed in twitch_feeds:
        channel = feed['channel_id']
        success = await subscribe_twitch_eventsub(channel)
        results["twitch"].append({"channel": channel, "success": success})
    
    # Get all YouTube feeds
    youtube_feeds = await discord_bot.db.fetch(
        "SELECT DISTINCT channel_id FROM social_feeds WHERE platform = 'youtube'"
    )
    
    for feed in youtube_feeds:
        channel = feed['channel_id']
        success = await subscribe_youtube_websub(channel)
        results["youtube"].append({"channel": channel, "success": success})
    
    return results


# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "lycan-webhooks"}


# ==================== RUNNER ====================

def run_webhook_server():
    """Run the webhook server (blocking)."""
    uvicorn.run(app, host="0.0.0.0", port=6100, log_level="info")


async def start_webhook_server_async():
    """Start webhook server in async context."""
    config = uvicorn.Config(app, host="0.0.0.0", port=6100, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
