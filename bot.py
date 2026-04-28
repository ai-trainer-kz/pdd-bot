import json
import random
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ====== Загрузка вопросов ======
with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

# ====== Хранилище пользователей ======
users = {}

# ====== Клавиатуры ======
lang_kb = ReplyKeyboardMarkup(resize_keyboard=True)
lang_kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")

menu_kb_ru = ReplyKeyboardMarkup(resize_keyboard=True)
menu_kb_ru.add("🚗 Тест", "📚 Обучение")

menu_kb_kz = ReplyKeyboardMarkup(resize_keyboard=True)
menu_kb_kz.add("🚗 Тест", "📚 Оқу")

# ====== Старт ======
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    users[msg.from_user.id] = {
        "lang": None,
        "score": 0,
        "q_index": 0
    }

    await msg.answer("Выбери язык / Тілді таңда:", reply_markup=lang_kb)

# ====== Выбор языка ======
@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_language(msg: types.Message):
    user = users[msg.from_user.id]

    if "Русский" in msg.text:
        user["lang"] = "ru"
        await msg.answer("Выбери режим:", reply_markup=menu_kb_ru)
    else:
        user["lang"] = "kz"
        await msg.answer("Режимді таңда:", reply_markup=menu_kb_kz)

# ====== Запуск теста ======
@dp.message_handler(lambda m: "Тест" in m.text or "🚗" in m.text)
async def start_test(msg: types.Message):
    user = users[msg.from_user.id]
    user["score"] = 0
    user["q_index"] = 0
    random.shuffle(questions)

    await send_question(msg)

# ====== Отправка вопроса ======
async def send_question(msg):
    user = users[msg.from_user.id]

    if user["q_index"] >= len(questions):
        await msg.answer(f"✅ Тест завершен!\nРезультат: {user['score']}/{len(questions)}")
        return

    q = questions[user["q_index"]]

    if user["lang"] == "ru":
        text = q["q_ru"] + "\n\n" + "\n".join(q["options_ru"])
    else:
        text = q["q_kz"] + "\n\n" + "\n".join(q["options_kz"])

    await msg.answer(text)

# ====== Ответ пользователя ======
@dp.message_handler(lambda m: m.text and m.text[0] in ["A", "B", "C", "D"])
async def handle_answer(msg: types.Message):
    user = users[msg.from_user.id]
    q = questions[user["q_index"]]

    answer = msg.text[0]

    if answer == q["correct"]:
        user["score"] += 1
        await msg.answer("✅ Правильно!" if user["lang"] == "ru" else "✅ Дұрыс!")
    else:
        await msg.answer("❌ Неправильно!" if user["lang"] == "ru" else "❌ Қате!")

    # объяснение
    if user["lang"] == "ru":
        await msg.answer(q["ex_ru"])
    else:
        await msg.answer(q["ex_kz"])

    user["q_index"] += 1
    await send_question(msg)

# ====== Обучение ======
@dp.message_handler(lambda m: "Обучение" in m.text or "Оқу" in m.text)
async def learning(msg: types.Message):
    user = users[msg.from_user.id]

    q = random.choice(questions)

    if user["lang"] == "ru":
        text = q["q_ru"] + "\n\n" + q["ex_ru"]
    else:
        text = q["q_kz"] + "\n\n" + q["ex_kz"]

    await msg.answer(text)

# ====== Запуск ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
