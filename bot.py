import asyncio
import os
import time
from datetime import datetime

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

import database

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
VIEW_TTL = 15 * 60


def money(value):
    return f"{value:,} บาท"


def stamp(value):
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def set_label(item):
    return f"Set #{item['id']} — {item['name']}"


@bot.event
async def on_ready():
    database.init_db()
    if not cleanup_views.is_running():
        cleanup_views.start()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@tasks.loop(seconds=60)
async def cleanup_views():
    for view in database.get_expired_views():
        guild = bot.get_guild(view["guild_id"])
        if guild:
            channel = guild.get_channel(view["channel_id"])
            if channel:
                try:
                    await channel.delete(reason="EcoBot temporary set view expired")
                except discord.HTTPException:
                    pass
        database.delete_set_view(view["set_id"])


@cleanup_views.before_loop
async def before_cleanup():
    await bot.wait_until_ready()


@bot.command(name="รับ")
async def income(ctx, amount: int, *, description="ไม่ระบุรายละเอียด"):
    if amount <= 0:
        await ctx.send("❌ จำนวนเงินต้องมากกว่า 0")
        return
    try:
        database.add_transaction("income", amount, description, ctx.message.id)
    except ValueError as error:
        if str(error) == "DUPLICATE_MESSAGE":
            return
        if str(error) == "NO_ACTIVE_SESSION":
            await ctx.send("❌ ไม่มี session ที่กำลังใช้งานอยู่ ใช้ `!newday` เพื่อเริ่ม session ใหม่")
            return
        raise
    await ctx.send(f"✅ บันทึกรายรับ **{money(amount)}** — {description}")


@bot.command(name="จ่าย")
async def expense(ctx, amount: int, *, description="ไม่ระบุรายละเอียด"):
    if amount <= 0:
        await ctx.send("❌ จำนวนเงินต้องมากกว่า 0")
        return
    try:
        database.add_transaction("expense", amount, description, ctx.message.id)
    except ValueError as error:
        if str(error) == "DUPLICATE_MESSAGE":
            return
        if str(error) == "NO_ACTIVE_SESSION":
            await ctx.send("❌ ไม่มี session ที่กำลังใช้งานอยู่ ใช้ `!newday` เพื่อเริ่ม session ใหม่")
            return
        raise
    await ctx.send(f"✅ บันทึกรายจ่าย **{money(amount)}** — {description}")


@bot.command(name="help", aliases=["?"])
async def help_command(ctx):
    await ctx.send("""📖 **EcoBot Commands**

`!รับ <จำนวน> <รายละเอียด>` — บันทึกรายรับ
`!จ่าย <จำนวน> <รายละเอียด>` — บันทึกรายจ่าย
`!สรุป` — ดูสรุป session ปัจจุบัน
`!newday` — จบ session เดิมและเริ่มวัน/session ใหม่
`!delsession <ID>` — ลบ session ที่จบแล้ว
`!clearall` — ล้างข้อมูลทั้งหมด (ต้องพิมพ์ `CONFIRM`)
`!newset <ชื่อ>` — สร้าง Set ใหม่
`!set <เลขหรือชื่อ>` — ผูกวันปัจจุบันเข้ากับ Set
`!setname <เลขหรือชื่อ> <ชื่อใหม่>` — เปลี่ยนชื่อ Set
`!showset <เลขหรือชื่อ>` — เปิดดู Set ในห้องชั่วคราว
`!hideset [เลขหรือชื่อ]` — ปิดห้อง Set ชั่วคราว

💡 `!?` และ `!help` ใช้คำสั่งเดียวกัน""")


