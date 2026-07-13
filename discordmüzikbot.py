import discord
from discord.ext import commands
import asyncio
import yt_dlp
import os
import random
from flask import Flask
from threading import Thread

# Flask (Render için)
app = Flask(__name__)

@app.route('/')
def home():
    return "Kross Music Bot - Aktif"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

ytdl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'extract_flat': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'source_address': '0.0.0.0',
}

ffmpeg_opts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_opts)
queues = {}

class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.loop = 'off'
        self.volume = 0.5

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = MusicQueue()
    return queues[guild_id]

async def play_next(ctx):
    if not ctx.voice_client or not ctx.voice_client.channel:
        return
    
    q = get_queue(ctx.guild.id)
    
    if q.loop == 'one' and q.current:
        q.queue.insert(0, q.current)
    
    if q.queue:
        if q.loop == 'all' and q.current:
            q.queue.append(q.current)
        
        q.current = q.queue.pop(0)
        
        def after_play(error):
            if error:
                print(f"Hata: {error}")
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        
        try:
            ctx.voice_client.play(
                discord.FFmpegPCMAudio(q.current['url'], **ffmpeg_opts),
                after=after_play
            )
            ctx.voice_client.source = discord.PCMVolumeTransformer(ctx.voice_client.source, q.volume)
            
            embed = discord.Embed(
                title="🎶 Şimdi Çalıyor",
                description=f"**[{q.current['title']}]({q.current['webpage_url']})**",
                color=0x1DB954
            )
            if q.current.get('duration'):
                m, s = divmod(q.current['duration'], 60)
                embed.add_field(name="⏱️ Süre", value=f"{int(m)}:{int(s):02d}", inline=True)
            embed.add_field(name="👤 İsteyen", value=q.current['requester'].mention, inline=True)
            if q.current.get('thumbnail'):
                embed.set_thumbnail(url=q.current['thumbnail'])
            
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"Oynatma hatası: {e}")
            await play_next(ctx)
    else:
        q.current = None

@bot.command(name='gir')
async def join(ctx):
    if not ctx.author.voice:
        return await ctx.send("❌ Ses kanalında değilsin!")
    
    channel = ctx.author.voice.channel
    
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    
    await ctx.send(f"🔊 **{channel.name}** kanalına katıldım!")

@bot.command(name='cik')
async def leave(ctx):
    if ctx.voice_client:
        q = get_queue(ctx.guild.id)
        q.queue.clear()
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Görüşürüz!")
    else:
        await ctx.send("❌ Zaten kanalda değilim!")

@bot.command(name='oynat', aliases=['p', 'play'])
async def play(ctx, *, query):
    if not ctx.author.voice:
        return await ctx.send("❌ Ses kanalında değilsin!")
    
    channel = ctx.author.voice.channel
    
    if not ctx.voice_client:
        await channel.connect()
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)
    
    query = query.split('?si=')[0].split('&si=')[0]
    
    msg = await ctx.send("🔍 **Aranıyor...**")
    
    try:
        loop = asyncio.get_event_loop()
        
        if not query.startswith('http'):
            search_query = f"ytsearch:{query}"
        else:
            search_query = query
        
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))
        
        if data is None:
            return await msg.edit(content="❌ **Sonuç bulunamadı!**")
        
        entries = []
        if 'entries' in data and len(data['entries']) > 0:
            entries = data['entries']
        elif 'url' in data:
            entries = [data]
        else:
            return await msg.edit(content="❌ **Sonuç bulunamadı!**")
        
        q = get_queue(ctx.guild.id)
        
        if len(entries) > 1:
            count = 0
            for entry in entries:
                if entry and entry.get('url'):
                    entry['requester'] = ctx.author
                    q.queue.append(entry)
                    count += 1
            await msg.edit(content=f"✅ **{count}** şarkı sıraya eklendi!")
        else:
            entry = entries[0]
            
            if not entry or not entry.get('url'):
                return await msg.edit(content="❌ **Geçersiz şarkı!**")
            
            entry['requester'] = ctx.author
            q.queue.append(entry)
            
            embed = discord.Embed(
                title="🎵 Sıraya Eklendi",
                description=f"**[{entry.get('title', 'Bilinmeyen')}]({entry.get('webpage_url', '')})**",
                color=0x57F287
            )
            if entry.get('duration'):
                m, s = divmod(entry['duration'], 60)
                embed.add_field(name="⏱️ Süre", value=f"{int(m)}:{int(s):02d}", inline=True)
            embed.add_field(name="📋 Sıra", value=f"#{len(q.queue)}", inline=True)
            if entry.get('thumbnail'):
                embed.set_thumbnail(url=entry['thumbnail'])
            
            await msg.edit(content=None, embed=embed)
        
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await play_next(ctx)
            
    except Exception as e:
        print(f"Play hatası: {e}")
        await msg.edit(content=f"❌ **Hata:** {str(e)[:100]}")

