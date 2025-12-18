import asyncio
import random
import os
import sys
import discord
import wavelink
import spotipy
import lyricsgenius
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
from discord.ui import View

# ================= COPYRIGHT =================
# This bot is developed by Mac GunJon.
# Copyright © 2023 Mac GunJon. All rights reserved.
# Redistribution or modification without permission is prohibited.
# For inquiries, contact: macgunjon@example.com

# ================= BASE CONFIG =================
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

TOKEN = os.getenv("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")

LAVALINK_HOST = os.getenv("LAVALINK_HOST", "127.0.0.1")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

# ================= CLIENTS =================
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
)

genius = lyricsgenius.Genius(
    GENIUS_TOKEN,
    skip_non_songs=True,
    excluded_terms=["(Remix)", "(Live)"]
)

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None  # ❌ disable default help
)

tree = bot.tree


# ================= MUSIC STATE =================
class MusicState:

    def __init__(self):
        self.queue = []
        self.current = None
        self.previous = None
        self.loop = False
        self.autoplay = False


music_states = {}


# ================= LAVALINK =================
@bot.event
async def on_ready():
    if not wavelink.Pool.nodes:
        await wavelink.Pool.connect(
            nodes=[
                wavelink.Node(
                    uri=f"http://{LAVALINK_HOST}:{LAVALINK_PORT}",
                    password=LAVALINK_PASSWORD
                )
            ],
            client=bot
        )

    await tree.sync()
    print(f"✅ Logged in as {bot.user}")
    print("✅ Lavalink connected")


def node_ready():
    return any(
        node.status == wavelink.NodeStatus.CONNECTED
        for node in wavelink.Pool.nodes.values()
    )


# ================= TRACK RESOLVE =================
async def resolve_tracks(query: str, requester: discord.Member):
    tracks = []

    # Spotify playlist
    if "spotify.com/playlist" in query:
        playlist_id = query.split("/")[-1].split("?")[0]
        results = sp.playlist_items(playlist_id)

        for item in results["items"]:
            track = item.get("track")
            if not track:
                continue

            search = f"{track['name']} {track['artists'][0]['name']}"
            found = await wavelink.Playable.search(f"ytmsearch:{search}")

            if found:
                found[0].extras = {"requester_id": requester.id}
                tracks.append(found[0])

        return tracks

    search_order = [
        f"ytmsearch:{query}",
        f"ytsearch:{query}",
        query,
    ]

    for q in search_order:
        found = await wavelink.Playable.search(q)
        if found:
            found[0].extras = {"requester_id": requester.id}
            return [found[0]]

    return []


# ================= QUEUE HANDLER =================
async def play_next(player: wavelink.Player, gid: int):
    state = music_states.get(gid)
    if not state:
        return

    if state.loop and state.current:
        await player.play(state.current)
        return

    if state.queue:
        state.previous = state.current
        state.current = state.queue.pop(0)
        await player.play(state.current)
    else:
        state.current = None


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    if payload.reason == "FINISHED":
        await play_next(payload.player, payload.player.guild.id)


