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
        kb.add("🚗 Тест ПДД", "📚 Оқу", "🧠 Емтихан")
        kb.add("📊 Статистика", "💰 Сатып алу")
        kb.add("⬅️ Артқа")
    else:
        kb.add("🚗 Тест ПДД", "📚 Обучение", "🧠 Экзамен")
        kb.add("📊 Статистика", "💰 Купить")
        kb.add("⬅️ Назад")
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

# ====== QUESTIONS ======
questions_db = [
    {
        "q_ru": "Какой знак запрещает движение?",
        "q_kz": "Қай белгі қозғалысқа тыйым салады?",
        "img": "images/znak1.jpg",
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
        ],
        "ex_ru": "Этот знак полностью запрещает движение.",
        "ex_kz": "Бұл белгі қозғалысқа толық тыйым салады."
    }
]

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
        "stats": {"correct": 0, "wrong": 0},
        "exam": {"q": 0, "errors": 0}
    })
    save_users()

    await msg.answer("Выбери язык / Тілді таңда:", reply_markup=lang_kb)

# ====== LANGUAGE ======
@dp.message_handler(lambda msg: msg.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_lang(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid]["lang"] = "ru" if "Русский" in msg.text else "kz"
    save_users()

    text = "Выбери режим 👇" if users[uid]["lang"] == "ru" else "Таңдаңыз 👇"
    await msg.answer(text, reply_markup=get_main_kb(users[uid]["lang"]))

# ====== BACK ======
@dp.message_handler(lambda msg: msg.text in ["⬅️ Назад", "⬅️ Артқа"])
async def back(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    users[uid]["mode"] = None
    save_users()

    await msg.answer("Главное меню" if lang == "ru" else "Басты мәзір",
                     reply_markup=get_main_kb(lang))

# ====== STATISTICS ======
@dp.message_handler(lambda msg: "Статистика" in msg.text)
async def stats(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    c = user["stats"]["correct"]
    w = user["stats"]["wrong"]
    total = c + w

    if lang == "kz":
        text = f"📊 Статистика:\nДұрыс: {c}\nҚате: {w}\nБарлығы: {total}"
    else:
        text = f"📊 Статистика:\nПравильно: {c}\nОшибок: {w}\nВсего: {total}"

    await msg.answer(text, reply_markup=get_back_kb(lang))

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
    save_users()

    await msg.answer("Экзамен: 20 вопросов, 3 ошибки = провал" if lang == "ru"
                     else "Емтихан: 20 сұрақ, 3 қате = құлау")

    await send_question(msg)

# ====== QUESTION ======
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    await bot.send_chat_action(msg.chat.id, "typing")

    q = random.choice(questions_db)
    user["last_question"] = q

    if user["mode"] == "exam":
        user["exam"]["q"] += 1

    save_users()

    question = q["q_kz"] if lang == "kz" else q["q_ru"]
    options = q["options_kz"] if lang == "kz" else q["options_ru"]

    text = f"{question}\n\n" + "\n".join(options)

    try:
        await msg.answer_photo(
            photo=open(q["img"], "rb"),
            caption=text,
            reply_markup=get_answers_kb(lang)
        )
    except:
        await msg.answer(text, reply_markup=get_answers_kb(lang))

# ====== ANSWER ======
@dp.message_handler(lambda msg: msg.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    await bot.send_chat_action(msg.chat.id, "typing")

    q = user["last_question"]
    correct = q["correct"]

    if msg.text == correct:
        user["stats"]["correct"] += 1
        text = "✅ Дұрыс!" if lang == "kz" else "✅ Правильно!"
    else:
        user["stats"]["wrong"] += 1
        text = f"❌ Дұрыс жауап: {correct}" if lang == "kz" else f"❌ Ответ: {correct}"

        if user["mode"] == "exam":
            user["exam"]["errors"] += 1

    await msg.answer(text)

    # ===== экзамен логика =====
    if user["mode"] == "exam":
        if user["exam"]["errors"] >= 3:
            await msg.answer("❌ Провал" if lang == "ru" else "❌ Құладың")
            user["mode"] = None
            save_users()
            return

        if user["exam"]["q"] >= 20:
            await msg.answer("🎉 Сдал!" if lang == "ru" else "🎉 Өттің!")
            user["mode"] = None
            save_users()
            return

    save_users()
    await send_question(msg)

# ====== RUN ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