@bot.command(name="clearall")
async def clear_all_command(ctx):
    await ctx.send(
        "⚠️ **ยืนยันการล้างข้อมูลทั้งหมด**\n"
        "ข้อมูลรายรับ รายจ่าย, session และ Set ทั้งหมดจะถูกลบถาวร\n"
        "พิมพ์ `CONFIRM` ภายใน 30 วินาทีเพื่อยืนยัน"
    )

    def check(message):
        return (
            message.author.id == ctx.author.id
            and message.channel.id == ctx.channel.id
            and message.content.strip() == "CONFIRM"
        )

    try:
        await bot.wait_for("message", check=check, timeout=30)
    except asyncio.TimeoutError:
        await ctx.send("❌ หมดเวลา ยกเลิกการล้างข้อมูล")
        return

    database.clear_all()
    day = database.get_or_create_active_day()
    await ctx.send(
        "🗑️ **ล้างข้อมูลทั้งหมดแล้ว**\n"
        f"สร้าง session ใหม่แล้ว: `{stamp(day['started_at'])}`"
    )


@bot.command(name="newset")
async def new_set(ctx, *, name):
    set_id = database.create_set(name.strip())
    await ctx.send(f"📦 สร้าง **Set #{set_id} — {name.strip()}** แล้ว")


@bot.command(name="setname")
async def set_name(ctx, ref, *, name):
    if not database.rename_set(ref, name.strip()):
        await ctx.send("❌ ไม่พบ Set นี้")
        return
    item = database.get_set(ref)
    await ctx.send(f"✏️ เปลี่ยนชื่อเป็น **{set_label(item)}** แล้ว")


@bot.command(name="set")
async def assign_set(ctx, ref):
    item = database.get_set(ref)
    if not item:
        await ctx.send("❌ ไม่พบ Set นี้")
        return
    database.get_or_create_active_day(item["id"])
    await ctx.send(f"📌 วันปัจจุบันอยู่ใน **{set_label(item)}** แล้ว")


@bot.command(name="newday")
async def new_day(ctx, ref=None):
    active = database.get_active_day()
    if not active:
        set_id = None
        if ref is not None:
            item = database.get_set(ref)
            if not item:
                await ctx.send("❌ ไม่พบ Set นี้")
                return
            set_id = item["id"]
        day = database.get_or_create_active_day(set_id)
        target = database.get_set(set_id) if set_id else None
        text = f"🌅 **เริ่มวันใหม่แล้ว!**\nเริ่ม session ใหม่: `{stamp(day['started_at'])}`"
        if target:
            text += f"\nSet: **{set_label(target)}**"
        await ctx.send(text)
        return

    set_id = active["set_id"]
    if ref is not None:
        item = database.get_set(ref)
        if not item:
            await ctx.send("❌ ไม่พบ Set นี้")
            return
        set_id = item["id"]
    day = database.reset_day(set_id)
    target = database.get_set(set_id) if set_id else None
    text = f"🌅 **เริ่มวันใหม่แล้ว!**\nเริ่ม session ใหม่: `{stamp(day['started_at'])}`"
    if target:
        text += f"\nSet: **{set_label(target)}**"
    await ctx.send(text)


@bot.command(name="delsession")
async def delete_session(ctx, day_id: int):
    if database.delete_day(day_id):
        await ctx.send(f"🗑️ ลบ session #{day_id} แล้ว")
    else:
        await ctx.send("❌ ลบไม่ได้: ไม่พบ session หรือ session นี้ยังไม่จบ")


@bot.command(name="สรุป")
async def summary(ctx):
    day = database.get_or_create_active_day()
    rows, income, expense, balance = database.get_day_summary(day["id"])
    lines = [
        "📊 **สรุป session ปัจจุบัน**",
        f"เริ่ม: {stamp(day['started_at'])}",
    ]
    if day["set_id"]:
        item = database.get_set(day["set_id"])
        if item:
            lines.append(f"Set: {set_label(item)}")
    lines += ["", "```text", f"{'รายการ':<24} {'ประเภท':<10} {'จำนวน':>12}", "-" * 48]
    for row in rows:
        kind = "รายรับ" if row["type"] == "income" else "รายจ่าย"
        sign = "+" if row["type"] == "income" else "-"
        lines.append(f"{row['description'][:24]:<24} {kind:<10} {sign}{row['amount']:>10,}")
    lines += ["-" * 48, f"{'รายรับรวม':<34} {income:>12,}", f"{'รายจ่ายรวม':<34} {expense:>12,}", f"{'คงเหลือ':<34} {balance:>12,}", "```"]
    await ctx.send("\n".join(lines))


