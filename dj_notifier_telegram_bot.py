import os
import json
import asyncio
import holidays
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

CONFIG_FILE_PATH = "config.json"
CONFIG_ABS_PATH = os.path.abspath(CONFIG_FILE_PATH)

# Load config
def load_config():
    with open(CONFIG_FILE_PATH, "r") as file:
        return json.load(file)

config = load_config()

TOKEN = config["TOKEN"]
GROUP_ID = config["GROUP_ID"]
USER_LIST = config["USER_LIST"]
COUNTRY_CODE = config.get("COUNTRY_CODE", "RU")

# Initialize bot
app = Application.builder().token(TOKEN).build()

# Get public holidays
public_holidays = holidays.country_holidays(COUNTRY_CODE)

# Counter for user index (resets on restart)
user_index = 0

# Function to check if today is a valid posting day
def is_valid_day():
    today = datetime.today()
    return today.weekday() < 5 and today.strftime("%Y-%m-%d") not in public_holidays  # Mon-Fri & not a holiday

# Function to get the next user in the list
def get_next_user():
    global user_index
    user = USER_LIST[user_index % len(USER_LIST)]  # Rotate through users
    user_index += 1  # Increment after posting
    return user

# Function to notify user
async def notify_user():
    if is_valid_day():
        user = get_next_user()
        text = f"🎵 {user}, сегодня твоя очередь постить трек дня!"
        await app.bot.send_message(chat_id=GROUP_ID, text=text)

# Run async function inside scheduler
def run_async_job():
    asyncio.run(notify_user())

# Setup APScheduler
def schedule_notification():
    global scheduler
    notification_time = config.get("NOTIFICATION_TIME", "08:00") # Time in UTC, default 08:00, 24-hour format
    notification_hour, notification_minute = map(int, notification_time.split(":"))

    # Check if job exists, update it; otherwise, add a new one
    job = scheduler.get_job("notification_job")
    if job:
        job.reschedule(trigger=CronTrigger(hour=notification_hour, minute=notification_minute))
    else:
        scheduler.add_job(run_async_job, "cron", hour=notification_hour, minute=notification_minute, id="notification_job")

scheduler = BackgroundScheduler()
schedule_notification()
scheduler.start()

# Monitor config changes using watchdog
class ConfigFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if os.path.abspath(event.src_path) == CONFIG_ABS_PATH:
            print(f"Config file {CONFIG_FILE_PATH} has been modified. Reloading...")
            global config, USER_LIST
            config = load_config()  # Reload config
            USER_LIST = config["USER_LIST"]  # Update USER_LIST
            schedule_notification() # Update the scheduled job

# Setup watchdog to monitor changes in the config file
observer = Observer()
observer.schedule(ConfigFileHandler(), path="./", recursive=False)
observer.start()

if __name__ == "__main__":
    print("Bot is running...")
    try:
        app.run_polling()
    except KeyboardInterrupt:
        app.stop_polling()
        observer.stop()
        scheduler.shutdown()
    observer.join()