@bot.command(name='atla', aliases=['skip', 's'])
async def skip(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        return await ctx.send("❌ Müzik çalmıyor!")
    
    ctx.voice_client.stop()
    await ctx.send("⏭️ **Atlandı!**")

@bot.command(name='durdur', aliases=['pause'])
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ **Durduruldu!**")
    else:
        await ctx.send("❌ Müzik çalmıyor!")

@bot.command(name='devam', aliases=['resume'])
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ **Devam ediyor!**")
    else:
        await ctx.send("❌ Duraklatılmamış!")

@bot.command(name='ses', aliases=['volume', 'v'])
async def volume(ctx, volume: int = None):
    q = get_queue(ctx.guild.id)
    
    if volume is None:
        return await ctx.send(f"🔊 Ses: **%{int(q.volume * 100)}**")
    
    if 0 <= volume <= 200:
        q.volume = volume / 100
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = q.volume
        await ctx.send(f"🔊 Ses: **%{volume}**")
    else:
        await ctx.send("❌ 0-200 arası olmalı!")

@bot.command(name='sira', aliases=['queue', 'q'])
async def show_queue(ctx):
    q = get_queue(ctx.guild.id)
    
    if not q.current and not q.queue:
        return await ctx.send("📋 Sıra boş!")
    
    embed = discord.Embed(title="📋 Şarkı Sırası", color=0x9B59B6)
    
    if q.current:
        embed.add_field(
            name="🎶 Çalıyor",
            value=f"**[{q.current['title']}]({q.current['webpage_url']})**",
            inline=False
        )
    
    for i, song in enumerate(q.queue[:10], 1):
        embed.add_field(
            name=f"#{i}",
            value=f"**[{song['title']}]({song['webpage_url']})**",
            inline=False
        )
    
    if len(q.queue) > 10:
        embed.set_footer(text=f"Ve {len(q.queue) - 10} şarkı daha...")
    
    await ctx.send(embed=embed)

@bot.command(name='dongu', aliases=['loop'])
async def loop(ctx, mode: str = None):
    q = get_queue(ctx.guild.id)
    
    if mode is None:
        modes = ['off', 'one', 'all']
        current = modes.index(q.loop)
        q.loop = modes[(current + 1) % 3]
    elif mode.lower() in ['off', 'kapat']:
        q.loop = 'off'
    elif mode.lower() in ['one', 'tek', '1']:
        q.loop = 'one'
    elif mode.lower() in ['all', 'tum', 'hepsi']:
        q.loop = 'all'
    else:
        return await ctx.send("❌ `off`, `one` veya `all`")
    
    names = {'off': '➡️ Kapalı', 'one': '🔂 Tek Şarkı', 'all': '🔁 Tüm Liste'}
    await ctx.send(f"🔄 **{names[q.loop]}**")

@bot.command(name='karistir', aliases=['shuffle'])
async def shuffle(ctx):
    q = get_queue(ctx.guild.id)
    if len(q.queue) > 1:
        random.shuffle(q.queue)
        await ctx.send("🔀 **Karıştırıldı!**")
    else:
        await ctx.send("❌ En az 2 şarkı gerek!")

@bot.command(name='stop')
async def stop(ctx):
    if ctx.voice_client:
        q = get_queue(ctx.guild.id)
        q.queue.clear()
        q.loop = 'off'
        ctx.voice_client.stop()
        await ctx.send("⏹️ **Durduruldu, sıra temizlendi!**")

@bot.command(name='np', aliases=['now', 'calan'])
async def now_playing_cmd(ctx):
    q = get_queue(ctx.guild.id)
    if not q.current:
        return await ctx.send("❌ Şu anda müzik çalmıyor!")
    
    song = q.current
    embed = discord.Embed(
        title="🎶 Şimdi Çalıyor",
        description=f"**[{song['title']}]({song['webpage_url']})**",
        color=0x1DB954
    )
    if song.get('duration'):
        m, s = divmod(song['duration'], 60)
        embed.add_field(name="⏱️ Süre", value=f"{int(m)}:{int(s):02d}", inline=True)
    embed.add_field(name="👤 İsteyen", value=song['requester'].mention, inline=True)
    embed.add_field(name="🔊 Ses", value=f"%{int(q.volume * 100)}", inline=True)
    if song.get('thumbnail'):
        embed.set_thumbnail(url=song['thumbnail'])
    
    await ctx.send(embed=embed)

@bot.command(name='yardim', aliases=['h', 'komutlar'])
async def help_cmd(ctx):
    embed = discord.Embed(title="🎵 KROSS MÜZİK BOT", color=0x5865F2)
    embed.add_field(name="🎤 Temel", value="`!gir` `!cik`", inline=False)
    embed.add_field(name="🎵 Müzik", value="`!oynat <şarkı/link>` `!atla` `!durdur` `!devam`", inline=False)
    embed.add_field(name="📋 Sıra", value="`!sira` `!karistir` `!dongu <off/one/all>` `!stop`", inline=False)
    embed.add_field(name="⚙️ Diğer", value="`!ses <0-200>` `!np` `!yardim`", inline=False)
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f"Hata: {error}")

@bot.event
async def on_ready():
    print(f"🎵 {bot.user} aktif!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="!yardim | !oynat"))

# Başlat
if __name__ == "__main__":
    Thread(target=run_flask).start()
    print("🎵 Kross Müzik Bot başlatılıyor...")
    TOKEN = os.environ.get('DISCORD_TOKEN')
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ Token bulunamadı!")