@bot.command(name="showset")
async def show_set(ctx, *, ref):
    item = database.get_set(ref)
    if not item:
        await ctx.send("❌ ไม่พบ Set นี้")
        return

    existing = database.get_set_view(item["id"])
    if existing:
        channel = ctx.guild.get_channel(existing["channel_id"])
        if channel:
            await ctx.send(f"👀 Set นี้เปิดอยู่แล้ว: {channel.mention}")
            return
        database.delete_set_view(item["id"])

    category = ctx.channel.category
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    try:
        channel = await ctx.guild.create_text_channel(
            f"set-{item['id']}-{item['name'][:40]}",
            category=category,
            overwrites=overwrites,
            reason="EcoBot temporary set view",
        )
    except discord.Forbidden:
        await ctx.send(
            "❌ EcoBot ไม่มีสิทธิ์สร้างห้องนี้\n"
            "ตรวจสอบสิทธิ์ **Manage Channels** ของบอทในเซิร์ฟเวอร์/หมวดหมู่นี้ก่อน"
        )
        return
    expires = int(time.time()) + VIEW_TTL
    database.save_set_view(item["id"], ctx.guild.id, channel.id, ctx.author.id, expires)

    days, rows, income, expense, balance = database.get_set_summary(item["id"])
    lines = [
        f"📦 **{set_label(item)}**",
        f"สร้าง Set: {stamp(item['created_at'])}",
        "",
        "**Sessions / วันที่**",
    ]
    for day in days:
        lines.append(f"• `{stamp(day['started_at'])}`" + (f" → `{stamp(day['ended_at'])}`" if day['ended_at'] else " (กำลังใช้งาน)"))
    if not days:
        lines.append("• ยังไม่มี session")
    lines += [
        "",
        "**ยอดรวม**",
        f"รายรับ: **{money(income)}**",
        f"รายจ่าย: **{money(expense)}**",
        f"คงเหลือ: **{money(balance)}**",
        "",
        f"⏱️ ห้องนี้จะลบอัตโนมัติใน {VIEW_TTL // 60} นาที",
        "ใช้ `!hideset` เพื่อลบทันที",
    ]
    await channel.send("\n".join(lines))
    await ctx.send(f"📊 เปิดดู **{set_label(item)}** ที่ {channel.mention}")


@bot.command(name="hideset")
async def hide_set(ctx, ref=None):
    if ref is None:
        found = None
        for item in database.get_expired_views(int(time.time()) + VIEW_TTL + 1):
            if item["channel_id"] == ctx.channel.id:
                found = item
                break
        if found:
            database.delete_set_view(found["set_id"])
        if ctx.channel != ctx.guild.system_channel and ctx.channel.name.startswith("set-"):
            await ctx.channel.delete(reason="EcoBot set view closed by user")
            return
        await ctx.send("❌ คำสั่งนี้ต้องใช้ในห้อง Set ชั่วคราว หรือระบุ Set เช่น `!hideset 1`")
        return

    item = database.get_set(ref)
    if not item:
        await ctx.send("❌ ไม่พบ Set นี้")
        return
    view = database.get_set_view(item["id"])
    if not view:
        await ctx.send("ℹ️ Set นี้ไม่ได้เปิดอยู่")
        return
    channel = ctx.guild.get_channel(view["channel_id"])
    database.delete_set_view(item["id"])
    if channel:
        await channel.delete(reason="EcoBot set view closed by user")
    else:
        await ctx.send("🧹 ล้างข้อมูลห้องชั่วคราวของ Set แล้ว")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ ใช้คำสั่งไม่ครบ เช่น `!รับ 500 ขายของ` หรือ `!showset 1`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ จำนวนเงินต้องเป็นตัวเลข เช่น `!รับ 500 ขายของ`")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        raise error


bot.run(TOKEN)
