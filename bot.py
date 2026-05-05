import os
import random
import asyncio
import sqlite3
import time
import json
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 503301815

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================= БАЗА =================

conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    access_until INTEGER DEFAULT 0,
    exams_passed INTEGER DEFAULT 0,
    exams_failed INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS mistakes (
    user_id INTEGER,
    topic TEXT,
    count INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, topic)
)
""")

conn.commit()

# ================= ВОПРОСЫ =================

questions = [
    {"q":"Какой сигнал светофора разрешает движение?",
     "options":["Красный","Желтый","Зеленый","Мигающий красный"],
     "correct":2,
     "explanation":"Зеленый сигнал разрешает движение."},

    {"q":"Максимальная скорость в городе?",
     "options":["40","60","80","100"],
     "correct":1,
     "explanation":"60 км/ч"},

    {"q":"Кто имеет преимущество на перекрестке?",
     "options":["Кто быстрее","По договоренности","По ПДД","Кто сигналит"],
     "correct":2,
     "explanation":"Приоритет по ПДД"}
]

# ================= STATE =================

class QuizState(StatesGroup):
    data = State()

# ================= AI =================

TEMPLATES = [
    "Что верно?",
    "Как правильно поступить?",
    "Выберите вариант:",
]

def generate_ai_question():
    base = random.choice(questions)
    q = f"{random.choice(TEMPLATES)} {base['q']}"

    options = base["options"][:]
    correct_text = options[base["correct"]]
    random.shuffle(options)

    return {
        "q": q,
        "options": options,
        "correct": options.index(correct_text),
        "explanation": base["explanation"],
        "topic": base["q"]
    }

async def generate_gpt_question():
    if not OPENAI_API_KEY:
        return generate_ai_question()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{
                        "role": "user",
                        "content": "Сгенерируй вопрос ПДД Казахстан JSON"
                    }]
                }
            ) as resp:
                data = await resp.json()

        text = data["choices"][0]["message"]["content"]
        return json.loads(text)

    except:
        return generate_ai_question()

def get_user_level(user_id):
    cursor.execute("SELECT exams_passed FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

# ================= UTILS =================

def has_access(user_id):
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] > int(time.time())

# ================= КНОПКИ =================

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Тренировка", callback_data="training")],
        [InlineKeyboardButton(text="🎯 Экзамен", callback_data="exam")]
    ])

def answers_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data="ans_0"),
         InlineKeyboardButton(text="B", callback_data="ans_1")],
        [InlineKeyboardButton(text="C", callback_data="ans_2"),
         InlineKeyboardButton(text="D", callback_data="ans_3")]
    ])

def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить доступ", callback_data="buy")]
    ])

# ================= START =================

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, 0, 0, 0)",
                   (message.from_user.id, message.from_user.username))
    conn.commit()

    await state.clear()
    await message.answer("🚗 Выбери режим:", reply_markup=menu_kb())

# ================= РЕЖИМЫ =================

@dp.callback_query(F.data=="training")
async def training(callback: CallbackQuery, state: FSMContext):
    qs = random.sample(questions, len(questions))

    # 🔥 добавляем GPT вопросы
    for _ in range(5):
        qs.append(await generate_gpt_question())

    await state.set_state(QuizState.data)
    await state.update_data(qs=qs, index=0, score=0, mistakes=0)

    await send_question(callback.message, state)

@dp.callback_query(F.data=="exam")
async def exam(callback: CallbackQuery, state: FSMContext):
    if not has_access(callback.from_user.id):
        await callback.message.answer("🔒 Нужна оплата", reply_markup=pay_kb())
        return

    qs = random.sample(questions, len(questions))

    for _ in range(10):
        qs.append(await generate_gpt_question())

    await state.set_state(QuizState.data)
    await state.update_data(qs=qs, index=0, score=0, mistakes=0)

    await send_question(callback.message, state)

# ================= ВОПРОС =================

async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()
    qs = data["qs"]
    i = data["index"]

    if i >= len(qs):
        await message.answer(f"🎉 Конец! Баллы: {data['score']}")
        await state.clear()
        return

    q = qs[i]

    text = f"{q['q']}\n\n"
    for idx, opt in enumerate(q["options"]):
        text += f"{chr(65+idx)}) {opt}\n"

    await message.answer(text, reply_markup=answers_kb())

# ================= ОТВЕТ =================

@dp.callback_query(F.data.startswith("ans_"))
async def answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    qs = data["qs"]
    i = data["index"]

    q = qs[i]
    user = int(callback.data.split("_")[1])

    if user == q["correct"]:
        data["score"] += 1
        await callback.message.answer("✅")
    else:
        data["mistakes"] += 1
        await callback.message.answer("❌")

    await state.update_data(index=i+1, score=data["score"], mistakes=data["mistakes"])
    await send_question(callback.message, state)

# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
