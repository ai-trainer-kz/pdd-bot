import os
import asyncio
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import psycopg2

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = 503301815

# ================= BOT =================

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================= DATABASE =================

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

# ================= TABLES =================

cursor.execute("""
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT,
    name TEXT,
    phone TEXT,
    visits INTEGER DEFAULT 0,
    total_paid INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS services (
    id SERIAL PRIMARY KEY,
    title TEXT,
    price INTEGER,
    duration INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS masters (
    id SERIAL PRIMARY KEY,
    name TEXT,
    specialty TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    client_id INTEGER
)
""")

asyncio.run(main())
