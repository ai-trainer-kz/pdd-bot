import os
import logging
import json
from datetime import datetime, timedelta
import re

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ADMIN_ID = 8398266271
KASPI = "4400430352720152"

MODEL = "gpt-4o-mini"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

users = {}

# ===== SAVE =====
def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_users():
    global users
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        users = {}

# ===== USER =====
def ensure_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "mode": None,
            "correct_answer": None,
            "explanation": "",
            "free_limit": 5,
            "used_free": 0,
            "premium_until": None,
            "plan": None,
            "correct": 0,
            "wrong": 0,
            "exam_count": 0,
            "exam_correct": 0
        }
        save_users()

def has_access(u):
    try:
        if u["premium_until"] and datetime.now() < datetime.fromisoformat(u["premium_until"]):
            return True
    except:
        pass
    return u["used_free"] < u["free_limit"]

# ===== UI =====
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎯 Тренировка", "🧠 Экзамен")
    kb.add("📊 Статистика", "💳 Купить доступ")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add("⬅️ Назад")
    return kb

# ===== GPT =====
def ask_gpt():
    prompt = """
Сделай экзаменационный вопрос ПДД Казахстан.

Формат:
Вопрос:
...

A) ...
B) ...
C) ...
D) ...

Правильный ответ: A
Объяснение: кратко
"""

    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role":"user","content":prompt}]
    )

    text = r.choices[0].message.content

    ans = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
    exp = re.search(r"Объяснение[:\s]*(.*)", text, re.S)

    return text, ans.group(1) if ans else "A", exp.group(1).strip() if exp else ""

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)

    await message.answer(
        "🚗 Подготовка к ПДД\n\n"
        "🎁 5 бесплатных вопросов\n"
        "📊 Проверь свой уровень\n"
        "🚀 Сдай экзамен с первого раза\n\n"
        "👇 Выбери режим:",
        reply_markup=main_kb()
    )

# ===== MODE =====
@dp.message_handler(lambda m: m.text == "🎯 Тренировка")
async def train(message: types.Message):
    u = users[str(message.from_user.id)]
    u["mode"] = "train"

    if not has_access(u):
        await message.answer("🔒 Купи доступ")
        return

    await send_question(message, u)

@dp.message_handler(lambda m: m.text == "🧠 Экзамен")
async def exam(message: types.Message):
    u = users[str(message.from_user.id)]
    u["mode"] = "exam"
    u["exam_count"] = 0
    u["exam_correct"] = 0

    await message.answer("🧠 Экзамен: 20 вопросов")
    await send_question(message, u)

# ===== BUY =====
@dp.message_handler(lambda m: m.text == "💳 Купить доступ")
async def buy(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней — 5000₸")
    kb.add("30 дней — 10000₸")

    await message.answer("💰 Выбери тариф:", reply_markup=kb)

@dp.message_handler(lambda m: "дней" in m.text)
async def plan(message: types.Message):
    u = users[str(message.from_user.id)]

    u["plan"] = 7 if "7" in message.text else 30
    save_users()

    await message.answer(
        f"💳 Kaspi: {KASPI}\n📦 {u['plan']} дней\n📸 Отправь чек"
    )

# ===== PHOTO =====
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def receipt(message: types.Message):
    user = message.from_user
    u = users[str(user.id)]

    try:
        await bot.send_photo(
            ADMIN_ID,
            message.photo[-1].file_id,
            caption=f"💰 Оплата\nID: {user.id}\nТариф: {u.get('plan')}",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Дать доступ", callback_data=f"give_{user.id}")
            )
        )
        print("SUCCESS SEND")
    except Exception as e:
        print("ERROR:", e)

    await message.answer("⏳ Отправлено админу")

# ===== GIVE ACCESS =====
@dp.callback_query_handler(lambda c: c.data.startswith("give_"))
async def give(callback: types.CallbackQuery):
    uid = callback.data.split("_")[1]
    days = users[uid].get("plan", 7)

    users[uid]["premium_until"] = (datetime.now()+timedelta(days=days)).isoformat()
    save_users()

    await bot.send_message(uid, "🔥 Доступ открыт!")
    await callback.answer("OK")

# ===== QUESTION =====
async def send_question(message, u):
    text, ans, exp = ask_gpt()

    clean = re.sub(r"Правильный ответ.*", "", text, flags=re.S)
    clean = re.sub(r"Объяснение.*", "", clean, flags=re.S)

    u["correct_answer"] = ans
    u["explanation"] = exp

    await message.answer(clean, reply_markup=answer_kb())
    save_users()

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if message.text == u["correct_answer"]:
        u["correct"] += 1
        if u["mode"] == "exam":
            u["exam_correct"] += 1
        await message.answer("✅ Верно")
    else:
        u["wrong"] += 1
        await message.answer(f"❌ Неверно\nОтвет: {u['correct_answer']}")

    if u["explanation"]:
        await message.answer(f"📘 {u['explanation'][:200]}")

    if u["mode"] == "exam":
        u["exam_count"] += 1
        if u["exam_count"] >= 20:
            percent = int(u["exam_correct"]/20*100)
            status = "✅ СДАЛ" if percent >= 80 else "❌ НЕ СДАЛ"

            await message.answer(
                f"📊 Результат:\n{u['exam_correct']}/20\n{percent}%\n{status}"
            )
            return

    await send_question(message, u)

# ===== STATS =====
@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(message: types.Message):
    u = users[str(message.from_user.id)]

    total = u["correct"] + u["wrong"]
    percent = int(u["correct"]/total*100) if total else 0

    level = "Новичок"
    if percent > 50:
        level = "Средний"
    if percent > 80:
        level = "Готов к экзамену"

    await message.answer(
        f"📊 Статистика\n\n"
        f"✅ Правильно: {u['correct']}\n"
        f"❌ Ошибки: {u['wrong']}\n"
        f"📈 Процент: {percent}%\n"
        f"🏆 Уровень: {level}"
    )

# ===== RUN =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
