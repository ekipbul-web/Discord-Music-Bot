import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import asyncio
import yt_dlp
import os
import random
import re
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

# Flask (Render için)
app = Flask(__name__)

@app.route('/')
def home():
    return "Kross Music Bot - Aktif"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Bot ayarları
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# -------------------- MÜZİK AYARLARI --------------------
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'music_cache/%(id)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    'socket_timeout': 30,
    'retries': 5,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
        }
    },
    'cookiefile': None,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 10 -analyzeduration 0',
    'options': '-vn -b:a 128k',
}

# Cache klasörü
if not os.path.exists('music_cache'):
    os.makedirs('music_cache')

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# -------------------- RENK PALETİ --------------------
class Colors:
    PRIMARY = 0x2B2D31
    SUCCESS = 0x57F287
    ERROR = 0xED4245
    WARNING = 0xFEE75C
    INFO = 0x5865F2
    QUEUE = 0x9B59B6
    PLAYING = 0x1DB954
    PAUSED = 0xF39C12

# -------------------- MÜZİK SINIFI --------------------
class MusicSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title', 'Bilinmeyen')
        self.url = data.get('webpage_url', data.get('url', ''))
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail', '')
        self.uploader = data.get('uploader', 'Bilinmeyen')
        self.views = data.get('view_count', 0)
        self.likes = data.get('like_count', 0)

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            
            if 'entries' in data:
                data = data['entries'][0]
            
            return cls(discord.FFmpegPCMAudio(data['url'], **ffmpeg_options), data=data)
        except Exception as e:
            print(f"Kaynak hatası: {e}")
            return None

