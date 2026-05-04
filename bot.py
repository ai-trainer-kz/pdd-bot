import os
import json
import random
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# -------------------- СОСТОЯНИЯ --------------------

class QuizState(StatesGroup):
    mode = State()
    question_index = State()
    score = State()
    paid = State()

# -------------------- ВОПРОСЫ --------------------

questions = [
    {
        "q": "Какой сигнал светофора разрешает движение?",
        "options": ["Красный", "Желтый", "Зеленый", "Мигающий красный"],
        "correct": 2,
        "explanation": "Зеленый сигнал разрешает движение."
    },
    {
        "q": "Когда включается ближний свет?",
        "options": ["Только ночью", "Всегда при движении", "Только в городе", "По желанию"],
        "correct": 1,
        "explanation": "По ПДД ближний свет должен быть включен всегда."
    },
    {
        "q": "Максимальная скорость в городе?",
        "options": ["40", "60", "80", "100"],
        "correct": 1,
        "explanation": "В большинстве случаев — 60 км/ч."
    }
]

# -------------------- КНОПКИ --------------------

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Тренировка", callback_data="training")],
        [InlineKeyboardButton(text="📝 Экзамен", callback_data="exam")]
    ])

def answers_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data="ans_0"),
         InlineKeyboardButton(text="B", callback_data="ans_1")],
        [InlineKeyboardButton(text="C", callback_data="ans_2"),
         InlineKeyboardButton(text="D", callback_data="ans_3")],
        [InlineKeyboardButton(text="📖 Объяснение", callback_data="explain")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить доступ", callback_data="buy")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
    ])

# -------------------- СТАРТ --------------------

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выбери режим:", reply_markup=menu_kb())

# -------------------- ВЫБОР РЕЖИМА --------------------

@dp.callback_query(F.data == "training")
async def training(callback: CallbackQuery, state: FSMContext):
    await state.set_state(QuizState.question_index)
    await state.update_data(question_index=0, score=0, mode="training", paid=True)
    await send_question(callback.message, state)

@dp.callback_query(F.data == "exam")
async def exam(callback: CallbackQuery, state: FSMContext):
    # ПРОВЕРКА ОПЛАТЫ (пока фейк)
    paid = False

    if not paid:
        await callback.message.answer(
            "🔒 Доступ ограничен\n\nKaspi: 4400430352720152",
            reply_markup=pay_kb()
        )
        return

    await state.set_state(QuizState.question_index)
    await state.update_data(question_index=0, score=0, mode="exam", paid=True)
    await send_question(callback.message, state)

# -------------------- ОПЛАТА --------------------

@dp.callback_query(F.data == "buy")
async def buy(callback: CallbackQuery):
    await callback.answer("Оплати по Kaspi выше 👆")

@dp.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery, state: FSMContext):
    await state.update_data(paid=True)
    await callback.message.answer("✅ Оплата принята (тест)")
    await training(callback, state)

# -------------------- ВОПРОС --------------------

async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    if index >= len(questions):
        await message.answer(f"🎉 Конец! Баллы: {data['score']}")
        await state.clear()
        return

    q = questions[index]

    text = f"{q['q']}\n\n"
    for i, opt in enumerate(q["options"]):
        text += f"{chr(65+i)}) {opt}\n"

    await message.answer(text, reply_markup=answers_kb())

# -------------------- ОТВЕТ --------------------

@dp.callback_query(F.data.startswith("ans_"))
async def answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]
    q = questions[index]

    user_answer = int(callback.data.split("_")[1])

    if user_answer == q["correct"]:
        await callback.message.answer("✅ Верно")
        data["score"] += 1
    else:
        await callback.message.answer("❌ Неверно")

    # СЛЕДУЮЩИЙ ВОПРОС (фикс залипания)
    await state.update_data(
        question_index=index + 1,
        score=data["score"]
    )

    await send_question(callback.message, state)

# -------------------- ОБЪЯСНЕНИЕ --------------------

@dp.callback_query(F.data == "explain")
async def explain(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    if index < len(questions):
        explanation = questions[index]["explanation"]
        await callback.message.answer(f"📖 {explanation}")
    else:
        await callback.message.answer("Нет объяснения")

# -------------------- НАЗАД --------------------

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выбери режим:", reply_markup=menu_kb())

# -------------------- ЗАПУСК --------------------

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
