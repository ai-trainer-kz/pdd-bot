import os
import logging
import json
import random
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "users.json"

# ====== DATA ======
def load_users():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()

# ====== KEYBOARDS ======
lang_kb = ReplyKeyboardMarkup(resize_keyboard=True)
lang_kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")

def get_main_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == "kz":
        kb.add("🚗 Тест ПДД", "📚 Оқу", "🧠 Емтихан")
        kb.add("📊 Статистика")
    else:
        kb.add("🚗 Тест ПДД", "📚 Обучение", "🧠 Экзамен")
        kb.add("📊 Статистика")
    return kb

def get_back_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅️ Артқа" if lang == "kz" else "⬅️ Назад")
    return kb

def get_answers_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Артқа" if lang == "kz" else "⬅️ Назад")
    return kb

# ====== QUESTIONS ======
questions_db = [
    {
        "q_ru": "Какой знак запрещает движение?",
        "q_kz": "Қай белгі қозғалысқа тыйым салады?",
        "correct": "C",
        "options_ru": [
            "A) Уступить дорогу",
            "B) Стоянка запрещена",
            "C) Движение запрещено",
            "D) Ограничение скорости"
        ],
        "options_kz": [
            "A) Жол беру",
            "B) Тұраққа тыйым",
            "C) Қозғалысқа тыйым",
            "D) Жылдамдық шектеуі"
        ]
    }
]

# ====== START ======
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid] = users.get(uid, {
        "lang": None,
        "mode": None,
        "stats": {"correct": 0, "wrong": 0},
        "exam": {"q": 0, "errors": 0},
        "last_q": None,
        "exam_active": False
    })
    save_users()

    await msg.answer("Выбери язык / Тілді таңда:", reply_markup=lang_kb)

# ====== LANGUAGE ======
@dp.message_handler(lambda msg: msg.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_lang(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["lang"] = "ru" if "Русский" in msg.text else "kz"
    save_users()

    await msg.answer("Выбери режим 👇" if users[uid]["lang"] == "ru" else "Таңдаңыз 👇",
                     reply_markup=get_main_kb(users[uid]["lang"]))

# ====== BACK ======
@dp.message_handler(lambda msg: msg.text in ["⬅️ Назад", "⬅️ Артқа"])
async def back(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    users[uid]["mode"] = None
    users[uid]["exam_active"] = False
    save_users()

    await msg.answer("Главное меню" if lang == "ru" else "Басты мәзір",
                     reply_markup=get_main_kb(lang))

# ====== TYPING LOOP ======
async def typing_loop(chat_id):
    while True:
        await bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(2)

# ====== TEST ======
@dp.message_handler(lambda msg: "Тест ПДД" in msg.text)
async def test(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["mode"] = "test"
    save_users()
    await send_question(msg)

# ====== EXAM ======
@dp.message_handler(lambda msg: "Экзамен" in msg.text or "Емтихан" in msg.text)
async def exam(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    users[uid]["mode"] = "exam"
    users[uid]["exam"] = {"q": 0, "errors": 0}
    users[uid]["exam_active"] = True
    save_users()

    await msg.answer("Экзамен: 20 вопросов, 3 ошибки = провал" if lang == "ru"
                     else "Емтихан: 20 сұрақ, 3 қате = құлау")

    await send_question(msg)

# ====== ОБУЧЕНИЕ ======
@dp.message_handler(lambda msg: "Обучение" in msg.text or "Оқу" in msg.text)
async def learning(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    users[uid]["mode"] = "learn"
    save_users()

    await msg.answer("Напиши вопрос 👇" if lang == "ru" else "Сұрақ жаз 👇",
                     reply_markup=get_back_kb(lang))

# ====== AI ======
@dp.message_handler(lambda msg: True)
async def ai_handler(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)

    if not user or user.get("mode") != "learn":
        return

    task = asyncio.create_task(typing_loop(msg.chat.id))

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": msg.text}]
        )

        await msg.answer(response.choices[0].message.content)

    finally:
        task.cancel()

# ====== QUESTION ======
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    # ❗ защита от одинакового вопроса
    while True:
        q = random.choice(questions_db)
        if q != user.get("last_q"):
            break

    user["last_q"] = q

    if user["mode"] == "exam":
        user["exam"]["q"] += 1

    save_users()

    question = q["q_kz"] if lang == "kz" else q["q_ru"]
    options = q["options_kz"] if lang == "kz" else q["options_ru"]

    text = f"{question}\n\n" + "\n".join(options)

    await msg.answer(text, reply_markup=get_answers_kb(lang))

# ====== ANSWER ======
@dp.message_handler(lambda msg: msg.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    if user.get("exam_active") is False and user["mode"] == "exam":
        return

    q = user["last_q"]
    correct = q["correct"]

    if msg.text == correct:
        user["stats"]["correct"] += 1
        text = "✅ Дұрыс!" if lang == "kz" else "✅ Правильно!"
    else:
        user["stats"]["wrong"] += 1
        text = f"❌ {correct}"

        if user["mode"] == "exam":
            user["exam"]["errors"] += 1

    await msg.answer(text)

    # ❗ СТОП ЭКЗАМЕНА
    if user["mode"] == "exam":
        if user["exam"]["errors"] >= 3:
            user["exam_active"] = False
            await msg.answer("❌ Провал" if lang == "ru" else "❌ Құладың")
            return

        if user["exam"]["q"] >= 20:
            user["exam_active"] = False
            await msg.answer("🎉 Сдал!" if lang == "ru" else "🎉 Өттің!")
            return

    save_users()
    await send_question(msg)

# ====== RUN ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
