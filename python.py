import logging
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import requests
from functools import partial
from datetime import datetime, time, timedelta
import pytz

# Конфигурация логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# API токен бота и API ключ для OpenWeatherMap
TELEGRAM_BOT_TOKEN = '7244186636:AAE8EH7nPX_Yu_fN08VChHJKCwYuOAy-KIg'
WEATHER_API_KEY = 'dd11a63b3c2b7165eb36ac8ad79e9ecf'

# Словарь для хранения данных пользователей
user_data = {}

# Функция для получения прогноза погоды
def get_weather(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    response = requests.get(url)
    data = response.json()
    weather = data['weather'][0]['description']
    temperature = data['main']['temp']
    return f"Погода: {weather}, Температура: {temperature}°C"

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = KeyboardButton('Поделиться локацией', request_location=True)
    reply_markup = ReplyKeyboardMarkup([[button]], one_time_keyboard=True)
    await update.message.reply_text('Привет! Поделитесь своей локацией, чтобы я мог отправлять вам прогноз погоды.', reply_markup=reply_markup)

# Команда /now для немедленного получения прогноза погоды
async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    lat, lon = user_data.get(user_id, (None, None))
    if lat and lon:
        weather = get_weather(lat, lon)
        await update.message.reply_text(f'Ваш текущий прогноз погоды:\n{weather}')
    else:
        await update.message.reply_text('Сначала поделитесь своей локацией, используя команду /start.')

# Обработка сообщения с локацией
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_location = update.message.location
    user_id = update.message.from_user.id
    user_data[user_id] = (user_location.latitude, user_location.longitude)
    await update.message.reply_text('Локация сохранена! Я настрою ежедневное отправление прогноза погоды на 08:00.')

    # Get the current time in the timezone +05:00
    timezone_offset = pytz.FixedOffset(300)  # +05:00 is 300 minutes
    now = datetime.now(timezone_offset)

    # Set the time for the job to 08:00:21.547733
    scheduled_time = time(hour=7, minute=0)
    now_date = now.date()
    scheduled_datetime = datetime.combine(now_date, scheduled_time) + timedelta(seconds=21, microseconds=547733)

    # Set the timezone to +05:00
    scheduled_datetime = scheduled_datetime.replace(tzinfo=timezone_offset)

    # Calculate the next run time
    if now > scheduled_datetime:
        next_run = scheduled_datetime + timedelta(days=1)
    else:
        next_run = scheduled_datetime

    # Calculate the delay in seconds until the next run
    delay = (next_run - now).total_seconds()
    logging.info(f"Delay in seconds: {delay}")
    logging.info(f"Current time: {now}")
    logging.info(f"Next run time: {next_run}")

    # Schedule the daily job
    context.job_queue.run_repeating(
        partial(send_weather, user_id=user_id),
        interval=86400,  # 24 hours
        first=delay,     # Initial delay until the first execution
        name=str(user_id),
    )

# Отправка прогноза погоды
async def send_weather(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    lat, lon = user_data.get(user_id, (None, None))
    if lat and lon:
        weather = get_weather(lat, lon)
        await context.bot.send_message(chat_id=user_id, text=f'Ваш прогноз погоды на сегодня:\n{weather}')

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    job_queue = application.job_queue
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('now', now))  # Добавляем обработчик для команды /now
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))

    application.run_polling()
