import discord
from discord.ext import commands, tasks
from discord.utils import get
import asyncio
from datetime import datetime, timedelta
import random
import json
import os
from flask import Flask
from threading import Thread

# Flask (Render için)
app = Flask(__name__)

@app.route('/')
def home():
    return "Kross Guard Bot - Aktif"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='.', intents=intents, help_command=None)

# -------------------- AYARLAR --------------------
MOD_LOG_KANALI = "mod-log"
MUTE_ROLU = "Muted"
UYARI_LIMIT = 3
OTOROL = "Üye"
REKLAM_KELIMELER = ["discord.gg", "https://", "http://", ".com", ".net", ".xyz"]
KUFUR_KELIMELER = ["amk", "sg", "oç", "orospu", "yarrak", "siktir", "piç", "gavat", "ananı", "sülaleni"]
SPAM_LIMIT = 5
SPAM_MESAJ = 3

# Anti-Phishing kelimeleri
PHISHING_KELIMELER = [
    "free nitro", "free steam", "discord nitro free", "claim nitro",
    "discord gift", "discord free", "steam gift", "free discord",
    "nitro giveaway", "steam giveaway", "click here nitro",
    "discord.com/gifts", "discordnitro", "nitro-free", "nitrofree"
]

VERI_DOSYASI = "guard_verileri.json"

# -------------------- VERİ --------------------
def veri_yukle():
    if os.path.exists(VERI_DOSYASI):
        with open(VERI_DOSYASI, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "uyarilar": {}, "mute_kayit": {}, "welcome": {}, "leave": {},
        "reklam_kayit": {}, "kufur_kayit": {}, "dm_log": [],
        "cekilisler": [], "gecici_banlar": [], "notlar": {}
    }

def veri_kaydet(veri):
    with open(VERI_DOSYASI, 'w', encoding='utf-8') as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)

# -------------------- HAZIR --------------------
@bot.event
async def on_ready():
    print(f"🛡️ {bot.user} aktif!")
    print(f"📊 {len(bot.guilds)} sunucuda görevde")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="sunucuyu | .yardim"
        ),
        status=discord.Status.online
    )
    
    for guild in bot.guilds:
        print(f"   • {guild.name} - {guild.member_count} üye")
    
    mute_kontrol.start()
    durum_guncelle.start()
    gecici_ban_kontrol.start()

@tasks.loop(seconds=30)
async def durum_guncelle():
    durumlar = [
        f"{sum(g.member_count for g in bot.guilds)} üye | .yardim",
        ".yardim yazarak komutları gör",
        "🛡️ Sunucunuzu koruyorum",
        f"{len(bot.guilds)} sunucu",
        "Reklam engelleme aktif",
        "Anti-Phishing aktif"
    ]
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=random.choice(durumlar)))

@tasks.loop(seconds=60)
async def mute_kontrol():
    veri = veri_yukle()
    simdi = datetime.now()
    for uid, bilgi in list(veri["mute_kayit"].items()):
        baslangic = datetime.fromisoformat(bilgi["baslangic"])
        sure = bilgi["sure"]
        if (simdi - baslangic).total_seconds() >= sure * 60:
            for guild in bot.guilds:
                member = guild.get_member(int(uid))
                mute_rolu = get(guild.roles, name=MUTE_ROLU)
                if member and mute_rolu and mute_rolu in member.roles:
                    try:
                        await member.remove_roles(mute_rolu)
                        del veri["mute_kayit"][uid]
                        veri_kaydet(veri)
                    except: pass

@tasks.loop(seconds=60)
async def gecici_ban_kontrol():
    veri = veri_yukle()
    simdi = datetime.now()
    for ban in list(veri["gecici_banlar"]):
        bitis = datetime.fromisoformat(ban["bitis"])
        if simdi >= bitis:
            for guild in bot.guilds:
                try:
                    user = await bot.fetch_user(int(ban["kullanici_id"]))
                    await guild.unban(user)
                    veri["gecici_banlar"].remove(ban)
                    veri_kaydet(veri)
                    
                    log_kanal = get(guild.text_channels, name=MOD_LOG_KANALI)
                    if log_kanal:
                        await log_kanal.send(f"✅ {user.mention} geçici banı sona erdi!")
                except: pass