# ================= CONTROLS =================
class MusicControlView(View):

    def __init__(self, player: wavelink.Player, guild_id: int):
        super().__init__(timeout=None)
        self.player = player
        self.guild_id = guild_id

    def _check_user(self, interaction: discord.Interaction):
        if not interaction.user.voice or interaction.user.voice.channel != self.player.channel:
            asyncio.create_task(
                interaction.response.send_message(
                    embed=discord.Embed(
                        title="Access Restricted",
                        description="To use this control, please join the same voice channel as the bot.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
            )
            return False
        return True

    @discord.ui.button(label="🔉 Down", style=discord.ButtonStyle.secondary)
    async def volume_down(self, interaction, _):
        if not self._check_user(interaction):
            return
        await self.player.set_volume(max(1, self.player.volume - 10))
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Audio Level Changed",
                description=f"Playback volume successfully adjusted to **{self.player.volume}%**.",
                color=discord.Color.blurple(),
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="🔊 Up", style=discord.ButtonStyle.secondary)
    async def volume_up(self, interaction, _):
        if not self._check_user(interaction):
            return
        await self.player.set_volume(min(1000, self.player.volume + 10))
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Audio Level Changed",
                description=f"Playback volume successfully adjusted to **{self.player.volume}%**.",
                color=discord.Color.blurple(),
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="⏮ Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, _):
        if not self._check_user(interaction):
            return

        state = music_states[self.guild_id]
        if state.previous:
            state.queue.insert(0, state.current)
            state.current = state.previous
            await self.player.play(state.current)
            text = "The previous track is now playing."
            color = discord.Color.green()
        else:
            text = "No previously played track is available."
            color = discord.Color.red()

        await interaction.response.send_message(
            embed=discord.Embed(title="⏮ Playback Reverted", description=text, color=color),
            ephemeral=True,
        )

    @discord.ui.button(label="⏸ Pause", style=discord.ButtonStyle.primary)
    async def pause_resume(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self._check_user(interaction):
            return

        # ▶ Resume
        if self.player.paused:
            await self.player.pause(False)
            button.label = "⏸ Pause"

        # ⏸ Pause
        else:
            await self.player.pause(True)
            button.label = "▶ Resume"

        # 🔴 IMPORTANT: update ONLY the view (no embed change)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏭ Skip", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction, _):
        if not self._check_user(interaction):
            return
        await self.player.stop()
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⏭ Track Skipped",
                description="The current track has been skipped successfully.",
                color=discord.Color.blurple(),
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="🔀 Shuffle", style=discord.ButtonStyle.secondary)
    async def shuffle(self, interaction, _):
        if not self._check_user(interaction):
            return
        random.shuffle(music_states[self.guild_id].queue)
        await interaction.response.send_message(
            embed=discord.Embed(title="🔀 Queue Shuffled", description="Tracks in the queue have been shuffled.", color=discord.Color.blurple()),
            ephemeral=True,
        )

    @discord.ui.button(label="🔁 Loop", style=discord.ButtonStyle.secondary)
    async def loop(self, interaction, _):
        if not self._check_user(interaction):
            return
        state = music_states[self.guild_id]
        state.loop = not state.loop
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔁 Playback Loop",
                description=f"Continuous playback is now **{'active' if state.loop else 'inactive'}**.",
                color=discord.Color.green() if state.loop else discord.Color.red(),
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction, _):
        if not self._check_user(interaction):
            return
        await self.player.disconnect()
        music_states.pop(self.guild_id, None)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Music Stopped",
                description="Playback has ended and the bot has left the voice channel.",
                color=discord.Color.red(),
            ),
            view=None,
        )


# ================= /PLAY =================
@tree.command(name="play", description="Play a song or playlist")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer(thinking=True)

    if not node_ready():
        return await interaction.followup.send(
            embed=discord.Embed(title="❌ Lavalink Offline"),
            ephemeral=True,
        )

    if not interaction.user.voice:
        return await interaction.followup.send(
            embed=discord.Embed(
                title="Voice Channel Required",
                description="Please join a voice channel to start music playback.",
                color=discord.Color.orange(),
            ),
            ephemeral=True,
        )

    player: wavelink.Player = interaction.guild.voice_client
    if not player:
        player = await interaction.user.voice.channel.connect(cls=wavelink.Player)

    state = music_states.setdefault(interaction.guild.id, MusicState())

    tracks = await resolve_tracks(query, interaction.user)
    if not tracks:
        return await interaction.followup.send(
            embed=discord.Embed(
                title="No Matching Content",
                description="Your search did not return any playable results.",
            ),
            ephemeral=True,
        )

    for t in tracks:
        if not player.playing:
            state.current = t
            await player.play(t)
        else:
            state.queue.append(t)

    track = tracks[0]
    requester = interaction.user

    embed = discord.Embed(
        title="🎵 MUSIC PANEL",
        description="Use the buttons below to control playback.",
        color=discord.Color.blurple(),
    )

    embed.add_field(name="🎶 Song", value=f"[{track.title}]({track.uri})", inline=False)
    embed.add_field(name="🎧 Requested By", value=requester.mention, inline=True)
    embed.add_field(
        name="⏱ Duration",
        value=f"{track.length // 60000}m {(track.length // 1000) % 60}s",
        inline=True,
    )
    embed.add_field(name="✍ Author", value=track.author, inline=True)

    embed.set_author(name=requester.display_name, icon_url=requester.display_avatar.url)

    if track.artwork:
        embed.set_thumbnail(url=track.artwork)

    await interaction.followup.send(
        embed=embed,
        view=MusicControlView(player, interaction.guild.id),
    )


