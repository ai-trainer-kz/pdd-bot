import os
import json
import random
import asyncio
import os
import json
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

TOKEN = os.getenv("TOKEN")
ADMIN_ID = 503301815

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- СОСТОЯНИЯ ----------------

class Quiz(StatesGroup):
    question_index = State()
    score = State()
    free_count = State()
    paid = State()

# ---------------- ЗАГРУЗКА ВОПРОСОВ ----------------

with open("questions.json", encoding="utf-8") as f:
    questions = json.load(f)

# ---------------- КНОПКИ ----------------

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Тренировка", callback_data="train")],
        [InlineKeyboardButton(text="📝 Экзамен", callback_data="exam")]
    ])

def answers():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data="A"),
         InlineKeyboardButton(text="B", callback_data="B")],
        [InlineKeyboardButton(text="C", callback_data="C"),
         InlineKeyboardButton(text="D", callback_data="D")],
        [InlineKeyboardButton(text="📖 Объяснение", callback_data="exp")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить доступ", callback_data="buy")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
    ])

# ---------------- СТАРТ ----------------

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выбери режим:", reply_markup=menu())

# ---------------- РЕЖИМ ----------------

@dp.callback_query(F.data == "train")
async def train(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Quiz.question_index)
    await state.update_data(question_index=0, score=0, free_count=0, paid=False)
    await send_question(callback.message, state)

# ---------------- ВОПРОС ----------------

async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()

    # 🔒 ограничение 5 вопросов
    if data["free_count"] >= 5 and not data["paid"]:
        await message.answer(
            "🔒 Бесплатный лимит закончился\n\nKaspi: 4400430352720152",
            reply_markup=pay_kb()
        )
        return

    index = data["question_index"]

    if index >= len(questions):
        await message.answer(f"🎉 Конец! Баллы: {data['score']}")
        await state.clear()
        return

    q = questions[index]

    text = f"{q['question']}\n\n"
    text += f"A) {q['A']}\nB) {q['B']}\nC) {q['C']}\nD) {q['D']}"

    await message.answer(text, reply_markup=answers())

# ---------------- ОТВЕТ ----------------

@dp.callback_query(F.data.in_(["A", "B", "C", "D"]))
async def answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]
    q = questions[index]

    if callback.data == q["correct"]:
        await callback.message.answer("✅ Верно")
        data["score"] += 1
    else:
        await callback.message.answer("❌ Неверно")

    await state.update_data(
        question_index=index + 1,
        score=data["score"],
        free_count=data["free_count"] + 1
    )

    await send_question(callback.message, state)

# ---------------- ОБЪЯСНЕНИЕ ----------------

@dp.callback_query(F.data == "exp")
async def explanation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    if index < len(questions):
        q = questions[index]
        text = q.get("explanation", "Нет объяснения")
        await callback.message.answer(f"📖 {text}")

# ---------------- ОПЛАТА ----------------

@dp.callback_query(F.data == "buy")
async def buy(callback: CallbackQuery):
    await callback.answer("Оплати по Kaspi 👆")

@dp.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery, state: FSMContext):
    await state.update_data(paid=True)
    await callback.message.answer("✅ Доступ открыт!")
    await send_question(callback.message, state)

# ---------------- АДМИНКА ----------------

@dp.message(Command("give"))
async def give_access(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(message.text.split()[1])
        # тут можно добавить базу, пока просто сообщение
        await bot.send_message(user_id, "🎉 Вам выдан доступ!")
    except:
        await message.answer("Используй: /give user_id")

# ---------------- НАЗАД ----------------

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выбери режим:", reply_markup=menu())

# ---------------- ЗАПУСК ----------------

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