# -------------------- HOŞ GELDİN --------------------
@bot.event
async def on_member_join(member):
    otorol = get(member.guild.roles, name=OTOROL)
    if otorol:
        try: await member.add_roles(otorol)
        except: pass
    
    try:
        embed = discord.Embed(
            title=f"🌟 {member.guild.name} Sunucusuna Hoş Geldin!",
            description=f"**{member.mention}**, aramıza katıldığın için çok mutluyuz!",
            color=0x00FF00, timestamp=datetime.now()
        )
        embed.add_field(name="📜 Kurallar", value="Lütfen kurallar kanalını oku.", inline=False)
        embed.add_field(name="👥 Üye Sayımız", value=f"**{member.guild.member_count}** oldu!", inline=True)
        embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else None)
        embed.set_footer(text="Kross Guard • Hoş Geldin Sistemi")
        await member.send(embed=embed)
    except: pass
    
    veri = veri_yukle()
    welcome_data = veri["welcome"].get(str(member.guild.id), {})
    if welcome_data.get("aktif"):
        kanal = member.guild.get_channel(int(welcome_data.get("kanal")))
        if kanal:
            mesaj = welcome_data.get("mesaj", "{kullanici} sunucuya katıldı!")
            mesaj = mesaj.replace("{kullanici}", member.mention)
            mesaj = mesaj.replace("{kullanici_adi}", member.name)
            mesaj = mesaj.replace("{sunucu}", member.guild.name)
            mesaj = mesaj.replace("{uye_sayisi}", str(member.guild.member_count))
            
            embed = discord.Embed(title="🌟 Hoş Geldin!", description=mesaj, color=0x00FF00, timestamp=datetime.now())
            embed.add_field(name="👤 Kullanıcı", value=member.mention, inline=True)
            embed.add_field(name="📅 Katılım", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
            embed.add_field(name="👥 Üye", value=str(member.guild.member_count), inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Kross Guard Bot • Hoş Geldin")
            await kanal.send(embed=embed)

# -------------------- ANTI-SPAM / ANTI-REKLAM / ANTI-PHISHING --------------------
spam_cache = {}

@bot.event
async def on_message(message):
    if message.author.bot: return
    
    # Anti-Spam
    author_id = message.author.id
    simdi = datetime.now()
    
    if author_id not in spam_cache:
        spam_cache[author_id] = []
    
    spam_cache[author_id].append(simdi)
    spam_cache[author_id] = [t for t in spam_cache[author_id] if (simdi - t).total_seconds() < SPAM_LIMIT]
    
    if len(spam_cache[author_id]) > SPAM_MESAJ:
        if not message.author.guild_permissions.administrator:
            await message.channel.purge(limit=len(spam_cache[author_id]))
            
            mute_rolu = get(message.guild.roles, name=MUTE_ROLU)
            if mute_rolu:
                try:
                    await message.author.add_roles(mute_rolu, reason="Spam")
                    await message.channel.send(f"🚫 {message.author.mention} spam yaptığı için **5 dakika** susturuldu!", delete_after=5)
                    
                    veri = veri_yukle()
                    veri["mute_kayit"][str(message.author.id)] = {"sure": 5, "baslangic": simdi.isoformat(), "yetkili": "Anti-Spam"}
                    veri_kaydet(veri)
                except: pass
            
            spam_cache[author_id] = []
            await bot.process_commands(message)
            return
    
    # Anti-Phishing
    mesaj_lower = message.content.lower()
    for kelime in PHISHING_KELIMELER:
        if kelime in mesaj_lower:
            await message.delete()
            
            try:
                await message.author.timeout(timedelta(minutes=10), reason="Anti-Phishing: Şüpheli link")
            except: pass
            
            await message.channel.send(f"🚨 {message.author.mention} **şüpheli link/iftira tespit edildi!** 10 dakika timeout.", delete_after=10)
            
            await log_gonder(message.guild, discord.Embed(
                title="🚨 ANTI-PHISHING",
                description=f"{message.author.mention} şüpheli mesaj gönderdi!",
                color=0xFF0000, timestamp=datetime.now()
            ).add_field(name="📝 Mesaj", value=message.content[:200]))
            
            await bot.process_commands(message)
            return
    
    # Anti-Reklam
    for kelime in REKLAM_KELIMELER:
        if kelime in mesaj_lower:
            if message.author.guild_permissions.administrator: break
            
            await message.delete()
            veri = veri_yukle()
            uid = str(message.author.id)
            if uid not in veri["reklam_kayit"]: veri["reklam_kayit"][uid] = 0
            veri["reklam_kayit"][uid] += 1
            veri_kaydet(veri)
            
            await message.channel.send(f"🚫 {message.author.mention} **Reklam yasak!**", delete_after=5)
            await log_gonder(message.guild, discord.Embed(title="🚫 REKLAM", description=f"{message.author.mention} reklam yaptı!", color=0xFF0000).add_field(name="Mesaj", value=message.content[:100]))
            break
    
    # Anti-Küfür
    for kelime in KUFUR_KELIMELER:
        if kelime in message.content.lower().split():
            if message.author.guild_permissions.administrator: break
            
            await message.delete()
            veri = veri_yukle()
            uid = str(message.author.id)
            if uid not in veri["kufur_kayit"]: veri["kufur_kayit"][uid] = 0
            veri["kufur_kayit"][uid] += 1
            veri_kaydet(veri)
            
            await message.channel.send(f"⚠️ {message.author.mention} **Küfür etme!**", delete_after=5)
            break
    
    await bot.process_commands(message)

# -------------------- BAN / UNBAN / KICK / TEMPBAN --------------------
@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi"):
    if member == ctx.author: return await ctx.send("❌ Kendini banlayamazsın!")
    if member.top_role >= ctx.author.top_role: return await ctx.send("❌ Yetkin yetmez!")
    
    try:
        try: await member.send(embed=discord.Embed(title=f"🔨 {ctx.guild.name} Banlandınız!", description=f"Sebep: {reason}", color=0xFF0000).add_field(name="Yetkili", value=ctx.author.name))
        except: pass
        
        await member.ban(reason=reason, delete_message_days=1)
        
        embed = discord.Embed(title="🔨 BANLANDI", description=f"**{member.name}** yasaklandı!", color=0xFF0000, timestamp=datetime.now())
        embed.add_field(name="👤 Kişi", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.add_field(name="📝 Sebep", value=reason, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Kross Guard • Ban")
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, embed)
    except: await ctx.send("❌ Yetkim yok!")

@bot.command(name='tempban')
@commands.has_permissions(ban_members=True)
async def tempban(ctx, member: discord.Member, sure: int, *, reason: str = "Sebep belirtilmedi"):
    """Geçici ban: .tempban @kişi 7 Sebep (gün olarak)"""
    if member == ctx.author: return await ctx.send("❌ Kendini banlayamazsın!")
    if member.top_role >= ctx.author.top_role: return await ctx.send("❌ Yetkin yetmez!")
    
    try:
        try: await member.send(embed=discord.Embed(title=f"⏰ {ctx.guild.name} Geçici Ban!", description=f"Süre: **{sure} gün**\nSebep: {reason}", color=0xFFA500).add_field(name="Yetkili", value=ctx.author.name))
        except: pass
        
        await member.ban(reason=f"Geçici Ban ({sure} gün): {reason}", delete_message_days=1)
        
        veri = veri_yukle()
        veri["gecici_banlar"].append({
            "kullanici_id": member.id,
            "bitis": (datetime.now() + timedelta(days=sure)).isoformat(),
            "sebep": reason,
            "yetkili": ctx.author.name
        })
        veri_kaydet(veri)
        
        embed = discord.Embed(title="⏰ GEÇİCİ BAN", description=f"**{member.name}** {sure} gün banlandı!", color=0xFFA500, timestamp=datetime.now())
        embed.add_field(name="👤 Kişi", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.add_field(name="⏱️ Süre", value=f"{sure} gün", inline=True)
        embed.add_field(name="📝 Sebep", value=reason, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Kross Guard • Geçici Ban")
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, embed)
    except: await ctx.send("❌ Yetkim yok!")

@bot.command(name='unban')
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await ctx.guild.unban(user)
        embed = discord.Embed(title="✅ BAN AÇILDI", description=f"**{user.name}**", color=0x00FF00, timestamp=datetime.now())
        embed.add_field(name="👤 Kişi", value=f"{user.mention} ({user.id})", inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.set_footer(text="Kross Guard • Unban")
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, embed)
    except: await ctx.send("❌ Kullanıcı bulunamadı!")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi"):
    if member == ctx.author: return await ctx.send("❌ Kendini atamazsın!")
    if member.top_role >= ctx.author.top_role: return await ctx.send("❌ Yetkin yetmez!")
    
    try:
        try: await member.send(f"👢 **{ctx.guild.name}** sunucusundan atıldın!\n📝 {reason}")
        except: pass
        
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 ATILDI", description=f"**{member.name}** atıldı!", color=0xFFA500, timestamp=datetime.now())
        embed.add_field(name="👤 Kişi", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.add_field(name="📝 Sebep", value=reason, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Kross Guard • Kick")
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, embed)
    except: await ctx.send("❌ Yetkim yok!")

# -------------------- MUTE / UNMUTE / VOICEMUTE --------------------
@bot.command(name='mute')
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, sure: int = 10, *, reason: str = "Sebep belirtilmedi"):
    if member == ctx.author: return await ctx.send("❌ Kendini susturamazsın!")
    if member.top_role >= ctx.author.top_role: return await ctx.send("❌ Yetkin yetmez!")
    
    mute_rolu = get(ctx.guild.roles, name=MUTE_ROLU)
    if not mute_rolu:
        try:
            mute_rolu = await ctx.guild.create_role(name=MUTE_ROLU, color=0x808080)
            for channel in ctx.guild.channels:
                await channel.set_permissions(mute_rolu, send_messages=False, speak=False, add_reactions=False)
        except: return await ctx.send("❌ Mute rolü oluşturulamadı!")
    
    try:
        await member.add_roles(mute_rolu, reason=reason)
        try: await member.send(f"🔇 **{ctx.guild.name}** {sure} dk susturuldun!\n📝 {reason}")
        except: pass
        
        embed = discord.Embed(title="🔇 SUSTURULDU", description=f"**{member.name}**", color=0x808080, timestamp=datetime.now())
        embed.add_field(name="👤 Kişi", value=member.mention, inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.add_field(name="⏱️ Süre", value=f"{sure} dk", inline=True)
        embed.add_field(name="📝 Sebep", value=reason, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Kross Guard • Mute")
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, embed)
        
        veri = veri_yukle()
        veri["mute_kayit"][str(member.id)] = {"sure": sure, "baslangic": datetime.now().isoformat(), "yetkili": ctx.author.name}
        veri_kaydet(veri)
    except: await ctx.send("❌ Yetkim yok!")

@bot.command(name='voicemute')
@commands.has_permissions(manage_roles=True)
async def voicemute(ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi"):
    """Ses kanalında susturur"""
    if member == ctx.author: return await ctx.send("❌ Kendini susturamazsın!")
    if not member.voice: return await ctx.send("❌ Kullanıcı ses kanalında değil!")
    
    try:
        await member.edit(mute=True, reason=reason)
        embed = discord.Embed(title="🎤 SES MUTE", description=f"**{member.name}** ses kanalında susturuldu!", color=0x808080, timestamp=datetime.now())
        embed.add_field(name="👤 Kişi", value=member.mention, inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.add_field(name="📝 Sebep", value=reason, inline=True)
        embed.set_footer(text="Kross Guard • Voice Mute")
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, embed)
    except: await ctx.send("❌ Yetkim yok!")

@bot.command(name='voiceunmute')
@commands.has_permissions(manage_roles=True)
async def voiceunmute(ctx, member: discord.Member):
    if not member.voice: return await ctx.send("❌ Kullanıcı ses kanalında değil!")
    
    try:
        await member.edit(mute=False)
        await ctx.send(f"🎤 {member.mention} ses mute kaldırıldı!")
    except: await ctx.send("❌ Yetkim yok!")

@bot.command(name='unmute')
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    mute_rolu = get(ctx.guild.roles, name=MUTE_ROLU)
    if not mute_rolu or mute_rolu not in member.roles: return await ctx.send("❌ Susturulmamış!")
    
    await member.remove_roles(mute_rolu)
    embed = discord.Embed(title="🔊 SUSTURMA AÇILDI", description=f"**{member.name}**", color=0x00FF00, timestamp=datetime.now())
    embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
    embed.set_footer(text="Kross Guard • Unmute")
    await ctx.send(embed=embed)
    await log_gonder(ctx.guild, embed)

# -------------------- UYARI SİSTEMİ --------------------
@bot.command(name='uyari')
@commands.has_permissions(manage_messages=True)
async def uyari(ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi"):
    if member == ctx.author: return await ctx.send("❌ Kendine uyarı veremezsin!")
    
    veri = veri_yukle()
    uid = str(member.id)
    if uid not in veri["uyarilar"]: veri["uyarilar"][uid] = {"isim": member.name, "sayi": 0, "sebepler": []}
    
    veri["uyarilar"][uid]["sayi"] += 1
    veri["uyarilar"][uid]["sebepler"].append({"sebep": reason, "yetkili": ctx.author.name, "tarih": datetime.now().isoformat()})
    veri_kaydet(veri)
    
    uyari_sayisi = veri["uyarilar"][uid]["sayi"]
    
    embed = discord.Embed(title="⚠️ UYARI VERİLDİ", description=f"**{member.name}** uyarı aldı!", color=0xFFFF00, timestamp=datetime.now())
    embed.add_field(name="👤 Kişi", value=member.mention, inline=False)
    embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
    embed.add_field(name="⚠️ Uyarı", value=f"**{uyari_sayisi}/{UYARI_LIMIT}**", inline=True)
    embed.add_field(name="📝 Sebep", value=reason, inline=False)
    embed.set_footer(text="Kross Guard • Uyarı")
    await ctx.send(embed=embed)
    await log_gonder(ctx.guild, embed)
    
    if uyari_sayisi >= UYARI_LIMIT:
        mute_rolu = get(ctx.guild.roles, name=MUTE_ROLU)
        if mute_rolu:
            await member.add_roles(mute_rolu)
            await ctx.send(f"🚨 {member.mention} **{UYARI_LIMIT}** uyarı! Otomatik susturuldu!")

@bot.command(name='uyarilar')
async def uyarilar(ctx, member: discord.Member = None):
    if member is None: member = ctx.author
    veri = veri_yukle()
    uid = str(member.id)
    if uid not in veri["uyarilar"] or veri["uyarilar"][uid]["sayi"] == 0: return await ctx.send(f"✅ {member.mention} uyarısı yok!")
    
    bilgi = veri["uyarilar"][uid]
    embed = discord.Embed(title=f"⚠️ {member.display_name} Uyarıları", description=f"Toplam: **{bilgi['sayi']}**", color=0xFFFF00)
    for i, u in enumerate(bilgi["sebepler"][-5:], 1):
        embed.add_field(name=f"Uyarı #{i}", value=f"📝 {u['sebep']}\n👤 {u['yetkili']}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='uyarisil')
@commands.has_permissions(manage_messages=True)
async def uyari_sil(ctx, member: discord.Member):
    veri = veri_yukle()
    uid = str(member.id)
    if uid in veri["uyarilar"]:
        veri["uyarilar"][uid] = {"isim": member.name, "sayi": 0, "sebepler": []}
        veri_kaydet(veri)
    await ctx.send(f"✅ {member.mention} uyarıları silindi!")

@bot.command(name='uyaritop')
async def uyari_top(ctx):
    """En çok uyarı alanları listeler"""
    veri = veri_yukle()
    uyarilar = veri.get("uyarilar", {})
    
    if not uyarilar: return await ctx.send("📊 Henüz uyarı verilmemiş!")
    
    sirali = sorted(uyarilar.items(), key=lambda x: x[1]["sayi"], reverse=True)[:10]
    
    embed = discord.Embed(title="⚠️ Uyarı Liderlik", color=0xFFFF00, timestamp=datetime.now())
    for i, (uid, bilgi) in enumerate(sirali, 1):
        if bilgi["sayi"] == 0: continue
        embed.add_field(name=f"{i}. {bilgi['isim']}", value=f"⚠️ **{bilgi['sayi']}** uyarı", inline=False)
    
    embed.set_footer(text="Kross Guard • Uyarı Liderlik")
    await ctx.send(embed=embed)

# -------------------- GEÇMİŞ --------------------
@bot.command(name='gecmis')
@commands.has_permissions(manage_messages=True)
async def gecmis(ctx, member: discord.Member):
    """Kullanıcının ceza geçmişini gösterir"""
    veri = veri_yukle()
    uid = str(member.id)
    
    embed = discord.Embed(title=f"📋 {member.display_name} Geçmişi", color=0x5865F2, timestamp=datetime.now())
    embed.set_thumbnail(url=member.display_avatar.url)
    
    # Uyarılar
    uyari_data = veri.get("uyarilar", {}).get(uid, {})
    uyari_sayisi = uyari_data.get("sayi", 0)
    embed.add_field(name="⚠️ Uyarı", value=str(uyari_sayisi), inline=True)
    
    # Reklam
    reklam_sayisi = veri.get("reklam_kayit", {}).get(uid, 0)
    embed.add_field(name="🚫 Reklam", value=str(reklam_sayisi), inline=True)
    
    # Küfür
    kufur_sayisi = veri.get("kufur_kayit", {}).get(uid, 0)
    embed.add_field(name="⚠️ Küfür", value=str(kufur_sayisi), inline=True)
    
    # Mute
    mute_data = veri.get("mute_kayit", {}).get(uid, {})
    mute_durum = f"🔇 Susturulmuş ({mute_data.get('sure', '?')} dk)" if mute_data else "✅ Temiz"
    embed.add_field(name="🔇 Mute", value=mute_durum, inline=True)
    
    # Son uyarılar
    if uyari_data.get("sebepler"):
        son_uyarilar = "\n".join([f"• {u['sebep'][:50]} ({u['yetkili']})" for u in uyari_data["sebepler"][-3:]])
        embed.add_field(name="📝 Son Uyarılar", value=son_uyarilar[:300] or "Yok", inline=False)
    
    embed.set_footer(text="Kross Guard • Geçmiş")
    await ctx.send(embed=embed)

# -------------------- DUYURU --------------------
@bot.command(name='duyuru')
@commands.has_permissions(manage_messages=True)
async def duyuru(ctx, *, mesaj: str):
    """Embed duyuru atar: .duyuru mesaj"""
    await ctx.message.delete()
    
    embed = discord.Embed(
        title="📢 DUYURU",
        description=mesaj,
        color=0x5865F2,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Duyuran: {ctx.author.name}")
    
    await ctx.send("@everyone", embed=embed)

# -------------------- ÇEKİLİŞ --------------------
@bot.command(name='cekilis')
@commands.has_permissions(manage_messages=True)
async def cekilis(ctx, sure: int, *, odul: str):
    """Çekiliş başlatır: .cekilis 10 Ödül (dakika)"""
    await ctx.message.delete()
    
    embed = discord.Embed(
        title="🎉 ÇEKİLİŞ!",
        description=f"**Ödül:** {odul}\n**Süre:** {sure} dakika\n\n🎉 Katılmak için 🎉 tepkisine tıkla!",
        color=0xFFD700,
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Açan: {ctx.author.name}")
    
    msg = await ctx.send("@everyone", embed=embed)
    await msg.add_reaction("🎉")
    
    await asyncio.sleep(sure * 60)
    
    try:
        msg = await ctx.channel.fetch_message(msg.id)
        reaction = get(msg.reactions, emoji="🎉")
        
        kullanicilar = []
        async for user in reaction.users():
            if not user.bot:
                kullanicilar.append(user)
        
        if kullanicilar:
            kazanan = random.choice(kullanicilar)
            sonuc_embed = discord.Embed(
                title="🎉 ÇEKİLİŞ SONUCU!",
                description=f"**Ödül:** {odul}\n**Kazanan:** {kazanan.mention}",
                color=0x00FF00,
                timestamp=datetime.now()
            )
            sonuc_embed.set_footer(text=f"Katılımcı: {len(kullanicilar)} kişi")
            await ctx.send(f"🎉 Tebrikler {kazanan.mention}! **{odul}** kazandın!", embed=sonuc_embed)
        else:
            await ctx.send("❌ Yeterli katılım olmadı!")
    except:
        await ctx.send("❌ Çekiliş sonuçlandırılamadı!")

# -------------------- VERİFİZİERT --------------------
@bot.command(name='ver')
@commands.has_permissions(manage_roles=True)
async def verifiziert_ver(ctx, member: discord.Member):
    verifiziert_rol = get(ctx.guild.roles, name="✅・Verifiziert")
    
    if not verifiziert_rol:
        try:
            verifiziert_rol = await ctx.guild.create_role(
                name="✅・Verifiziert",
                color=0x3498db,
                hoist=True,
                mentionable=False,
                reason="Verifiziert rolü"
            )
            await ctx.send("✅ Verifiziert rolü oluşturuldu!")
        except: return await ctx.send("❌ Rol oluşturulamadı!")
    
    if verifiziert_rol in member.roles: return await ctx.send(f"❌ {member.mention} zaten verifiziert!")
    
    await member.add_roles(verifiziert_rol)
    embed = discord.Embed(title="✅ Verifiziert!", description=f"{member.mention} **✅・Verifiziert** oldu!", color=0x3498db)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention)
    await ctx.send(embed=embed)

@bot.command(name='unver')
@commands.has_permissions(manage_roles=True)
async def verifiziert_al(ctx, member: discord.Member):
    verifiziert_rol = get(ctx.guild.roles, name="✅・Verifiziert")
    if not verifiziert_rol: return await ctx.send("❌ Verifiziert rolü bulunamadı!")
    if verifiziert_rol not in member.roles: return await ctx.send(f"❌ {member.mention} verifiziert değil!")
    
    await member.remove_roles(verifiziert_rol)
    embed = discord.Embed(title="❌ Verifiziert Kaldırıldı", description=f"{member.mention} verifiziert rolü alındı.", color=0xFF0000)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention)
    await ctx.send(embed=embed)

@bot.command(name='verlist')
async def verifiziert_liste(ctx):
    verifiziert_rol = get(ctx.guild.roles, name="✅・Verifiziert")
    if not verifiziert_rol: return await ctx.send("❌ Verifiziert rolü bulunamadı!")
    
    uyeler = verifiziert_rol.members
    if not uyeler: return await ctx.send("📋 Henüz verifiziert üye yok!")
    
    embed = discord.Embed(title="🔵 Verifiziert Üyeler", description="\n".join([f"• {m.mention}" for m in uyeler[:20]]), color=0x3498db)
    embed.set_footer(text=f"Toplam: {len(uyeler)} verifiziert üye")
    await ctx.send(embed=embed)

# -------------------- DM --------------------
@bot.command(name='dm')
@commands.has_permissions(administrator=True)
async def dm_herkes(ctx, *, mesaj: str):
    await ctx.send(f"📨 {ctx.guild.member_count} kişiye DM gönderiliyor...")
    basarili, basarisiz = 0, 0
    
    for member in ctx.guild.members:
        if member.bot: continue
        try:
            embed = discord.Embed(title=f"📨 {ctx.guild.name}", description=mesaj, color=0x5865F2, timestamp=datetime.now())
            embed.set_footer(text=f"Gönderen: {ctx.author.name}")
            await member.send(embed=embed)
            basarili += 1
            await asyncio.sleep(0.5)
        except: basarisiz += 1
    
    await ctx.send(f"✅ Başarılı: **{basarili}** | ❌ Başarısız: **{basarisiz}**")

@bot.command(name='dmkullanici')
@commands.has_permissions(manage_messages=True)
async def dm_kullanici(ctx, member: discord.Member, *, mesaj: str):
    try:
        embed = discord.Embed(title=f"📨 {ctx.guild.name}", description=mesaj, color=0x5865F2, timestamp=datetime.now())
        embed.set_footer(text=f"Gönderen: {ctx.author.name}")
        await member.send(embed=embed)
        await ctx.send(f"✅ {member.mention} gönderildi!")
    except: await ctx.send(f"❌ {member.mention} DM kapalı!")

@bot.command(name='dmrol')
@commands.has_permissions(manage_messages=True)
async def dm_rol(ctx, role: discord.Role, *, mesaj: str):
    await ctx.send(f"📨 **{role.name}** rolüne DM gönderiliyor...")
    basarili, basarisiz = 0, 0
    
    for member in role.members:
        if member.bot: continue
        try:
            embed = discord.Embed(title=f"📨 {ctx.guild.name}", description=mesaj, color=0x5865F2, timestamp=datetime.now())
            embed.set_footer(text=f"Gönderen: {ctx.author.name} • Rol: {role.name}")
            await member.send(embed=embed)
            basarili += 1
            await asyncio.sleep(0.3)
        except: basarisiz += 1
    
    await ctx.send(f"✅ Başarılı: **{basarili}** | ❌ Başarısız: **{basarisiz}**")

# -------------------- TEMİZLİK / LOCK / UNLOCK --------------------
@bot.command(name='temizle')
@commands.has_permissions(manage_messages=True)
async def temizle(ctx, miktar: int = 10):
    if miktar < 1 or miktar > 100: return await ctx.send("❌ 1-100 arası!")
    await ctx.channel.purge(limit=miktar + 1)
    msg = await ctx.send(f"✅ **{miktar}** mesaj silindi!")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name='yavasmod')
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, saniye: int = 0):
    if saniye < 0 or saniye > 21600: return await ctx.send("❌ 0-21600 arası!")
    await ctx.channel.edit(slowmode_delay=saniye)
    await ctx.send(f"✅ Yavaş mod: **{saniye}s**" if saniye else "✅ Yavaş mod kapandı!")

@bot.command(name='lock')
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 **Kanal kilitlendi!**")

@bot.command(name='unlock')
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 **Kanal açıldı!**")

# -------------------- BİLGİ --------------------
@bot.command(name='sunucu')
async def sunucu_bilgi(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"📊 {guild.name}", color=0x5865F2, timestamp=datetime.now())
    embed.add_field(name="👑 Sahip", value=guild.owner.mention, inline=True)
    embed.add_field(name="👥 Üye", value=str(guild.member_count), inline=True)
    embed.add_field(name="📅 Kuruluş", value=guild.created_at.strftime("%d.%m.%Y"), inline=True)
    embed.add_field(name="💬 Yazı", value=str(len(guild.text_channels)), inline=True)
    embed.add_field(name="🔊 Ses", value=str(len(guild.voice_channels)), inline=True)
    embed.add_field(name="🎭 Rol", value=str(len(guild.roles)), inline=True)
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)

@bot.command(name='kullanici')
async def kullanici_bilgi(ctx, member: discord.Member = None):
    if member is None: member = ctx.author
    embed = discord.Embed(title=f"👤 {member.display_name}", color=member.color, timestamp=datetime.now())
    embed.add_field(name="📛 İsim", value=member.name, inline=True)
    embed.add_field(name="🆔 ID", value=member.id, inline=True)
    embed.add_field(name="📅 Katılım", value=member.joined_at.strftime("%d.%m.%Y"), inline=True)
    embed.add_field(name="🎭 En Yüksek Rol", value=member.top_role.mention, inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='avatar')
async def avatar(ctx, member: discord.Member = None):
    if member is None: member = ctx.author
    embed = discord.Embed(title=f"🖼️ {member.display_name}", color=member.color)
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='botbilgi')
async def bot_bilgi(ctx):
    embed = discord.Embed(title="🤖 Kross Guard Bot", color=0x5865F2, timestamp=datetime.now())
    embed.add_field(name="📊 Sunucu", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="👥 Üye", value=str(sum(g.member_count for g in bot.guilds)), inline=True)
    embed.add_field(name="⚡ Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await ctx.send(embed=embed)

# -------------------- SOHBET --------------------
@bot.command(name='sohbet')
async def sohbet(ctx):
    konular = ["Bugün hava nasıl? 🌤️", "En son hangi filmi izledin? 🎬", "Hayalindeki tatil? 🏖️", "Hangi müzik? 🎵", "En sevdiğin yemek? 🍕", "Çay mı kahve? ☕"]
    await ctx.send(f"💬 **{random.choice(konular)}**")

@bot.command(name='efkar')
async def efkar(ctx):
    o = random.randint(0, 100)
    d = "😊 Keyifli!" if o<20 else "😐 Az efkar" if o<50 else "😔 Epey efkar" if o<80 else "😭 Çok efkarlı!"
    await ctx.send(f"🎭 {ctx.author.mention} efkar: **%{o}**\n{d}")

@bot.command(name='zar')
async def zar(ctx): await ctx.send(f"🎲 **{random.randint(1, 6)}**")

@bot.command(name='yazitura')
async def yazitura(ctx): await ctx.send(f"🪙 **{random.choice(['Yazı', 'Tura'])}**")

@bot.command(name='say')
@commands.has_permissions(manage_messages=True)
async def say(ctx, *, mesaj: str):
    await ctx.message.delete()
    await ctx.send(mesaj)

@bot.command(name='anket')
async def anket(ctx, *, soru: str):
    embed = discord.Embed(title="📊 Anket", description=soru, color=0x5865F2)
    embed.set_footer(text=f"Açan: {ctx.author.name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

# -------------------- LOG --------------------
async def log_gonder(guild, embed):
    kanal = get(guild.text_channels, name=MOD_LOG_KANALI)
    if kanal:
        try: await kanal.send(embed=embed)
        except: pass

# -------------------- YARDIM --------------------
@bot.command(name='yardim', aliases=['h', 'help'])
async def yardim(ctx):
    embed = discord.Embed(
        title="🛡️ KROSS GUARD BOT",
        description="Gelişmiş Güvenlik • Moderasyon • Çekiliş",
        color=0x5865F2,
        timestamp=datetime.now()
    )
    embed.add_field(name="🔨 **Ceza**", value="`.ban` `.unban` `.kick` `.tempban @kişi gün` `.mute` `.unmute` `.voicemute` `.voiceunmute`", inline=False)
    embed.add_field(name="⚠️ **Uyarı**", value="`.uyari` `.uyarilar` `.uyarisil` `.uyaritop`", inline=False)
    embed.add_field(name="🔵 **Verifiziert**", value="`.ver @kişi` `.unver @kişi` `.verlist`", inline=False)
    embed.add_field(name="📋 **Geçmiş**", value="`.gecmis @kişi` - Ceza geçmişi", inline=False)
    embed.add_field(name="📢 **Duyuru**", value="`.duyuru mesaj` - Embed duyuru", inline=False)
    embed.add_field(name="🎉 **Çekiliş**", value="`.cekilis 10 Ödül` (dakika)", inline=False)
    embed.add_field(name="📨 **DM**", value="`.dm` `.dmkullanici` `.dmrol`", inline=False)
    embed.add_field(name="🧹 **Kanal**", value="`.temizle` `.lock` `.unlock` `.yavasmod`", inline=False)
    embed.add_field(name="📊 **Bilgi**", value="`.sunucu` `.kullanici` `.avatar` `.botbilgi`", inline=False)
    embed.add_field(name="💬 **Sohbet**", value="`.sohbet` `.efkar` `.zar` `.yazitura` `.say` `.anket`", inline=False)
    embed.add_field(name="🤖 **Oto Sistemler**", value="⚡ Anti-Spam\n🔗 Anti-Reklam\n🚨 Anti-Phishing\n🚫 Anti-Küfür\n👋 DM Karşılama", inline=False)
    embed.set_footer(text="Kross Guard • Prefix: .")
    await ctx.send(embed=embed)

# -------------------- HATA --------------------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): return
    elif isinstance(error, commands.MissingPermissions): await ctx.send("❌ Yetkin yok!")
    elif isinstance(error, commands.MemberNotFound): await ctx.send("❌ Kullanıcı bulunamadı!")
    elif isinstance(error, commands.MissingRequiredArgument): await ctx.send("⚠️ Eksik bilgi! `.yardim`")

# -------------------- BAŞLAT --------------------
if __name__ == "__main__":
    Thread(target=run_flask).start()
    print("🛡️ Kross Guard Bot başlatılıyor...")
    print("⚡ Anti-Spam | 🔗 Anti-Reklam | 🚨 Anti-Phishing | 🚫 Anti-Küfür")
    print("🔵 Verifiziert | 📋 Geçmiş | 📢 Duyuru | 🎉 Çekiliş")
    TOKEN = os.environ.get('DISCORD_TOKEN')
    if TOKEN: bot.run(TOKEN)
    else: print("❌ Token bulunamadı!")