# ================= /LYRICS =================
@tree.command(name="lyrics", description="Get lyrics of current song")
async def lyrics(interaction: discord.Interaction):
    state = music_states.get(interaction.guild.id)
    if not state or not state.current:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="No Music Playing",
                description="There’s no active playback right now. Use the play command to start music.",
            ),
            ephemeral=True,
        )

    song = genius.search_song(state.current.title, state.current.author)
    if not song:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="Lyrics Unavailable",
                description="Lyrics for the current track could not be found.",
            ),
            ephemeral=True,
        )

    embed = discord.Embed(
        title=f"🎤 {song.title}",
        description=song.lyrics[:4000],
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed)


# ================= /QUEUE =================
@tree.command(name="queue", description="Show the current music queue")
async def queue(interaction: discord.Interaction):
    state = music_states.get(interaction.guild.id)
    if not state or not state.queue:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="Queue Empty",
                description="The music queue is currently empty.",
                color=discord.Color.orange(),
            ),
            ephemeral=True,
        )

    embed = discord.Embed(
        title="🎵 Music Queue",
        description="\n".join([f"{i+1}. {track.title} - {track.author}" for i, track in enumerate(state.queue[:10])]),
        color=discord.Color.blurple(),
    )
    if len(state.queue) > 10:
        embed.set_footer(text=f"And {len(state.queue) - 10} more...")
    await interaction.response.send_message(embed=embed)


# ================= /NOWPLAYING =================
@tree.command(name="nowplaying", description="Show the currently playing song")
async def nowplaying(interaction: discord.Interaction):
    state = music_states.get(interaction.guild.id)
    if not state or not state.current:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="No Music Playing",
                description="There’s no active playback right now.",
                color=discord.Color.orange(),
            ),
            ephemeral=True,
        )

    player = interaction.guild.voice_client
    if not player:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="Bot Not in Voice",
                description="The bot is not connected to a voice channel.",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )

    track = state.current
    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"[{track.title}]({track.uri}) by {track.author}",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="⏱ Duration",
        value=f"{track.length // 60000}m {(track.length // 1000) % 60}s",
        inline=True,
    )
    embed.add_field(
        name="🔊 Volume",
        value=f"{player.volume}%",
        inline=True,
    )
    if track.artwork:
        embed.set_thumbnail(url=track.artwork)
    await interaction.response.send_message(embed=embed)


# ================= /REMOVE =================
@tree.command(name="remove", description="Remove a song from the queue by position")
async def remove(interaction: discord.Interaction, position: int):
    state = music_states.get(interaction.guild.id)
    if not state or not state.queue:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="Queue Empty",
                description="The music queue is currently empty.",
                color=discord.Color.orange(),
            ),
            ephemeral=True,
        )

    if position < 1 or position > len(state.queue):
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="Invalid Position",
                description="Please provide a valid position in the queue.",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )

    removed_track = state.queue.pop(position - 1)
    await interaction.response.send_message(
        embed=discord.Embed(
            title="Track Removed",
            description=f"Removed **{removed_track.title}** from the queue.",
            color=discord.Color.green(),
        ),
        ephemeral=True,
    )


# ================= !HELP =================
@bot.command(name="musichelp")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="🎵 Music Bot Help",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="/play <song | link>",
        value="Plays a song or playlist from YouTube or Spotify.",
        inline=False,
    )
    embed.add_field(
        name="/lyrics",
        value="Displays the lyrics of the currently playing track.",
        inline=False,
    )
    embed.add_field(
        name="/queue",
        value="Shows the current music queue.",
        inline=False,
    )
    embed.add_field(
        name="/nowplaying",
        value="Shows details of the currently playing song.",
        inline=False,
    )
    embed.add_field(
        name="/remove <position>",
        value="Removes a song from the queue by its position number.",
        inline=False,
    )
    embed.add_field(
        name="Playback Controls",
        value="Pause, resume, skip, loop, shuffle, and adjust volume using the control buttons.",
        inline=False,
    )
    embed.set_footer(
        text="Powered by Mac GunJon • Lavalink • Wavelink"
    )
    await ctx.send(embed=embed)


# ================= RUN =================
bot.run(TOKEN)
