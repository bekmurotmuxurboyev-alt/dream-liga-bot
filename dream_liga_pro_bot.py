#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏆 DREAM LIGA PRO BOT
4v4 | 8v8 | 16v16 | Davomiy Liga
O'zbekcha Telegram Bot
"""

import logging
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

import os
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # @BotFather dan oling

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ── HOLATLAR ──────────────────────────────────────────────────────────────────
(
    WAIT_TOUR_NAME,
    WAIT_TEAM_NAME,
    WAIT_SCORE,
    WAIT_JOIN_ID,
    MAIN,
) = range(5)

# ── MA'LUMOTLAR ───────────────────────────────────────────────────────────────
db = {}  # {id: tournament}

FORMATS = {
    "4v4":    {"name": "⚡ Mini Cup (4 jamoa)",    "size": 4,  "type": "knockout"},
    "8v8":    {"name": "🏆 Standart Cup (8 jamoa)", "size": 8,  "type": "knockout"},
    "16v16":  {"name": "🌟 Mega Cup (16 jamoa)",    "size": 16, "type": "groups_knockout"},
    "league": {"name": "📅 Davomiy Liga",           "size": 0,  "type": "league"},
}

# ── YORDAMCHI ─────────────────────────────────────────────────────────────────
def new_id():
    return f"DL{random.randint(10000,99999)}"

def init_stat():
    return {"o":0,"g":0,"d":0,"y":0,"gf":0,"ga":0,"gd":0,"pts":0}

def update_stat(t, home, away, hs, as_):
    for team in [home, away]:
        if team not in t["stats"]:
            t["stats"][team] = init_stat()
    h, a = t["stats"][home], t["stats"][away]
    h["o"]+=1; a["o"]+=1
    h["gf"]+=hs; h["ga"]+=as_; h["gd"]=h["gf"]-h["ga"]
    a["gf"]+=as_; a["ga"]+=hs; a["gd"]=a["gf"]-a["ga"]
    if hs>as_:   h["g"]+=1; h["pts"]+=3; a["y"]+=1
    elif hs<as_: a["g"]+=1; a["pts"]+=3; h["y"]+=1
    else:        h["d"]+=1; h["pts"]+=1; a["d"]+=1; a["pts"]+=1

def sorted_teams(t):
    return sorted(t["teams"], key=lambda x: (
        t["stats"].get(x, init_stat())["pts"],
        t["stats"].get(x, init_stat())["gd"],
        t["stats"].get(x, init_stat())["gf"]
    ), reverse=True)

def standings_text(t):
    lines = [f"📊 *{t['name']} — JADVAL*\n",
             "`# Jamoa            O  G  D  Y  GM GY  Oc`"]
    for i, tm in enumerate(sorted_teams(t), 1):
        s = t["stats"].get(tm, init_stat())
        lines.append(f"`{i:<2} {tm:<16} {s['o']:<2} {s['g']:<2} {s['d']:<2} {s['y']:<2} {s['gf']:<2} {s['ga']:<2} {s['pts']:<3}`")
    return "\n".join(lines)

def make_bracket(teams):
    size = 1
    while size < len(teams): size *= 2
    pool = teams[:] + ["BYE"]*(size-len(teams))
    random.shuffle(pool)
    rounds = []
    current = []
    for i in range(0, len(pool), 2):
        h, a = pool[i], pool[i+1]
        played = a == "BYE"
        current.append({"home":h,"away":a,"played":played,
                        "hs":1 if played else 0,"as":0,
                        "winner":h if played else None})
    rounds.append(current)
    return rounds

def bracket_text(t):
    rounds = t.get("bracket", [])
    if not rounds: return "🏆 Bracket hali yo'q."
    names = ["1/8 Final","1/4 Final","Yarim Final","🏆 FINAL"]
    lines = [f"🏆 *{t['name']} — BRACKET*\n"]
    for i, rnd in enumerate(rounds):
        lines.append(f"\n*— {names[i] if i<len(names) else f'{i+1}-tur'} —*")
        for m in rnd:
            if m["away"] == "BYE":
                lines.append(f"  ✅ {m['home']} (BYE)")
            elif m["played"]:
                lines.append(f"  {m['home']} *{m['hs']}:{m['as']}* {m['away']}")
            else:
                lines.append(f"  {m['home']} 🆚 {m['away']}")
    return "\n".join(lines)

def gen_league_matches(teams):
    matches = []
    for i in range(len(teams)):
        for j in range(i+1, len(teams)):
            matches.append({"home":teams[i],"away":teams[j],"played":False,"hs":0,"as":0})
            matches.append({"home":teams[j],"away":teams[i],"played":False,"hs":0,"as":0})
    random.shuffle(matches)
    return matches

def t_menu_kb(tid):
    t = db[tid]
    fmt = t["format"]
    status = t["status"]
    rows = [
        [InlineKeyboardButton("👥 Jamoalar", callback_data=f"teams_{tid}"),
         InlineKeyboardButton("📊 Jadval", callback_data=f"stand_{tid}")],
        [InlineKeyboardButton("📅 O'yinlar", callback_data=f"matches_{tid}"),
         InlineKeyboardButton("🏆 Bracket", callback_data=f"bracket_{tid}")],
    ]
    if status == "reg":
        rows.append([
            InlineKeyboardButton("➕ Jamoa", callback_data=f"addteam_{tid}"),
            InlineKeyboardButton("▶️ Boshlash", callback_data=f"begin_{tid}"),
        ])
    if status in ("group","league","playoff"):
        rows.append([InlineKeyboardButton("⚽ Natija kiritish", callback_data=f"score_{tid}")])
    rows.append([InlineKeyboardButton("🏠 Menyu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)

# ── BOSHLASH ──────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 *DREAM LIGA PRO*\n\n"
        "Turnir o'tkazish uchun eng zo'r bot!\n"
        "4v4 • 8v8 • 16v16 • Davomiy Liga\n\n"
        "Boshlash uchun tugmani bosing:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 Turnir yaratish", callback_data="create")],
            [InlineKeyboardButton("📋 Turnirlarim", callback_data="mine")],
            [InlineKeyboardButton("🔍 Turnirga kirish", callback_data="join")],
            [InlineKeyboardButton("📈 Reyting", callback_data="rating")],
            [InlineKeyboardButton("ℹ️ Yordam", callback_data="help")],
        ])
    )
    return MAIN

async def menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🏠 *Asosiy Menyu*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 Turnir yaratish", callback_data="create")],
            [InlineKeyboardButton("📋 Turnirlarim", callback_data="mine")],
            [InlineKeyboardButton("🔍 Turnirga kirish", callback_data="join")],
            [InlineKeyboardButton("📈 Reyting", callback_data="rating")],
            [InlineKeyboardButton("ℹ️ Yordam", callback_data="help")],
        ])
    )
    return MAIN

# ── TURNIR YARATISH ───────────────────────────────────────────────────────────
async def create_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🏆 *Yangi Turnir*\n\nTurnir nomini yozing:",
        parse_mode="Markdown"
    )
    ctx.user_data["action"] = "create"
    return WAIT_TOUR_NAME

async def got_tour_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("❌ Nom juda qisqa!")
        return WAIT_TOUR_NAME
    ctx.user_data["tname"] = name
    rows = [[InlineKeyboardButton(v["name"], callback_data=f"fmt_{k}")] for k,v in FORMATS.items()]
    await update.message.reply_text(
        f"✅ Nom: *{name}*\n\nFormat tanlang:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return MAIN

async def fmt_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    fmt = q.data.replace("fmt_","")
    name = ctx.user_data.get("tname","Turnir")
    uid = q.from_user.id
    tid = new_id()
    db[tid] = {
        "id": tid, "name": name, "format": fmt,
        "admin": uid, "teams": [], "stats": {},
        "matches": [], "bracket": [],
        "status": "reg", "champion": None,
        "season": 1,
        "created": datetime.now().strftime("%d.%m.%Y"),
    }
    finfo = FORMATS[fmt]
    hint = f"Jami {finfo['size']} ta jamoa kerak" if finfo['size'] else "Istalgancha jamoa qo'shing"
    await q.edit_message_text(
        f"🎉 *Turnir yaratildi!*\n\n"
        f"📌 ID: `{tid}`\n"
        f"🏆 Nom: *{name}*\n"
        f"📋 Format: {finfo['name']}\n"
        f"💡 {hint}\n\n"
        f"Jamoalarni qo'shing:",
        parse_mode="Markdown",
        reply_markup=t_menu_kb(tid)
    )
    return MAIN

# ── JAMOA QO'SHISH ────────────────────────────────────────────────────────────
async def addteam_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = q.data.replace("addteam_","")
    t = db.get(tid)
    ctx.user_data["addteam_tid"] = tid
    await q.edit_message_text(
        f"➕ *Jamoa qo'shish*\n"
        f"Turnir: *{t['name']}*\n"
        f"Hozir: {len(t['teams'])} ta jamoa\n\n"
        f"Jamoa nomini yozing:",
        parse_mode="Markdown"
    )
    return WAIT_TEAM_NAME

async def got_team_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    tid = ctx.user_data.get("addteam_tid")
    t = db.get(tid)
    if not t:
        await update.message.reply_text("❌ Xatolik.")
        return MAIN
    if name in t["teams"]:
        await update.message.reply_text(f"❌ *{name}* allaqachon bor!", parse_mode="Markdown")
        return WAIT_TEAM_NAME
    t["teams"].append(name)
    t["stats"][name] = init_stat()

    fmt = FORMATS[t["format"]]
    need = fmt["size"]
    have = len(t["teams"])
    status_line = f"✅ {have}/{need} jamoa" if need else f"✅ {have} ta jamoa"

    await update.message.reply_text(
        f"✅ *{name}* qo'shildi!\n{status_line}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Yana qo'shish", callback_data=f"addteam_{tid}")],
            [InlineKeyboardButton("▶️ Boshlash", callback_data=f"begin_{tid}")],
            [InlineKeyboardButton("📋 Turnir menyusi", callback_data=f"tmenu_{tid}")],
        ])
    )
    return MAIN

# ── TURNIRNI BOSHLASH ─────────────────────────────────────────────────────────
async def begin_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = q.data.replace("begin_","")
    t = db.get(tid)
    if t["admin"] != q.from_user.id:
        await q.answer("❌ Faqat admin boshlaydi!", show_alert=True); return MAIN
    if len(t["teams"]) < 2:
        await q.answer("❌ Kamida 2 ta jamoa kerak!", show_alert=True); return MAIN

    fmt = t["format"]
    ftype = FORMATS[fmt]["type"]

    if ftype == "knockout":
        t["bracket"] = make_bracket(t["teams"])
        t["status"] = "playoff"
        msg = f"⚔️ *{t['name']}* boshlandi!\n\n{bracket_text(t)}"
    elif ftype == "groups_knockout":
        # Guruh bosqichi: barcha o'yinlar, keyin top 4 pleyof
        t["matches"] = gen_league_matches(t["teams"])
        # Faqat bir marta o'ynash (round robin bir marta)
        seen = set()
        half = []
        for m in t["matches"]:
            key = tuple(sorted([m["home"],m["away"]]))
            if key not in seen:
                seen.add(key); half.append(m)
        t["matches"] = half
        t["status"] = "group"
        msg = f"🏟 *{t['name']}* guruh bosqichi boshlandi!\n{len(t['matches'])} ta o'yin."
    elif ftype == "league":
        t["matches"] = gen_league_matches(t["teams"])
        t["status"] = "league"
        msg = f"📅 *{t['name']}* davomiy liga boshlandi!\n{len(t['matches'])} ta o'yin (ikki tur)."

    await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=t_menu_kb(tid))
    return MAIN

# ── O'YINLAR ──────────────────────────────────────────────────────────────────
async def matches_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = q.data.replace("matches_","")
    t = db.get(tid)
    matches = t.get("matches",[])
    if not matches:
        await q.edit_message_text("❌ O'yinlar yo'q.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️", callback_data=f"tmenu_{tid}")]]))
        return MAIN

    lines = [f"📅 *{t['name']} — O'YINLAR*\n"]
    for i, m in enumerate(matches):
        icon = "✅" if m["played"] else "⏳"
        if m["played"]:
            lines.append(f"{i+1}. {icon} {m['home']} *{m['hs']}:{m['as']}* {m['away']}")
        else:
            lines.append(f"{i+1}. {icon} {m['home']} 🆚 {m['away']}")

    unplayed = [(i,m) for i,m in enumerate(matches) if not m["played"]]
    buttons = []
    for i,m in unplayed[:8]:
        buttons.append([InlineKeyboardButton(
            f"⚽ {m['home']} vs {m['away']}",
            callback_data=f"mscore_{tid}_{i}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=f"tmenu_{tid}")])
    await q.edit_message_text("\n".join(lines), parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup(buttons))
    return MAIN

# ── NATIJA KIRITISH (guruh/liga) ──────────────────────────────────────────────
async def score_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = q.data.replace("score_","")
    t = db.get(tid)
    # Pleyof yoki guruh/liga
    if t["status"] == "playoff":
        # Bracket o'yinlari
        rounds = t.get("bracket",[])
        if not rounds:
            await q.answer("Bracket yo'q!", show_alert=True); return MAIN
        last = rounds[-1]
        unplayed = [(i,m) for i,m in enumerate(last) if not m["played"] and m["away"]!="BYE"]
        if not unplayed:
            # Keyingi raund
            winners = [m["winner"] for m in last]
            if len(winners)==1:
                t["champion"] = winners[0]; t["status"]="finished"
                await q.edit_message_text(
                    f"🏆 *CHEMPION: {winners[0]}!*\n\nTurnir yakunlandi! 🎉",
                    parse_mode="Markdown")
                return MAIN
            nr = []
            for i in range(0,len(winners),2):
                if i+1<len(winners):
                    nr.append({"home":winners[i],"away":winners[i+1],"played":False,"hs":0,"as":0,"winner":None})
                else:
                    nr.append({"home":winners[i],"away":"BYE","played":True,"hs":1,"as":0,"winner":winners[i]})
            rounds.append(nr)
            unplayed = [(i,m) for i,m in enumerate(nr) if not m["played"] and m["away"]!="BYE"]
        ctx.user_data["score_tid"] = tid
        ctx.user_data["score_type"] = "bracket"
        ctx.user_data["score_round"] = len(rounds)-1
        buttons = []
        for i,m in unplayed:
            buttons.append([InlineKeyboardButton(
                f"⚽ {m['home']} vs {m['away']}",
                callback_data=f"bscore_{tid}_{len(rounds)-1}_{i}"
            )])
        buttons.append([InlineKeyboardButton("⬅️", callback_data=f"tmenu_{tid}")])
        await q.edit_message_text("⚔️ Qaysi o'yin?", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        matches = t.get("matches",[])
        unplayed = [(i,m) for i,m in enumerate(matches) if not m["played"]]
        if not unplayed:
            # Guruh tugadimi?
            if t["status"]=="group":
                top = sorted_teams(t)[:4]
                t["bracket"] = make_bracket(top)
                t["status"]="playoff"
                await q.edit_message_text(
                    f"🏟 Guruh bosqichi tugadi!\n\nTop-4 pleyofga o'tdi:\n"
                    +"\n".join([f"🔸 {tm}" for tm in top])+
                    f"\n\n{bracket_text(t)}",
                    parse_mode="Markdown", reply_markup=t_menu_kb(tid))
            else:
                await q.answer("Barcha o'yinlar o'ynaldi!", show_alert=True)
            return MAIN
        buttons = []
        for i,m in unplayed[:8]:
            buttons.append([InlineKeyboardButton(
                f"⚽ {m['home']} vs {m['away']}",
                callback_data=f"mscore_{tid}_{i}"
            )])
        buttons.append([InlineKeyboardButton("⬅️", callback_data=f"tmenu_{tid}")])
        await q.edit_message_text("⚽ Qaysi o'yin natijasini kiritasiz?",
                                   reply_markup=InlineKeyboardMarkup(buttons))
    return MAIN

async def mscore_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts = q.data.split("_")
    tid = parts[1]; idx = int(parts[2])
    ctx.user_data["mscore_tid"] = tid
    ctx.user_data["mscore_idx"] = idx
    t = db[tid]; m = t["matches"][idx]
    await q.edit_message_text(
        f"⚽ *{m['home']}* vs *{m['away']}*\n\nNatijani kiriting (masalan `2:1`):",
        parse_mode="Markdown"
    )
    return WAIT_SCORE

async def bscore_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts = q.data.split("_")
    tid = parts[1]; rnd = int(parts[2]); idx = int(parts[3])
    ctx.user_data["bscore_tid"] = tid
    ctx.user_data["bscore_rnd"] = rnd
    ctx.user_data["bscore_idx"] = idx
    t = db[tid]; m = t["bracket"][rnd][idx]
    await q.edit_message_text(
        f"⚔️ *{m['home']}* vs *{m['away']}*\n\nNatijani kiriting (masalan `2:0`):",
        parse_mode="Markdown"
    )
    return WAIT_SCORE

async def got_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        hs, as_ = [int(x.strip()) for x in text.split(":")]
    except:
        await update.message.reply_text("❌ Format xato! `2:1` ko'rinishida yozing.", parse_mode="Markdown")
        return WAIT_SCORE

    # Liga/guruh o'yin
    if "mscore_tid" in ctx.user_data:
        tid = ctx.user_data.pop("mscore_tid")
        idx = ctx.user_data.pop("mscore_idx")
        t = db[tid]; m = t["matches"][idx]
        m["played"]=True; m["hs"]=hs; m["as"]=as_
        update_stat(t, m["home"], m["away"], hs, as_)
        extra = ""
        # Liga yangi mavsum?
        if t["status"]=="league":
            all_done = all(m["played"] for m in t["matches"])
            if all_done:
                t["season"]+=1
                t["matches"] = gen_league_matches(t["teams"])
                extra = f"\n\n🔄 {t['season']}-mavsum boshlandi!"

    # Bracket o'yin
    elif "bscore_tid" in ctx.user_data:
        tid = ctx.user_data.pop("bscore_tid")
        rnd = ctx.user_data.pop("bscore_rnd")
        idx = ctx.user_data.pop("bscore_idx")
        t = db[tid]; m = t["bracket"][rnd][idx]
        m["played"]=True; m["hs"]=hs; m["as"]=as_
        m["winner"] = m["home"] if hs>as_ else (m["away"] if as_>hs else m["home"])  # tenglikda uy
        extra = ""
    else:
        await update.message.reply_text("❌ Xatolik."); return MAIN

    await update.message.reply_text(
        f"✅ *{m['home']}* {hs}:{as_} *{m['away']}*{extra}\n\nSaqlandi!",
        parse_mode="Markdown",
        reply_markup=t_menu_kb(tid)
    )
    return MAIN

# ── JADVAL / BRACKET / TEAMS ──────────────────────────────────────────────────
async def stand_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = q.data.replace("stand_","")
    t = db.get(tid)
    await q.edit_message_text(standings_text(t), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data=f"tmenu_{tid}")]]))
    return MAIN

async def bracket_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = q.data.replace("bracket_","")
    t = db.get(tid)
    await q.edit_message_text(bracket_text(t), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️", callback_data=f"tmenu_{tid}")]]))
    return MAIN

async def teams_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = q.data.replace("teams_","")
    t = db.get(tid)
    lines = [f"👥 *{t['name']} — JAMOALAR* ({len(t['teams'])} ta)\n"]
    for i, tm in enumerate(t["teams"],1):
        lines.append(f"{i}. {tm}")
    await q.edit_message_text("\
