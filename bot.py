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
        kb.add("💰 Сатып алу")
    else:
        kb.add("🚗 Тест ПДД", "📚 Обучение")
        kb.add("💰 Купить")
    return kb

# ✅ НОВОЕ: универсальная кнопка назад
def get_back_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == "kz":
        kb.add("⬅️ Артқа")
    else:
        kb.add("⬅️ Назад")
    return kb

# ✅ НОВОЕ: ответы с языком
def get_answers_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")

    if lang == "kz":
        kb.add("⬅️ Артқа")
    else:
        kb.add("⬅️ Назад")

    return kb

pay_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Я оплатил / Төледім", callback_data="paid")]
])

# ====== LOCAL QUESTIONS (БАЗА) ======
questions_db = [
    {
        "q_ru": "Какой знак запрещает движение?",
        "q_kz": "Қай белгі қозғалысқа тыйым салады?",
        "img": "images/znak1.jpg",
        "options": ["A", "B", "C", "D"],
        "correct": "C",
        "ex_ru": "Знак 'Движение запрещено' полностью запрещает движение.",
        "ex_kz": "Бұл белгі қозғалысқа толық тыйым салады."
    },
    {
        "q_ru": "Кто имеет преимущество?",
        "q_kz": "Кімнің артықшылығы бар?",
        "img": "images/znak2.jpg",
        "options": ["A", "B", "C", "D"],
        "correct": "A",
        "ex_ru": "Преимущество у водителя на главной дороге.",
        "ex_kz": "Басты жолдағы жүргізушінің артықшылығы бар."
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
        "mode": None
    })
    save_users()

    await msg.answer("Выбери язык / Тілді таңда:", reply_markup=lang_kb)

# ====== LANGUAGE ======
@dp.message_handler(lambda msg: msg.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_lang(msg: types.Message):
    uid = str(msg.from_user.id)

    if "Русский" in msg.text:
        users[uid]["lang"] = "ru"
        text = "🚗 Привет! Я AI-тренер по ПДД KZ\n\nВыбери режим 👇"
    else:
        users[uid]["lang"] = "kz"
        text = "🚗 Сәлем! Мен ПДД бойынша AI жаттықтырушы\n\nТаңдаңыз 👇"

    save_users()

    await msg.answer(text, reply_markup=get_main_kb(users[uid]["lang"]))

# ====== BACK (FIXED) ======
@dp.message_handler(lambda msg: msg.text in ["⬅️ Назад", "⬅️ Артқа"])
async def back(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    users[uid]["mode"] = None
    save_users()

    text = "Главное меню" if lang == "ru" else "Басты мәзір"
    await msg.answer(text, reply_markup=get_main_kb(lang))

# ====== BUY ======
@dp.message_handler(lambda msg: msg.text in ["💰 Купить", "💰 Сатып алу"])
async def buy(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    if lang == "kz":
        text = "Толық қолжетімділік:\n7 күн — 5000 тг\n30 күн — 10000 тг"
    else:
        text = "Полный доступ:\n7 дней — 5000 тг\n30 дней — 10000 тг"

    await msg.answer(text, reply_markup=pay_kb)

@dp.callback_query_handler(lambda c: c.data == "paid")
async def paid(callback: types.CallbackQuery):
    await callback.message.answer("Отправь чек администратору / Чекті админге жібер")
    await callback.answer()

# ====== TEST MODE ======
@dp.message_handler(lambda msg: "Тест ПДД" in msg.text)
async def test(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["mode"] = "test"
    save_users()
    await send_question(msg)

# ====== LEARNING MODE (УЛУЧШЕН) ======
@dp.message_handler(lambda msg: "Обучение" in msg.text or "Оқу" in msg.text)
async def learning(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    users[uid]["mode"] = "learn"
    save_users()

    if lang == "kz":
        prompt = "Қазақстан ПДД толық әрі қарапайым тілмен түсіндір, мысалдармен"
    else:
        prompt = "Объясни ПДД Казахстана простым языком с примерами"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    await msg.answer(response.choices[0].message.content, reply_markup=get_back_kb(lang))

# ====== QUESTION ======
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    if not is_premium(uid) and user["free_used"] >= FREE_LIMIT:
        text = "Лимит закончился. Купи доступ" if lang == "ru" else "Лимит бітті. Сатып ал"
        await msg.answer(text)
        return

    # ✅ Берем из базы
    q = random.choice(questions_db)

    user["last_question"] = q

    if not is_premium(uid):
        user["free_used"] += 1

    save_users()

    text = q["q_kz"] if lang == "kz" else q["q_ru"]

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
    user = users.get(uid)

    if not user or "last_question" not in user:
        return

    lang = user["lang"]
    q = user["last_question"]

    correct = q["correct"]
    explanation = q["ex_kz"] if lang == "kz" else q["ex_ru"]

    if msg.text == correct:
        text = "✅ Дұрыс!\n\n" + explanation if lang == "kz" else "✅ Правильно!\n\n" + explanation
    else:
        text = f"❌ Қате. Дұрыс жауап: {correct}\n\n{explanation}" if lang == "kz" else f"❌ Неправильно. Ответ: {correct}\n\n{explanation}"

    await msg.answer(text)

    await send_question(msg)

# ====== RUN ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