# -------------------- MÜZİK PLAYER --------------------
class MusicPlayer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.queue = []
        self.history = []
        self.now_playing = None
        self.loop_mode = 'off'  # off, track, queue
        self.volume = 0.5
        self.start_time = None
        self.paused = False
        self.message = None
        self.auto_leave = 300  # 5 dakika boş kalınca çık
    
    async def add_to_queue(self, query, author, top=False):
        async with self.ctx.typing():
            sources = await self.search_tracks(query)
            
            if not sources:
                return None
            
            if not top:
                self.queue.extend(sources)
            else:
                self.queue = sources + self.queue
            
            return sources
    
    async def search_tracks(self, query):
        loop = asyncio.get_event_loop()
        
        if not query.startswith('http'):
            query = f"ytsearch:{query}"
        
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
            
            sources = []
            if 'entries' in data:
                for entry in data['entries'][:10]:  # Max 10 sonuç
                    if entry:
                        sources.append(MusicSource(
                            discord.FFmpegPCMAudio(entry['url'], **ffmpeg_options),
                            data=entry
                        ))
            else:
                sources.append(MusicSource(
                    discord.FFmpegPCMAudio(data['url'], **ffmpeg_options),
                    data=data
                ))
            
            return sources
        except Exception as e:
            print(f"Arama hatası: {e}")
            return []
    
    async def play_next(self):
        if self.loop_mode == 'track' and self.now_playing:
            self.queue.insert(0, self.now_playing)
        
        if self.queue:
            self.now_playing = self.queue.pop(0)
            self.start_time = datetime.now()
            
            try:
                self.ctx.voice_client.play(
                    self.now_playing,
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        self.handle_play_next(e), bot.loop
                    )
                )
                self.ctx.voice_client.source.volume = self.volume
                
                if self.message:
                    await self.update_now_playing()
                
            except Exception as e:
                print(f"Oynatma hatası: {e}")
                await self.play_next()
        else:
            self.now_playing = None
            self.start_time = None
            
            if self.message:
                await self.update_idle()
    
    async def handle_play_next(self, error):
        if error:
            print(f"Çalma hatası: {error}")
        
        if self.loop_mode == 'queue' and self.now_playing:
            self.queue.append(self.now_playing)
        
        await self.play_next()
    
    async def create_player_message(self):
        embed = self.create_idle_embed()
        view = MusicControls(self)
        self.message = await self.ctx.send(embed=embed, view=view)
    
    async def update_now_playing(self):
        if not self.message or not self.now_playing:
            return
        
        embed = self.create_playing_embed()
        view = MusicControls(self)
        await self.message.edit(embed=embed, view=view)
    
    async def update_idle(self):
        if not self.message:
            return
        
        embed = self.create_idle_embed()
        view = MusicControls(self)
        await self.message.edit(embed=embed, view=view)
    
    def create_playing_embed(self):
        song = self.now_playing
        embed = discord.Embed(
            title="🎶  Şimdi Çalıyor",
            description=f"**[{song.title}]({song.url})**",
            color=Colors.PLAYING,
            timestamp=datetime.now()
        )
        
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        
        if song.duration:
            mins, secs = divmod(song.duration, 60)
            embed.add_field(name="⏱️  Süre", value=f"`{int(mins)}:{int(secs):02d}`", inline=True)
        
        embed.add_field(name="👤  Yükleyen", value=f"`{song.uploader}`", inline=True)
        embed.add_field(name="🔊  Ses", value=f"`%{int(self.volume * 100)}`", inline=True)
        
        if song.views:
            embed.add_field(name="👀  Görüntülenme", value=f"`{song.views:,}`", inline=True)
        
        if self.queue:
            next_songs = "\n".join([f"`{i+1}.` {s.title[:50]}" for i, s in enumerate(self.queue[:5])])
            embed.add_field(name=f"📋  Sırada ({len(self.queue)} şarkı)", value=next_songs, inline=False)
        
        loop_emoji = "🔁" if self.loop_mode == 'track' else "🔂" if self.loop_mode == 'queue' else "➡️"
        embed.add_field(name="🔄  Döngü", value=loop_emoji, inline=True)
        
        embed.set_footer(text=f"Kross Müzik • {self.ctx.guild.name}", icon_url=self.ctx.guild.icon.url if self.ctx.guild.icon else None)
        
        return embed
    
    def create_idle_embed(self):
        embed = discord.Embed(
            title="🎵  Kross Müzik Bot",
            description="Şu anda müzik çalmıyor.\n`!oynat <şarkı>` ile başlatabilirsiniz!",
            color=Colors.PRIMARY,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Kross Müzik • {self.ctx.guild.name}")
        return embed
    
    def cleanup(self):
        self.queue.clear()
        self.history.clear()
        self.now_playing = None
        self.loop_mode = 'off'

# -------------------- MÜZİK KONTROL BUTONLARI --------------------
class MusicControls(View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.grey, custom_id="play_pause")
    async def play_pause(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Ses kanalında değilsin!", ephemeral=True)
        
        if self.player.ctx.voice_client.is_playing():
            self.player.ctx.voice_client.pause()
            self.player.paused = True
            await interaction.response.send_message("⏸️ Duraklatıldı", ephemeral=True)
        elif self.player.ctx.voice_client.is_paused():
            self.player.ctx.voice_client.resume()
            self.player.paused = False
            await interaction.response.send_message("▶️ Devam ediyor", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.grey, custom_id="skip")
    async def skip(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Ses kanalında değilsin!", ephemeral=True)
        
        if self.player.ctx.voice_client and self.player.ctx.voice_client.is_playing():
            self.player.ctx.voice_client.stop()
            await interaction.response.send_message("⏭️ Atlandı!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Müzik çalmıyor!", ephemeral=True)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.grey, custom_id="shuffle")
    async def shuffle(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Ses kanalında değilsin!", ephemeral=True)
        
        if len(self.player.queue) > 1:
            random.shuffle(self.player.queue)
            await interaction.response.send_message("🔀 Sıra karıştırıldı!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Yetersiz şarkı!", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.grey, custom_id="loop")
    async def loop(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Ses kanalında değilsin!", ephemeral=True)
        
        modes = ['off', 'track', 'queue']
        current = modes.index(self.player.loop_mode)
        self.player.loop_mode = modes[(current + 1) % 3]
        
        mode_names = {'off': '➡️ Kapalı', 'track': '🔂 Şarkı', 'queue': '🔁 Liste'}
        await interaction.response.send_message(f"🔄 Döngü: {mode_names[self.player.loop_mode]}", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.red, custom_id="stop")
    async def stop(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ Ses kanalında değilsin!", ephemeral=True)
        
        if self.player.ctx.voice_client:
            self.player.cleanup()
            self.player.ctx.voice_client.stop()
            await self.player.update_idle()
            await interaction.response.send_message("⏹️ Durduruldu!", ephemeral=True)

# -------------------- GLOBAL PLAYER YÖNETİMİ --------------------
players = {}

def get_player(ctx):
    guild_id = ctx.guild.id
    if guild_id not in players:
        players[guild_id] = MusicPlayer(ctx)
    return players[guild_id]

# -------------------- MÜZİK KOMUTLARI --------------------
@bot.command(name='oynat', aliases=['p', 'play'])
async def play(ctx, *, query: str):
    """🎵 Müzik çalar / sıraya ekler"""
    
    if not ctx.author.voice:
        embed = discord.Embed(
            title="❌ Hata",
            description="Önce bir ses kanalına katılmalısınız!",
            color=Colors.ERROR
        )
        return await ctx.send(embed=embed)
    
    player = get_player(ctx)
    
    # Ses kanalına bağlan
    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()
    elif ctx.voice_client.channel != ctx.author.voice.channel:
        await ctx.voice_client.move_to(ctx.author.voice.channel)
    
    # Şarkıyı ara ve ekle
    sources = await player.add_to_queue(query, ctx.author)
    
    if not sources:
        embed = discord.Embed(
            title="❌ Bulunamadı",
            description=f"`{query}` için sonuç bulunamadı!",
            color=Colors.ERROR
        )
        return await ctx.send(embed=embed)
    
    # İlk şarkı için
    if len(sources) == 1:
        song = sources[0]
        
        embed = discord.Embed(
            title="🎵  Sıraya Eklendi",
            description=f"**[{song.title}]({song.url})**",
            color=Colors.SUCCESS
        )
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        if song.duration:
            mins, secs = divmod(song.duration, 60)
            embed.add_field(name="⏱️  Süre", value=f"`{int(mins)}:{int(secs):02d}`", inline=True)
        embed.add_field(name="👤  Yükleyen", value=f"`{song.uploader}`", inline=True)
        embed.add_field(name="📋  Sıra No", value=f"`#{len(player.queue)}`", inline=True)
        
        await ctx.send(embed=embed)
    else:
        # Playlist
        embed = discord.Embed(
            title="📋  Oynatma Listesi Eklendi",
            description=f"**{len(sources)}** şarkı sıraya eklendi!",
            color=Colors.QUEUE
        )
        await ctx.send(embed=embed)
    
    # Çalmaya başla
    if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
        await player.play_next()
        
        # Player mesajını oluştur
        if player.message:
            await player.update_now_playing()
        else:
            await player.create_player_message()

@bot.command(name='atla', aliases=['skip', 's', 'gec'])
async def skip(ctx):
    """⏭️ Şarkıyı atlar"""
    
    player = get_player(ctx)
    
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        embed = discord.Embed(
            title="❌ Hata",
            description="Şu anda müzik çalmıyor!",
            color=Colors.ERROR
        )
        return await ctx.send(embed=embed)
    
    ctx.voice_client.stop()
    
    embed = discord.Embed(
        title="⏭️  Atlandı",
        description="Sonraki şarkıya geçiliyor...",
        color=Colors.WARNING
    )
    await ctx.send(embed=embed)

@bot.command(name='durdur', aliases=['pause'])
async def pause(ctx):
    """⏸️ Müziği duraklatır"""
    
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        embed = discord.Embed(title="❌ Hata", description="Müzik çalmıyor!", color=Colors.ERROR)
        return await ctx.send(embed=embed)
    
    ctx.voice_client.pause()
    
    embed = discord.Embed(
        title="⏸️  Duraklatıldı",
        description="`!devam` ile devam ettirebilirsiniz.",
        color=Colors.PAUSED
    )
    await ctx.send(embed=embed)

@bot.command(name='devam', aliases=['resume', 'devamet'])
async def resume(ctx):
    """▶️ Müziği devam ettirir"""
    
    if not ctx.voice_client or not ctx.voice_client.is_paused():
        embed = discord.Embed(title="❌ Hata", description="Müzik duraklatılmamış!", color=Colors.ERROR)
        return await ctx.send(embed=embed)
    
    ctx.voice_client.resume()
    
    embed = discord.Embed(
        title="▶️  Devam Ediyor",
        description="Müzik kaldığı yerden devam ediyor.",
        color=Colors.SUCCESS
    )
    await ctx.send(embed=embed)

@bot.command(name='ses', aliases=['volume', 'v'])
async def volume(ctx, volume: int = None):
    """🔊 Ses seviyesini ayarlar (0-100)"""
    
    player = get_player(ctx)
    
    if not ctx.voice_client:
        return await ctx.send("❌ Bağlı değilim!")
    
    if volume is None:
        embed = discord.Embed(
            title="🔊  Ses Seviyesi",
            description=f"Şu anki ses: **%{int(player.volume * 100)}**",
            color=Colors.INFO
        )
        return await ctx.send(embed=embed)
    
    if not 0 <= volume <= 100:
        return await ctx.send("❌ Ses 0-100 arası olmalı!")
    
    player.volume = volume / 100
    if ctx.voice_client.source:
        ctx.voice_client.source.volume = player.volume
    
    embed = discord.Embed(
        title="🔊  Ses Ayarlandı",
        description=f"Ses seviyesi: **%{volume}**",
        color=Colors.SUCCESS
    )
    await ctx.send(embed=embed)

@bot.command(name='kuyruk', aliases=['queue', 'q', 'sira'])
async def show_queue(ctx, page: int = 1):
    """📋 Şarkı sırasını gösterir"""
    
    player = get_player(ctx)
    
    if not player.queue and not player.now_playing:
        embed = discord.Embed(
            title="📋  Sıra Boş",
            description="`!oynat <şarkı>` ile şarkı ekleyebilirsiniz!",
            color=Colors.INFO
        )
        return await ctx.send(embed=embed)
    
    items_per_page = 10
    total_pages = max(1, (len(player.queue) + items_per_page - 1) // items_per_page)
    page = min(page, total_pages)
    
    embed = discord.Embed(
        title="📋  Şarkı Sırası",
        color=Colors.QUEUE,
        timestamp=datetime.now()
    )
    
    if player.now_playing:
        song = player.now_playing
        embed.add_field(
            name="🎶  Şimdi Çalıyor",
            value=f"**[{song.title}]({song.url})** `[{song.uploader}]`",
            inline=False
        )
    
    start = (page - 1) * items_per_page
    end = start + items_per_page
    
    for i, song in enumerate(player.queue[start:end], start + 1):
        duration = ""
        if song.duration:
            mins, secs = divmod(song.duration, 60)
            duration = f"`[{int(mins)}:{int(secs):02d}]`"
        embed.add_field(
            name=f"#{i}  {song.title[:50]}",
            value=f"👤 `{song.uploader}` {duration}",
            inline=False
        )
    
    embed.set_footer(text=f"Toplam: {len(player.queue)} şarkı • Sayfa {page}/{total_pages}")
    await ctx.send(embed=embed)

@bot.command(name='karistir', aliases=['shuffle', 'kar'])
async def shuffle(ctx):
    """🔀 Sırayı karıştırır"""
    
    player = get_player(ctx)
    
    if len(player.queue) < 2:
        return await ctx.send("❌ En az 2 şarkı gerek!")
    
    random.shuffle(player.queue)
    
    embed = discord.Embed(
        title="🔀  Sıra Karıştırıldı",
        description=f"**{len(player.queue)}** şarkı karıştırıldı!",
        color=Colors.QUEUE
    )
    await ctx.send(embed=embed)

@bot.command(name='dongu', aliases=['loop', 'l'])
async def loop(ctx, mode: str = None):
    """🔄 Döngü modunu ayarlar: off/track/queue"""
    
    player = get_player(ctx)
    
    if mode is None:
        modes = ['off', 'track', 'queue']
        current = modes.index(player.loop_mode)
        player.loop_mode = modes[(current + 1) % 3]
    elif mode.lower() in ['off', 'kapat', 'kapali']:
        player.loop_mode = 'off'
    elif mode.lower() in ['track', 'sarki', 'tek']:
        player.loop_mode = 'track'
    elif mode.lower() in ['queue', 'liste', 'tum']:
        player.loop_mode = 'queue'
    else:
        return await ctx.send("❌ Geçersiz mod! `off`, `track` veya `queue`")
    
    mode_names = {'off': '➡️ Kapalı', 'track': '🔂 Tek Şarkı', 'queue': '🔁 Tüm Liste'}
    
    embed = discord.Embed(
        title="🔄  Döngü Modu",
        description=f"**{mode_names[player.loop_mode]}**",
        color=Colors.INFO
    )
    await ctx.send(embed=embed)

@bot.command(name='durdurve', aliases=['stop', 'temizle'])
async def stop(ctx):
    """⏹️ Müziği durdurur ve sırayı temizler"""
    
    player = get_player(ctx)
    
    if ctx.voice_client:
        player.cleanup()
        ctx.voice_client.stop()
    
    embed = discord.Embed(
        title="⏹️  Durduruldu",
        description="Müzik durdu ve sıra temizlendi.",
        color=Colors.ERROR
    )
    await ctx.send(embed=embed)

@bot.command(name='np', aliases=['now', 'calan'])
async def now_playing(ctx):
    """🎶 Şu an çalan şarkıyı gösterir"""
    
    player = get_player(ctx)
    
    if not player.now_playing:
        return await ctx.send("❌ Şu anda müzik çalmıyor!")
    
    song = player.now_playing
    
    embed = discord.Embed(
        title="🎶  Şimdi Çalıyor",
        description=f"**[{song.title}]({song.url})**",
        color=Colors.PLAYING,
        timestamp=datetime.now()
    )
    
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    
    if song.duration:
        mins, secs = divmod(song.duration, 60)
        total = f"{int(mins)}:{int(secs):02d}"
        embed.add_field(name="⏱️  Süre", value=f"`{total}`", inline=True)
    
    embed.add_field(name="👤  Yükleyen", value=f"`{song.uploader}`", inline=True)
    embed.add_field(name="🔊  Ses", value=f"`%{int(player.volume * 100)}`", inline=True)
    
    if song.views:
        embed.add_field(name="👀  Görüntülenme", value=f"`{song.views:,}`", inline=True)
    if song.likes:
        embed.add_field(name="👍  Beğeni", value=f"`{song.likes:,}`", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='gir')
async def join(ctx):
    """🔊 Ses kanalına katılır"""
    
    if not ctx.author.voice:
        return await ctx.send("❌ Önce ses kanalına katıl!")
    
    channel = ctx.author.voice.channel
    
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    
    embed = discord.Embed(
        title="🔊  Bağlanıldı",
        description=f"**{channel.name}** kanalına katıldım!",
        color=Colors.SUCCESS
    )
    await ctx.send(embed=embed)

@bot.command(name='cik', aliases=['leave', 'ayril'])
async def leave(ctx):
    """👋 Ses kanalından ayrılır"""
    
    player = get_player(ctx)
    
    if ctx.voice_client:
        player.cleanup()
        await ctx.voice_client.disconnect()
    
    embed = discord.Embed(
        title="👋  Ayrıldım",
        description="Görüşürüz!",
        color=Colors.WARNING
    )
    await ctx.send(embed=embed)

@bot.command(name='yardim', aliases=['help', 'h', 'komutlar'])
async def help_command(ctx):
    """📋 Tüm komutları gösterir"""
    
    embed = discord.Embed(
        title="🎵  KROSS MÜZİK BOT",
        description="Profesyonel Discord Müzik Botu",
        color=Colors.PRIMARY,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="🎤  **Temel Komutlar**",
        value="```!gir - Ses kanalına katıl\n!cik - Ses kanalından ayrıl```",
        inline=False
    )
    
    embed.add_field(
        name="🎵  **Müzik Çalma**",
        value="```!oynat <şarkı/link> - Müzik çal\n!oynat <link> - YouTube linki\n!atla - Sonraki şarkı\n!durdur - Duraklat\n!devam - Devam et```",
        inline=False
    )
    
    embed.add_field(
        name="📋  **Sıra Yönetimi**",
        value="```!kuyruk - Sırayı gör\n!karistir - Sırayı karıştır\n!dongu <off/track/queue> - Döngü\n!durdurve - Tamamen durdur```",
        inline=False
    )
    
    embed.add_field(
        name="⚙️  **Ayarlar**",
        value="```!ses <0-100> - Ses seviyesi\n!np - Çalan şarkı bilgisi\n!yardim - Bu menü```",
        inline=False
    )
    
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="Kross Müzik Bot © 2026 • Prefix: !")
    
    await ctx.send(embed=embed)

# -------------------- OTOMATİK ÇIKIŞ --------------------
@bot.event
async def on_voice_state_update(member, before, after):
    """Bot yalnız kalınca 5 dk sonra çıkar"""
    
    if member.id == bot.user.id:
        return
    
    for guild in bot.guilds:
        voice_client = guild.voice_client
        if voice_client and voice_client.channel:
            # Bot ve diğer üyeleri say
            humans = len([m for m in voice_client.channel.members if not m.bot])
            
            if humans == 0:
                guild_id = guild.id
                if guild_id in players:
                    await asyncio.sleep(300)  # 5 dakika bekle
                    voice_client = guild.voice_client
                    if voice_client and voice_client.channel:
                        humans = len([m for m in voice_client.channel.members if not m.bot])
                        if humans == 0:
                            players[guild_id].cleanup()
                            await voice_client.disconnect()

# -------------------- HATA YÖNETİMİ --------------------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    
    embed = discord.Embed(
        title="❌ Hata",
        description=str(error)[:200],
        color=Colors.ERROR
    )
    embed.set_footer(text="Yardım için: !yardim")
    
    await ctx.send(embed=embed)

# -------------------- BOT HAZIR --------------------
@bot.event
async def on_ready():
    print(f"🎵 {bot.user} olarak giriş yapıldı!")
    print(f"📊 {len(bot.guilds)} sunucuda aktif")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!yardim | Müzik"
        ),
        status=discord.Status.online
    )
    
    for guild in bot.guilds:
        print(f"   • {guild.name}")

# -------------------- BAŞLAT --------------------
if __name__ == "__main__":
    Thread(target=run_flask).start()
    
    print("🎵 Kross Müzik Bot başlatılıyor...")
    print("═" * 40)
    
    TOKEN = os.environ.get('DISCORD_TOKEN')
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ DISCORD_TOKEN bulunamadı!")
