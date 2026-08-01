import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# Импорты для Selenium
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

API_TOKEN = "Token TG"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# --- 🗄️ БАЗА ДАННЫХ ---

def init_db():
    """Создает базу данных и таблицу при старте бота."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS parsed_data
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       quote_text
                       TEXT
                   )
                   ''')
    conn.commit()
    conn.close()


def save_to_db(quote):
    """Сохраняет новую цитату в базу данных."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO parsed_data (quote_text) VALUES (?)", (quote,))
    conn.commit()
    conn.close()


def get_history(limit=3):
    """Достает последние сохраненные цитаты из базы."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT quote_text FROM parsed_data ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]  # Возвращаем список строк


# --- 📱 ИНТЕРФЕЙС БОТА ---

main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🎛️ Меню управления")]],
    resize_keyboard=True,
)

# Добавили новую кнопку для просмотра истории
inline_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📊 Собрать данные", callback_data="start_parsing")],
        [InlineKeyboardButton(text="🗂 История парсинга", callback_data="show_history")],
        [InlineKeyboardButton(text="🌐 Посетить сайт", url="https://quotes.toscrape.com")],
    ]
)


# --- 🕷️ ПАРСЕР SELENIUM ---

def run_selenium_parser():
    """Фоновый парсер с защитой от ошибок."""
    options = Options()
    options.add_argument("--headless")
    driver = None

    try:
        # НОВАЯ ЛОГИКА ЗАПУСКА:
        # 1. Менеджер скачивает ИДЕАЛЬНО подходящий драйвер для вашего Firefox
        # 2. Мы передаем его в Service, игнорируя то, что лежит в /snap/bin/
        service = Service(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=options)

        driver.get("https://quotes.toscrape.com/")
        wait = WebDriverWait(driver, 10)

        # Скриншот для отладки
        driver.save_screenshot("debug.png")

        first_quote = wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "text"))
        )
        return True, first_quote.text
    except Exception as e:
        return False, str(e)
    finally:
        if driver:
            driver.quit()


# --- ⚙️ ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Бот готов к работе!", reply_markup=main_kb)


@dp.message(F.text == "🎛️ Меню управления")
async def open_menu(message: Message):
    await message.answer("Выберите действие:", reply_markup=inline_menu)


# --- ⚙️ ОБРАБОТЧИК КНОПКИ ПАРСИНГА ---

@dp.callback_query(F.data == "start_parsing")
async def process_start_parsing(callback: CallbackQuery):
    msg = await callback.message.answer("⏳ Собираю данные с сайта...")

    # 1. Запускаем парсер и РАСПАКОВЫВАЕМ два значения: флаг успеха и сами данные
    success, data = await asyncio.to_thread(run_selenium_parser)

    # 2. Проверяем флаг success (True или False)
    if success:
        await asyncio.to_thread(save_to_db, data)
        await msg.edit_text(f"✅ Данные собраны и сохранены в базу!\n\n<i>«{data}»</i>", parse_mode="HTML")
    else:
        # Если была ошибка, выводим её прямо в Telegram
        await msg.edit_text(f"❌ Ошибка при запуске браузера:\n{data}")

    await callback.answer()


@dp.callback_query(F.data == "show_history")
async def process_show_history(callback: CallbackQuery):
    await callback.answer()

    # Достаем данные из базы
    history = await asyncio.to_thread(get_history, 3)  # Берем 3 последние записи

    if not history:
        await callback.message.answer("📭 База данных пока пуста. Сначала соберите данные!")
        return

    # Формируем красивое сообщение
    text = "<b>🗂 Последние 3 записи из базы:</b>\n\n"
    for i, quote in enumerate(history, start=1):
        text += f"{i}. <i>{quote}</i>\n\n"

    await callback.message.answer(text, parse_mode="HTML")


# --- 🚀 ЗАПУСК ---

async def main():
    init_db()  # Создаем базу при запуске скрипта
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
