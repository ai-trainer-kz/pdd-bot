import os
import logging
import json
from datetime import datetime
import re
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ADMIN_ID = 503301815
KASPI = "4400430352720152"

MODEL = "gpt-4o-mini"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

# ===== USERS =====
def load_users():
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()
last_questions = {}

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
            "correct": 0,
            "wrong": 0,
            "exam_count": 0,
            "exam_correct": 0,
            "waiting_answer": False
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

# ===== GPT (FIXED) =====
async def ask_gpt(uid):
    prompt = """
Ты экзаменатор ПДД Казахстан.

Сгенерируй 1 НОВЫЙ вопрос.

Ответ строго в формате:

Вопрос:
...

A) ...
B) ...
C) ...
D) ...

Правильный ответ: A
Объяснение: кратко
"""

    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.8
        )

        text = r.choices[0].message.content

        ans = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
        exp = re.search(r"Объяснение[:\s]*(.*)", text, re.S)

        question_only = re.sub(r"Правильный ответ.*", "", text, flags=re.S)
        question_only = re.sub(r"Объяснение.*", "", question_only, flags=re.S)

        # УБРАЛИ РЕКУРСИЮ
        last_questions[uid] = question_only

        return question_only, ans.group(1) if ans else "A", exp.group(1).strip() if exp else ""

    except Exception as e:
        print("GPT ERROR:", e)
        return "Ошибка генерации вопроса. Попробуй ещё раз.", "A", ""

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)

    await message.answer(
        "🚗 Подготовка к ПДД\n\n"
        "🎁 5 бесплатных вопросов\n"
        "👇 Выбери режим:",
        reply_markup=main_kb()
    )

# ===== MODE =====
@dp.message_handler(lambda m: m.text == "🎯 Тренировка")
async def train(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    u["mode"] = "train"
    u["waiting_answer"] = False

    return await send_question(message, u)

@dp.message_handler(lambda m: m.text == "🧠 Экзамен")
async def exam(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    u["mode"] = "exam"
    u["exam_count"] = 0
    u["exam_correct"] = 0
    u["waiting_answer"] = False

    await message.answer("🧠 Экзамен: 20 вопросов")
    return await send_question(message, u)

# ===== QUESTION =====
async def send_question(message, u):
    if u.get("waiting_answer"):
        return

    if not has_access(u):
        await message.answer("🔒 Нет доступа", reply_markup=main_kb())
        return

    text, ans, exp = await ask_gpt(message.from_user.id)

    u["correct_answer"] = ans
    u["explanation"] = exp
    u["waiting_answer"] = True

    progress = ""
    if u["mode"] == "exam":
        progress = f"\n\n📊 Вопрос {u['exam_count'] + 1}/20"

    await message.answer(text + progress, reply_markup=answer_kb())
    save_users()

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if not u.get("waiting_answer"):
        return

    u["waiting_answer"] = False

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
            percent = int(u["exam_correct"] / 20 * 100)

            msg = f"📊 Результат:\n{u['exam_correct']}/20\n{percent}%\n\n"
            msg += "🔥 Отлично!" if percent >= 80 else "❌ Не сдал"

            await message.answer(msg, reply_markup=main_kb())
            save_users()
            return

    # ЗАДЕРЖКА = убирает "спам/залипание"
    await asyncio.sleep(0.3)

    await send_question(message, u)

# ===== BACK =====
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    u["mode"] = None
    u["waiting_answer"] = False

    save_users()
    await message.answer("🏠 Главное меню", reply_markup=main_kb())

# ===== STATS =====
@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(message: types.Message):
    u = users[str(message.from_user.id)]

    total = u["correct"] + u["wrong"]
    percent = int(u["correct"]/total*100) if total else 0

    await message.answer(
        f"📊 Статистика\n\n"
        f"✅ {u['correct']}\n"
        f"❌ {u['wrong']}\n"
        f"📈 {percent}%"
    )

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
