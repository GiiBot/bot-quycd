
import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands
from dotenv import load_dotenv

# ================= LOAD ENV =================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ================= CONFIG =================
FUND_CHANNEL_ID = 123456789012345678  # ID kênh ghi quỹ
DB_FILE = "fund.db"
TIMEZONE = timezone(timedelta(hours=7))  # VN

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATABASE =================
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS fund (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    balance INTEGER NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY AUTOINCREMENT,
    user TEXT,
    amount INTEGER,
    content TEXT,
    time TEXT
)
""")

cursor.execute("INSERT OR IGNORE INTO fund (id, balance) VALUES (1, 0)")
conn.commit()

# ================= UTILS =================
def format_money(x: int):
    return f"{x:,}".replace(",", ".")

def parse_amount(text: str):
    """
    Nhận diện:
    +5000000
    -25m
    +10M
    +5k
    """
    match = re.search(r"([+-])\s*(\d+(?:\.\d+)?)([mMkK]?)", text)
    if not match:
        return None

    sign, number, unit = match.groups()
    value = float(number)

    if unit.lower() == "m":
        value *= 1_000_000
    elif unit.lower() == "k":
        value *= 1_000

    value = int(value)
    if sign == "-":
        value = -value

    return value

# ================= EVENTS =================
@bot.event
async def on_ready():
    print(f"BOT ONLINE: {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # ❗ CHỈ NHẬN DIỆN TRONG 1 KÊNH
    if message.channel.id != FUND_CHANNEL_ID:
        return

    amount = parse_amount(message.content)
    if amount is None:
        return

    # Lấy số dư
    cursor.execute("SELECT balance FROM fund WHERE id = 1")
    balance = cursor.fetchone()[0]
    new_balance = balance + amount

    if new_balance < 0:
        await message.reply("❌ **Quỹ chiếm đóng không đủ tiền để trừ.**")
        return

    # Update DB
    cursor.execute(
        "UPDATE fund SET balance = ? WHERE id = 1",
        (new_balance,)
    )
    cursor.execute(
        "INSERT INTO logs (user, amount, content, time) VALUES (?, ?, ?, ?)",
        (
            str(message.author),
            amount,
            message.content,
            datetime.now(TIMEZONE).strftime("%d/%m/%Y %H:%M")
        )
    )
    conn.commit()

    # Phản hồi cập nhật quỹ
    sign = "+" if amount > 0 else ""
    embed = discord.Embed(
        title="📒 SỔ QUỸ CHIẾM ĐÓNG (ĐÃ CẬP NHẬT)",
        color=0x2ecc71 if amount > 0 else 0xe74c3c,
        timestamp=datetime.now(TIMEZONE)
    )

    embed.add_field(
        name="👤 Người ghi",
        value=message.author.mention,
        inline=False
    )

    embed.add_field(
        name="💰 Giao dịch",
        value=f"{sign}{format_money(amount)}$",
        inline=False
    )

    embed.add_field(
        name="📊 TỔNG QUỸ CHIẾM ĐÓNG HIỆN TẠI",
        value=f"**{format_money(new_balance)}$**",
        inline=False
    )

    embed.add_field(
        name="📝 Nội dung",
        value=message.content,
        inline=False
    )

    await message.reply(embed=embed)

    await bot.process_commands(message)

# ================= COMMANDS =================
@bot.command(name="quy")
async def xem_quy(ctx):
    cursor.execute("SELECT balance FROM fund WHERE id = 1")
    balance = cursor.fetchone()[0]
    await ctx.send(f"💰 **QUỸ CHIẾM ĐÓNG HIỆN TẠI:** `{format_money(balance)}$`")

@bot.command(name="logquy")
async def xem_log(ctx, limit: int = 10):
    cursor.execute(
        "SELECT user, amount, content, time FROM logs ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()

    if not rows:
        return await ctx.send("📭 Chưa có giao dịch nào.")

    msg = ""
    for user, amount, content, time in rows:
        sign = "+" if amount > 0 else ""
        msg += f"[{time}] {sign}{format_money(amount)}$ | {user}\n{content}\n\n"

    await ctx.send(f"```{msg}```")

# ================= RUN =================
bot.run(TOKEN)
