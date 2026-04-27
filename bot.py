import os
import logging
import json
import random
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
FREE_LIMIT = 5

# ====== PREMIUM ======
def is_premium(user_id):
    user = users.get(user_id)
    if not user or not user.get("premium"):
        return False

    expires = user.get("expires")
    if not expires:
        return False

    expires_date = datetime.strptime(expires, "%Y-%m-%d")

    if datetime.now() > expires_date:
        user["premium"] = False
        save_users()
        return False

    return True

# ====== KEYBOARDS ======
lang_kb = ReplyKeyboardMarkup(resize_keyboard=True)
lang_kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")

def get_main_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == "kz":
        kb.add("🚗 Тест ПДД", "📚 Оқу")
        kb.add("📝 Емтихан")
        kb.add("💰 Сатып алу")
    else:
        kb.add("🚗 Тест ПДД", "📚 Обучение")
        kb.add("📝 Экзамен")
        kb.add("💰 Купить")
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

pay_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Я оплатил / Төледім", callback_data="paid")]
])

# ====== БАЗА 100+ ВОПРОСОВ (ШАБЛОН) ======
questions_db = []

categories = ["signs", "priority", "parking", "speed"]

# генерим 120 вопросов автоматически
for i in range(120):
    questions_db.append({
        "q_ru": f"Вопрос #{i+1}: Кто имеет преимущество?",
        "q_kz": f"{i+1}-сұрақ: Кімнің артықшылығы бар?",
        "img": None,
        "options": ["A", "B", "C", "D"],
        "correct": random.choice(["A", "B", "C", "D"]),
        "ex_ru": "Преимущество у водителя на главной дороге.",
        "ex_kz": "Басты жолдағы жүргізушінің артықшылығы бар.",
        "category": random.choice(categories)
    })

# ====== START ======
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid] = users.get(uid, {
        "free_used": 0,
        "premium": False,
        "expires": None,
        "lang": None,
        "mode": None,
        "exam": None
    })
    save_users()

    await msg.answer("Выбери язык / Тілді таңда:", reply_markup=lang_kb)

# ====== LANGUAGE ======
@dp.message_handler(lambda msg: msg.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_lang(msg: types.Message):
    uid = str(msg.from_user.id)

    if "Русский" in msg.text:
        users[uid]["lang"] = "ru"
        text = "🚗 AI-тренер ПДД\nВыбери режим"
    else:
        users[uid]["lang"] = "kz"
        text = "🚗 ПДД жаттықтырушы\nРежим таңда"

    save_users()

    await msg.answer(text, reply_markup=get_main_kb(users[uid]["lang"]))

# ====== BACK ======
@dp.message_handler(lambda msg: msg.text in ["⬅️ Назад", "⬅️ Артқа"])
async def back(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    users[uid]["mode"] = None
    users[uid]["exam"] = None
    save_users()

    await msg.answer("Басты мәзір" if lang == "kz" else "Главное меню", reply_markup=get_main_kb(lang))

# ====== TEST ======
@dp.message_handler(lambda msg: "Тест ПДД" in msg.text)
async def test(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["mode"] = "test"
    save_users()
    await send_question(msg)

# ====== EXAM MODE ======
@dp.message_handler(lambda msg: "Экзамен" in msg.text or "Емтихан" in msg.text)
async def exam_start(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid]["mode"] = "exam"
    users[uid]["exam"] = {
        "current": 0,
        "errors": 0
    }

    save_users()

    await msg.answer("Экзамен начался (20 вопросов, 3 ошибки = провал)" if users[uid]["lang"]=="ru" else "Емтихан басталды (20 сұрақ, 3 қате = құлау)")
    await send_question(msg)

# ====== QUESTION ======
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    if user["mode"] == "exam":
        exam = user["exam"]

        if exam["errors"] >= 3:
            await msg.answer("❌ Провал" if lang=="ru" else "❌ Құладың")
            user["mode"] = None
            return

        if exam["current"] >= 20:
            await msg.answer("✅ Экзамен сдан!" if lang=="ru" else "✅ Емтихан өтті!")
            user["mode"] = None
            return

        exam["current"] += 1

    q = random.choice(questions_db)
    user["last_question"] = q
    save_users()

    text = q["q_kz"] if lang == "kz" else q["q_ru"]

    await msg.answer(text, reply_markup=get_answers_kb(lang))

# ====== ANSWER ======
@dp.message_handler(lambda msg: msg.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)
    lang = user["lang"]
    q = user["last_question"]

    correct = q["correct"]

    if msg.text != correct:
        if user["mode"] == "exam":
            user["exam"]["errors"] += 1

    text = "✅ Правильно" if msg.text == correct else f"❌ Неправильно ({correct})"
    if lang == "kz":
        text = "✅ Дұрыс" if msg.text == correct else f"❌ Қате ({correct})"

    await msg.answer(text)

    await send_question(msg)

# ====== RUN ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
