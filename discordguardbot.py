import discord
from discord.ext import commands
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
OTOROL_KANALI = "otorol"
OTOROL = "Üye"
REKLAM_KELIMELER = ["discord.gg", "https://", "http://", ".com", ".net", ".xyz"]
KUFUR_KELIMELER = ["amk", "sg", "oç", "orospu", "yarrak", "siktir", "piç", "gavat", "ananı", "sülaleni"]

# -------------------- VERİ --------------------
VERI_DOSYASI = "guard_verileri.json"

def veri_yukle():
    if os.path.exists(VERI_DOSYASI):
        with open(VERI_DOSYASI, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"uyarilar": {}, "mute_kayit": {}, "welcome": {}, "leave": {}, "sayac": 0, "reklam_kayit": {}, "kufur_kayit": {}, "dm_log": []}

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
    
    bot.loop.create_task(mute_kontrol())
    bot.loop.create_task(durum_guncelle())

async def durum_guncelle():
    while True:
        await asyncio.sleep(30)
        durumlar = [
            f"{sum(g.member_count for g in bot.guilds)} üye | .yardim",
            ".yardim yazarak komutları gör",
            "🛡️ Sunucunuzu koruyorum",
            f"{len(bot.guilds)} sunucu",
            "Reklam engelleme aktif",
            "Küfür engelleme aktif"
        ]
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=random.choice(durumlar)))

async def mute_kontrol():
    while True:
        await asyncio.sleep(60)
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
                        except:
                            pass

