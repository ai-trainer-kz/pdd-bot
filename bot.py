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
            "step": "menu",
            "lang": "ru",
            "mode": None,
            "topic": None,
            "level": None,
            "correct": 0,
            "wrong": 0,
            "total_correct": 0,
            "total_wrong": 0,
            "exam_q": 0,
            "premium_until": None,
            "correct_answer": None
        }
        save_users()

def has_access(u):
    try:
        return u["premium_until"] and datetime.now() < datetime.fromisoformat(u["premium_until"])
    except:
        return False

# ===== UI =====
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎯 Тренировка", "🧠 Экзамен")
    kb.add("📊 Статистика", "🌐 Язык")
    kb.add("💳 Купить доступ")
    return kb

def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")
    kb.add("⬅️ Назад")
    return kb

def topic_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🚸 Знаки", "🛣 Разметка")
    kb.add("🚦 Перекрестки", "🚗 Общие")
    kb.add("⬅️ Назад")
    return kb

def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Легкий", "🟡 Средний", "🔴 Сложный")
    kb.add("⬅️ Назад")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Назад")
    return kb

def pay_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Оплатил")
    kb.add("⬅️ Назад")
    return kb

# ===== GPT =====
def system_prompt(u):
    lang = "на русском" if u["lang"] == "ru" else "қазақ тілінде"

    return f"""
Ты строгий экзаменатор ПДД. Отвечай {lang}.

Тема: {u['topic']}
Уровень: {u['level']}

Сделай 1 качественный вопрос как на экзамене.

Формат строго:

Ситуация:
...

Вопрос:
...

A) ...
B) ...
C) ...
D) ...

Правильный ответ:
A
"""

def ask_gpt(u):
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt(u)},
                {"role": "user", "content": "Сгенерируй вопрос"}
            ]
        )
        return resp.choices[0].message.content
    except Exception as e:
        return "Ошибка генерации вопроса, попробуй снова."

# ===== IMAGE =====
def generate_image(prompt):
    try:
        img = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )
        return img.data[0].url
    except:
        return None

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    await message.answer("🚗 AI ПДД Инструктор", reply_markup=main_kb())

# ===== LANGUAGE =====
@dp.message_handler(lambda m: m.text == "🌐 Язык")
async def choose_lang(message: types.Message):
    await message.answer("Выбери язык", reply_markup=lang_kb())

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский","🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    u = users[str(message.from_user.id)]
    u["lang"] = "ru" if "Рус" in message.text else "kz"
    save_users()
    await message.answer("✅ Язык обновлен", reply_markup=main_kb())

# ===== BUY =====
@dp.message_handler(lambda m: m.text == "💳 Купить доступ")
async def buy(message: types.Message):
    await message.answer(
        f"💳 Оплата Kaspi\n{KASPI}\n\nПосле оплаты отправь чек",
        reply_markup=pay_kb()
    )

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_receipt(message: types.Message):
    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"Оплата от {message.from_user.id}",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("Выдать доступ", callback_data=f"give_{message.from_user.id}")
        )
    )
    await message.answer("⏳ Чек отправлен на проверку")

@dp.callback_query_handler(lambda c: c.data.startswith("give_"))
async def give_access(callback: types.CallbackQuery):
    user_id = callback.data.split("_")[1]

    users[user_id]["premium_until"] = (datetime.now() + timedelta(days=30)).isoformat()
    save_users()

    await bot.send_message(user_id, "🔥 Доступ активирован на 30 дней")
    await callback.answer("OK")

# ===== MODE =====
@dp.message_handler(lambda m: m.text in ["🎯 Тренировка","🧠 Экзамен"])
async def mode(message: types.Message):
    u = users[str(message.from_user.id)]

    if not has_access(u):
        await message.answer("❌ Нужен доступ", reply_markup=pay_kb())
        return

    u["mode"] = message.text
    u["step"] = "topic"
    save_users()

    await message.answer("Выбери тему:", reply_markup=topic_kb())

# ===== TOPIC =====
@dp.message_handler(lambda m: m.text in ["🚸 Знаки","🛣 Разметка","🚦 Перекрестки","🚗 Общие"])
async def topic(message: types.Message):
    u = users[str(message.from_user.id)]
    u["topic"] = message.text
    u["step"] = "level"
    save_users()

    await message.answer("Выбери уровень:", reply_markup=level_kb())

# ===== LEVEL =====
@dp.message_handler(lambda m: m.text in ["🟢 Легкий","🟡 Средний","🔴 Сложный"])
async def level(message: types.Message):
    u = users[str(message.from_user.id)]

    u["level"] = message.text
    u["correct"] = 0
    u["wrong"] = 0
    u["exam_q"] = 0
    u["step"] = "test"

    save_users()

    await send_question(message, u)

# ===== QUESTION =====
async def send_question(message, u):
    text = ask_gpt(u)

    match = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
    if match:
        u["correct_answer"] = match.group(1)

    clean = re.sub(r"Правильный ответ[:\s]*[ABCD]", "", text)

    img_url = generate_image(clean[:300])

    if img_url:
        await bot.send_photo(message.chat.id, img_url, caption=clean, reply_markup=answer_kb())
    else:
        await message.answer(clean, reply_markup=answer_kb())

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if not u.get("correct_answer"):
        await message.answer("Ошибка, начни заново")
        return

    if message.text == u["correct_answer"]:
        u["correct"] += 1
        u["total_correct"] += 1
        res = "✅ Верно"
    else:
        u["wrong"] += 1
        u["total_wrong"] += 1
        res = f"❌ Неверно. Ответ: {u['correct_answer']}"

    await message.answer(res)

    if u["mode"] == "🧠 Экзамен":
        u["exam_q"] += 1
        if u["exam_q"] >= 20:
            await message.answer(
                f"🏁 Экзамен завершен\n\n"
                f"✅ {u['correct']}\n❌ {u['wrong']}"
            )
            u["step"] = "menu"
            save_users()
            return

    save_users()
    await send_question(message, u)

# ===== STATS =====
@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(message: types.Message):
    u = users[str(message.from_user.id)]

    await message.answer(
        f"📊 Статистика:\n\n"
        f"✅ Правильно: {u['total_correct']}\n"
        f"❌ Ошибки: {u['total_wrong']}"
    )

# ===== BACK =====
@dp.message_handler(lambda m: "Назад" in m.text)
async def back(message: types.Message):
    await message.answer("Меню", reply_markup=main_kb())

# ===== RUN =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
