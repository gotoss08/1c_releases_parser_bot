import schedule
import time
import json
import asyncio
import os
import traceback

from telegram.ext import Application, CommandHandler
from telegram import ForceReply
from telegram.error import Forbidden

import releases_parser as rp
import bot_config as config

import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    filename='bot.log',
    level=logging.INFO
)

logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

subscribers_file_name = 'subscribers.json'
distros_file_name = 'distros.json'
current_distros = []
subscribers = []

def dump_subscribers():
    logging.info('dumping subscribers: %s', subscribers)
    with open(subscribers_file_name, 'w', encoding='utf-8') as f:
        json.dump(subscribers, f, ensure_ascii=False)

def restore_subscribers():
    global subscribers
    with open(subscribers_file_name, 'r', encoding='utf-8') as f:
        subscribers = json.load(f)
    logging.info('restoring subscribers from dump: %s', subscribers)

def chat_dict(chat):
    chat_dict = {
        'id': chat['id'],
        'first_name': chat['first_name'],
        'username': chat['username']
    }
    return chat_dict

async def bot_subscribe_command(update, context):

    chat = update.effective_chat
    logging.info('requested "start" command: %s', chat_dict(chat))

    global subscribers
    found_chat = next((c for c in subscribers if c['id'] == chat['id']), None)

    if not found_chat:
        logging.info('subscribed %s', chat['id'])
        subscribers.append(chat_dict(chat))
        dump_subscribers()
        await update.message.reply_text('Подписка на уведомления подключена')
    else:
        logging.info('already subscribed %s', chat['id'])
        await update.message.reply_text('Вы уже подписаны на уведомления')

async def bot_unsubscribe_command(update, context):
    chat = update.effective_chat
    logging.info('requested "unsubscribe" command: %s', chat_dict(chat))
    global subscribers
    subscribers = [c for c in subscribers if c['id'] != chat['id']]
    dump_subscribers()
    await chat.send_message('Подписка на уведомления отключена')

async def bot_about_command(update, context):
    chat = update.effective_chat
    logging.info('requested "about" command: %s', chat_dict(chat))
    message_text = f"Бот используется для автоматической отправки уведомлений о выходе новых обновлений на конфигурации 1С для Казахстана.\n\nИсточники данных:\nreleases.1c.ru\ndownload.1c-rating.kz\n\nПочта для обратной связи: {config.MAIL}"
    await chat.send_message(message_text)

async def send_to_subscribers(bot, text):
    logging.info('sending message "%s" to all subscribers', text)
    global subscribers
    for chat in subscribers:
        try:
            logging.info('sending to %s', chat_dict(chat))
            await bot.send_message(chat_id=chat['id'], text=text, parse_mode='HTML')
        except Forbidden:
            logging.info('bot blocked by user: %s', chat['id'])
            subscribers = [c for c in subscribers if c['id'] != chat['id']]
            dump_subscribers()
        except Exception as ex:
            logging.exception('sending message failed')

def compose_distro_update_text(distro):

    distro_name = distro['name']
    distro_url = distro['url']
    distro_version = distro['current_version']
    distro_release_date = distro['release_date']

    distro_name_text = f"<b>{distro_name}</b>"

    if distro_url and distro_version:
        distro_version_text = f"Версия: <a href=\"{distro_url}\">{distro_version}</a>"
    elif distro_version:
        distro_version_text = f"Версия: {distro_version}"
    elif distro_url:
        distro_version_text = f"Версия: <a href=\"{distro_url}\">{distro_url}</a>"
    else:
        distro_version_text = 'Версия не найдена'

    distro_release_date_text = f"Дата выхода: {distro_release_date}"

    message_text = (f"Новый релиз конфигурации\n"
            f"{distro_name_text}\n\n"
            f"{distro_version_text}\n"
            f"{distro_release_date_text}")

    return message_text

async def fetch_distros(context):

    global current_distros

    if config.RELOAD_CURRENT_DISTROS_FROM_DISK:
        current_distros = rp.load_distros_from_file(distros_file_name)

    loaded_distros = rp.fetch_distros()
    diffed_distros = rp.diff_distros(current_distros, loaded_distros)

    if diffed_distros:
        logging.info('found diffed distros')
        rp.dump_distros_to_file(loaded_distros, distros_file_name)
        current_distros = loaded_distros
        for distro in diffed_distros:
            message_text = compose_distro_update_text(distro)
            await send_to_subscribers(context.bot, message_text)

async def test_all_current_distros_distribution(app):
    for distro in current_distros:
        message_text = compose_distro_update_text(distro)
        await send_to_subscribers(app.bot, message_text)
    print('test_all_current_distros_distribution completed')

async def post_init(app):
    logging.info('bot started')
    # await test_all_current_distros_distribution(app)

def create_file_if_not_exists(file_path, initial_content):
    if not os.path.exists(file_path):
        with open(file_path, 'a') as f:
            f.write(initial_content)
            f.close()

if __name__ == '__main__':

    create_file_if_not_exists(subscribers_file_name, '[]')
    create_file_if_not_exists(distros_file_name, '[]')

    current_distros = rp.load_distros_from_file(distros_file_name)
    if not current_distros:
        logging.info('local distros not found, fetching fresh...')
        loaded_distros = rp.fetch_distros()
        rp.dump_distros_to_file(loaded_distros, distros_file_name)
        current_distros = loaded_distros

    restore_subscribers()

    app = Application.builder().token(config.TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler('start', bot_subscribe_command))
    app.add_handler(CommandHandler('unsubscribe', bot_unsubscribe_command))
    app.add_handler(CommandHandler('about', bot_about_command))

    app.job_queue.run_repeating(fetch_distros, interval=config.NEW_DISTROS_CHECK_INTERVAL, first=5)
    app.run_polling()