# -------------------- HOŞ GELDİN / GÜLE GÜLE --------------------
@bot.event
async def on_member_join(member):
    # Otorol
    otorol = get(member.guild.roles, name=OTOROL)
    if otorol:
        try:
            await member.add_roles(otorol)
        except:
            pass
    
    # Hoş geldin mesajı
    veri = veri_yukle()
    welcome_data = veri["welcome"].get(str(member.guild.id), {})
    
    if welcome_data.get("aktif"):
        kanal_id = welcome_data.get("kanal")
        mesaj = welcome_data.get("mesaj", "{kullanici} sunucuya katıldı!")
        
        mesaj = mesaj.replace("{kullanici}", member.mention)
        mesaj = mesaj.replace("{kullanici_adi}", member.name)
        mesaj = mesaj.replace("{sunucu}", member.guild.name)
        mesaj = mesaj.replace("{uye_sayisi}", str(member.guild.member_count))
        
        kanal = member.guild.get_channel(int(kanal_id))
        if kanal:
            embed = discord.Embed(
                title="🌟 Hoş Geldin!",
                description=mesaj,
                color=0x00FF00,
                timestamp=datetime.now()
            )
            embed.add_field(name="👤 Kullanıcı", value=member.mention, inline=True)
            embed.add_field(name="📅 Katılım", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
            embed.add_field(name="👥 Üye Sayısı", value=str(member.guild.member_count), inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Kross Guard Bot • Hoş Geldin Sistemi")
            await kanal.send(embed=embed)
    
    # DM Hoş geldin
    try:
        dm_embed = discord.Embed(
            title=f"🌟 {member.guild.name} Sunucusuna Hoş Geldin!",
            description="Umarım keyifli vakit geçirirsin! Kurallara uymayı unutma!",
            color=0x00FF00
        )
        dm_embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else None)
        await member.send(embed=dm_embed)
    except:
        pass

@bot.event
async def on_member_remove(member):
    veri = veri_yukle()
    leave_data = veri["leave"].get(str(member.guild.id), {})
    
    if leave_data.get("aktif"):
        kanal_id = leave_data.get("kanal")
        mesaj = leave_data.get("mesaj", "{kullanici} sunucudan ayrıldı!")
        
        mesaj = mesaj.replace("{kullanici}", member.name)
        mesaj = mesaj.replace("{sunucu}", member.guild.name)
        mesaj = mesaj.replace("{uye_sayisi}", str(member.guild.member_count))
        
        kanal = member.guild.get_channel(int(kanal_id))
        if kanal:
            embed = discord.Embed(
                title="👋 Güle Güle!",
                description=mesaj,
                color=0xFF0000,
                timestamp=datetime.now()
            )
            embed.add_field(name="👤 Ayrılan", value=member.name, inline=True)
            embed.add_field(name="👥 Kalan Üye", value=str(member.guild.member_count), inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Kross Guard Bot • Ayrılış Sistemi")
            await kanal.send(embed=embed)

# -------------------- HOŞ GELDİN AYAR --------------------
@bot.command(name='hosgeldin-ayarla')
@commands.has_permissions(administrator=True)
async def welcome_ayarla(ctx, kanal: discord.TextChannel = None, *, mesaj: str = "{kullanici} sunucuya katıldı!"):
    """Hoş geldin mesajını ayarlar"""
    if kanal is None:
        return await ctx.send("❌ Bir kanal etiketle! `.hosgeldin-ayarla #kanal mesaj`")
    
    veri = veri_yukle()
    veri["welcome"][str(ctx.guild.id)] = {
        "aktif": True,
        "kanal": str(kanal.id),
        "mesaj": mesaj
    }
    veri_kaydet(veri)
    
    await ctx.send(f"✅ Hoş geldin mesajı ayarlandı!\n📝 Kanal: {kanal.mention}\n📝 Mesaj: {mesaj}")

@bot.command(name='hosgeldin-kapat')
@commands.has_permissions(administrator=True)
async def welcome_kapat(ctx):
    veri = veri_yukle()
    if str(ctx.guild.id) in veri["welcome"]:
        veri["welcome"][str(ctx.guild.id)]["aktif"] = False
        veri_kaydet(veri)
    await ctx.send("✅ Hoş geldin mesajı kapatıldı!")

# -------------------- GÜLE GÜLE AYAR --------------------
@bot.command(name='gulegule-ayarla')
@commands.has_permissions(administrator=True)
async def leave_ayarla(ctx, kanal: discord.TextChannel = None, *, mesaj: str = "{kullanici} sunucudan ayrıldı!"):
    if kanal is None:
        return await ctx.send("❌ Bir kanal etiketle!")
    
    veri = veri_yukle()
    veri["leave"][str(ctx.guild.id)] = {
        "aktif": True,
        "kanal": str(kanal.id),
        "mesaj": mesaj
    }
    veri_kaydet(veri)
    await ctx.send(f"✅ Ayrılış mesajı ayarlandı!")

# -------------------- BAN / UNBAN --------------------
@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi"):
    if member == ctx.author:
        return await ctx.send("❌ Kendini banlayamazsın!")
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Bu kullanıcıyı banlayamazsın!")
    
    try:
        # Banlamadan önce DM gönder
        try:
            dm_embed = discord.Embed(
                title=f"🔨 {ctx.guild.name} Sunucusundan Banlandınız!",
                description=f"**Sebep:** {reason}",
                color=0xFF0000
            )
            dm_embed.add_field(name="🛡️ Yetkili", value=ctx.author.name)
            await member.send(embed=dm_embed)
        except:
            pass
        
        await member.ban(reason=reason, delete_message_days=1)
        
        embed = discord.Embed(
            title="🔨 KULLANICI BANLANDI",
            description=f"**{member.name}** sunucudan yasaklandı!",
            color=0xFF0000,
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 Yasaklanan", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.add_field(name="📝 Sebep", value=reason, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Kross Guard Bot • Ban Sistemi")
        
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, embed)
    except:
        await ctx.send("❌ Yetkim yok!")

@bot.command(name='unban')
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await ctx.guild.unban(user)
        
        embed = discord.Embed(title="✅ BAN AÇILDI", description=f"**{user.name}** banı açıldı!", color=0x00FF00, timestamp=datetime.now())
        embed.add_field(name="👤 Kullanıcı", value=f"{user.mention} ({user.id})", inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.set_footer(text="Kross Guard Bot • Unban")
        
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, embed)
    except discord.NotFound:
        await ctx.send("❌ Kullanıcı bulunamadı!")

# -------------------- KICK --------------------
@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi"):
    if member == ctx.author:
        return await ctx.send("❌ Kendini atamazsın!")
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Bu kullanıcıyı atamazsın!")
    
    try:
        try:
            await member.send(f"👢 **{ctx.guild.name}** sunucusundan atıldınız!\n📝 Sebep: {reason}")
        except:
            pass
        
        await member.kick(reason=reason)
        
        embed = discord.Embed(title="👢 KULLANICI ATILDI", description=f"**{member.name}** atıldı!", color=0xFFA500, timestamp=datetime.now())
        embed.add_field(name="👤 Atılan", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.add_field(name="📝 Sebep", value=reason, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Kross Guard Bot • Kick")
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, embed)
    except:
        await ctx.send("❌ Yetkim yok!")

# -------------------- MUTE / UNMUTE --------------------
@bot.command(name='mute')
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, sure: int = 10, *, reason: str = "Sebep belirtilmedi"):
    if member == ctx.author:
        return await ctx.send("❌ Kendini susturamazsın!")
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ Bu kullanıcıyı susturamazsın!")
    
    mute_rolu = get(ctx.guild.roles, name=MUTE_ROLU)
    if not mute_rolu:
        try:
            mute_rolu = await ctx.guild.create_role(name=MUTE_ROLU, color=0x808080)
            for channel in ctx.guild.channels:
                await channel.set_permissions(mute_rolu, send_messages=False, speak=False, add_reactions=False)
        except:
            return await ctx.send("❌ Mute rolü oluşturulamadı!")
    
    try:
        await member.add_roles(mute_rolu, reason=reason)
        
        try:
            await member.send(f"🔇 **{ctx.guild.name}** sunucusunda **{sure}** dakika susturuldun!\n📝 Sebep: {reason}")
        except:
            pass
        
        embed = discord.Embed(title="🔇 SUSTURULDU", description=f"**{member.name}** susturuldu!", color=0x808080, timestamp=datetime.now())
        embed.add_field(name="👤 Kullanıcı", value=f"{member.mention}", inline=False)
        embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
        embed.add_field(name="⏱️ Süre", value=f"{sure} dakika", inline=True)
        embed.add_field(name="📝 Sebep", value=reason, inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Kross Guard Bot • Mute")
        await ctx.send(embed=embed)
        await log_gonder(ctx.guild, embed)
        
        veri = veri_yukle()
        veri["mute_kayit"][str(member.id)] = {"sure": sure, "baslangic": datetime.now().isoformat(), "yetkili": ctx.author.name}
        veri_kaydet(veri)
        
    except:
        await ctx.send("❌ Yetkim yok!")

@bot.command(name='unmute')
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    mute_rolu = get(ctx.guild.roles, name=MUTE_ROLU)
    if not mute_rolu or mute_rolu not in member.roles:
        return await ctx.send("❌ Susturulmamış!")
    
    await member.remove_roles(mute_rolu)
    embed = discord.Embed(title="🔊 SUSTURMA AÇILDI", description=f"**{member.name}** susturması açıldı!", color=0x00FF00, timestamp=datetime.now())
    embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
    embed.set_footer(text="Kross Guard Bot • Unmute")
    await ctx.send(embed=embed)
    await log_gonder(ctx.guild, embed)

# -------------------- UYARI --------------------
@bot.command(name='uyari')
@commands.has_permissions(manage_messages=True)
async def uyari(ctx, member: discord.Member, *, reason: str = "Sebep belirtilmedi"):
    if member == ctx.author:
        return await ctx.send("❌ Kendine uyarı veremezsin!")
    
    veri = veri_yukle()
    uid = str(member.id)
    
    if uid not in veri["uyarilar"]:
        veri["uyarilar"][uid] = {"isim": member.name, "sayi": 0, "sebepler": []}
    
    veri["uyarilar"][uid]["sayi"] += 1
    veri["uyarilar"][uid]["sebepler"].append({"sebep": reason, "yetkili": ctx.author.name, "tarih": datetime.now().isoformat()})
    veri_kaydet(veri)
    
    uyari_sayisi = veri["uyarilar"][uid]["sayi"]
    
    embed = discord.Embed(title="⚠️ UYARI VERİLDİ", description=f"**{member.name}** uyarı aldı!", color=0xFFFF00, timestamp=datetime.now())
    embed.add_field(name="👤 Kullanıcı", value=member.mention, inline=False)
    embed.add_field(name="🛡️ Yetkili", value=ctx.author.mention, inline=True)
    embed.add_field(name="⚠️ Uyarı", value=f"**{uyari_sayisi}/{UYARI_LIMIT}**", inline=True)
    embed.add_field(name="📝 Sebep", value=reason, inline=False)
    embed.set_footer(text="Kross Guard Bot • Uyarı")
    await ctx.send(embed=embed)
    await log_gonder(ctx.guild, embed)
    
    if uyari_sayisi >= UYARI_LIMIT:
        mute_rolu = get(ctx.guild.roles, name=MUTE_ROLU)
        if mute_rolu:
            await member.add_roles(mute_rolu)
            await ctx.send(f"🚨 {member.mention} **{UYARI_LIMIT}** uyarıya ulaştı! Otomatik susturuldu!")

@bot.command(name='uyarilar')
async def uyarilar(ctx, member: discord.Member = None):
    if member is None: member = ctx.author
    veri = veri_yukle()
    uid = str(member.id)
    
    if uid not in veri["uyarilar"] or veri["uyarilar"][uid]["sayi"] == 0:
        return await ctx.send(f"✅ {member.mention} hiç uyarı almamış!")
    
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

# -------------------- DM KOMUTLARI --------------------
@bot.command(name='dm')
@commands.has_permissions(administrator=True)
async def dm_herkes(ctx, *, mesaj: str):
    """Sunucudaki TÜM üyelere DM gönderir: .dm mesaj"""
    
    await ctx.send(f"📨 Tüm üyelere DM gönderiliyor... ({ctx.guild.member_count} kişi)")
    
    basarili = 0
    basarisiz = 0
    
    for member in ctx.guild.members:
        if member.bot:
            continue
        try:
            embed = discord.Embed(
                title=f"📨 {ctx.guild.name}",
                description=mesaj,
                color=0x5865F2,
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Gönderen: {ctx.author.name}")
            await member.send(embed=embed)
            basarili += 1
            await asyncio.sleep(0.5)
        except:
            basarisiz += 1
    
    await ctx.send(f"✅ DM Gönderimi Tamamlandı!\n📨 Başarılı: **{basarili}**\n❌ Başarısız (DM kapalı): **{basarisiz}**")

@bot.command(name='dmkullanici')
@commands.has_permissions(manage_messages=True)
async def dm_kullanici(ctx, member: discord.Member, *, mesaj: str):
    """Belirli bir kullanıcıya DM gönderir: .dmkullanici @kişi mesaj"""
    
    try:
        embed = discord.Embed(
            title=f"📨 {ctx.guild.name}",
            description=mesaj,
            color=0x5865F2,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Gönderen: {ctx.author.name}")
        await member.send(embed=embed)
        await ctx.send(f"✅ {member.mention} kullanıcısına DM gönderildi!")
    except:
        await ctx.send(f"❌ {member.mention} DM almayı kapatmış!")

@bot.command(name='dmrol')
@commands.has_permissions(manage_messages=True)
async def dm_rol(ctx, role: discord.Role, *, mesaj: str):
    """Belirli bir role sahip üyelere DM gönderir: .dmrol @rol mesaj"""
    
    await ctx.send(f"📨 **{role.name}** rolündeki üyelere DM gönderiliyor...")
    
    basarili = 0
    basarisiz = 0
    
    for member in role.members:
        if member.bot:
            continue
        try:
            embed = discord.Embed(
                title=f"📨 {ctx.guild.name}",
                description=mesaj,
                color=0x5865F2,
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Gönderen: {ctx.author.name} • Rol: {role.name}")
            await member.send(embed=embed)
            basarili += 1
            await asyncio.sleep(0.3)
        except:
            basarisiz += 1
    
    await ctx.send(f"✅ DM Gönderimi Tamamlandı!\n📨 Başarılı: **{basarili}**\n❌ Başarısız: **{basarisiz}**")

# -------------------- REKLAM ENGELLE --------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Reklam engelleme
    for kelime in REKLAM_KELIMELER:
        if kelime in message.content.lower():
            if message.author.guild_permissions.administrator:
                return
            
            await message.delete()
            
            veri = veri_yukle()
            uid = str(message.author.id)
            if uid not in veri["reklam_kayit"]:
                veri["reklam_kayit"][uid] = 0
            veri["reklam_kayit"][uid] += 1
            veri_kaydet(veri)
            
            uyari_mesaji = await message.channel.send(f"🚫 {message.author.mention} **Reklam yapmak yasak!** ({veri['reklam_kayit'][uid]}. ihlal)")
            await asyncio.sleep(5)
            await uyari_mesaji.delete()
            
            await log_gonder(message.guild, discord.Embed(
                title="🚫 REKLAM ENGELLENDİ",
                description=f"{message.author.mention} reklam yapmaya çalıştı!",
                color=0xFF0000,
                timestamp=datetime.now()
            ).add_field(name="📝 Mesaj", value=message.content[:100], inline=False))
            
            break
    
    # Küfür engelleme
    for kelime in KUFUR_KELIMELER:
        if kelime in message.content.lower().split():
            if message.author.guild_permissions.administrator:
                return
            
            await message.delete()
            
            veri = veri_yukle()
            uid = str(message.author.id)
            if uid not in veri["kufur_kayit"]:
                veri["kufur_kayit"][uid] = 0
            veri["kufur_kayit"][uid] += 1
            veri_kaydet(veri)
            
            uyari = await message.channel.send(f"⚠️ {message.author.mention} **Küfür etme!** ({veri['kufur_kayit'][uid]}. ihlal)")
            await asyncio.sleep(5)
            await uyari.delete()
            break
    
    await bot.process_commands(message)

# -------------------- TEMİZLİK --------------------
@bot.command(name='temizle')
@commands.has_permissions(manage_messages=True)
async def temizle(ctx, miktar: int = 10):
    if miktar < 1 or miktar > 100:
        return await ctx.send("❌ 1-100 arası!")
    await ctx.channel.purge(limit=miktar + 1)
    msg = await ctx.send(f"✅ **{miktar}** mesaj silindi!")
    await asyncio.sleep(3)
    await msg.delete()

# -------------------- YAVAŞ MOD --------------------
@bot.command(name='yavasmod')
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, saniye: int = 0):
    if saniye < 0 or saniye > 21600:
        return await ctx.send("❌ 0-21600 arası!")
    await ctx.channel.edit(slowmode_delay=saniye)
    await ctx.send(f"✅ Yavaş mod: **{saniye}s**" if saniye else "✅ Yavaş mod kapandı!")

# -------------------- LOCK / UNLOCK --------------------
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

# -------------------- BİLGİ KOMUTLARI --------------------
@bot.command(name='sunucu')
async def sunucu_bilgi(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"📊 {guild.name}", color=0x5865F2, timestamp=datetime.now())
    embed.add_field(name="👑 Sahip", value=guild.owner.mention, inline=True)
    embed.add_field(name="👥 Üye", value=str(guild.member_count), inline=True)
    embed.add_field(name="📅 Kuruluş", value=guild.created_at.strftime("%d.%m.%Y"), inline=True)
    embed.add_field(name="💬 Yazı Kanalı", value=str(len(guild.text_channels)), inline=True)
    embed.add_field(name="🔊 Ses Kanalı", value=str(len(guild.voice_channels)), inline=True)
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
    embed.add_field(name="👥 Toplam Üye", value=str(sum(g.member_count for g in bot.guilds)), inline=True)
    embed.add_field(name="⚡ Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="Kross Guard Bot • Python discord.py")
    await ctx.send(embed=embed)

# -------------------- SOHBET --------------------
@bot.command(name='sohbet')
async def sohbet(ctx):
    konular = ["Bugün hava nasıl? 🌤️", "En son hangi filmi izledin? 🎬", "Hayalindeki tatil? 🏖️", "Hangi müzik? 🎵", "En sevdiğin yemek? 🍕", "Çay mı kahve? ☕", "Evcil hayvan? 🐱", "Hangi oyun? 🎮", "Komik anın? 😂"]
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
        await kanal.send(embed=embed)

# -------------------- YARDIM --------------------
@bot.command(name='yardim', aliases=['h', 'help'])
async def yardim(ctx):
    embed = discord.Embed(
        title="🛡️ KROSS GUARD BOT",
        description="Güvenlik • Moderasyon • DM • Sohbet",
        color=0x5865F2,
        timestamp=datetime.now()
    )
    embed.add_field(name="🔨 **Ceza**", value="`.ban` `.unban` `.kick` `.mute` `.unmute`", inline=False)
    embed.add_field(name="⚠️ **Uyarı**", value="`.uyari` `.uyarilar` `.uyarisil`", inline=False)
    embed.add_field(name="📨 **DM**", value="`.dm mesaj` `.dmkullanici @kişi mesaj` `.dmrol @rol mesaj`", inline=False)
    embed.add_field(name="🧹 **Kanal**", value="`.temizle` `.lock` `.unlock` `.yavasmod`", inline=False)
    embed.add_field(name="⚙️ **Ayarlar**", value="`.hosgeldin-ayarla` `.gulegule-ayarla` `.hosgeldin-kapat`", inline=False)
    embed.add_field(name="📊 **Bilgi**", value="`.sunucu` `.kullanici` `.avatar` `.botbilgi`", inline=False)
    embed.add_field(name="💬 **Sohbet**", value="`.sohbet` `.efkar` `.zar` `.yazitura` `.say` `.anket`", inline=False)
    embed.set_footer(text="Kross Guard Bot • Prefix: .")
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
    TOKEN = os.environ.get('DISCORD_TOKEN')
    if TOKEN: bot.run(TOKEN)
    else: print("❌ Token bulunamadı!")
