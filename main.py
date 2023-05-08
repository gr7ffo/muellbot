import asyncio
import json
import logging
import os
from datetime import datetime

import requests
import telegram
from bs4 import BeautifulSoup
from dateutil.parser import parse
from todoist_api_python.api import TodoistAPI


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

try:
    logging.info('Loading env')
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    BOT_URL = os.getenv('BOT_URL')
    CHAT_ID = os.getenv('CHAT_ID')
    CHAT_ID_LOCATION = os.getenv('CHAT_ID_LOCATION')
    DOIST_TOKEN = os.getenv('DOIST_TOKEN')
    logging.info('Environment loaded')
except Exception as e:
    logging.error('Environment not set up correctly')


def get_collection_dates(url: str, next_collection_date: dict) -> dict:
    logging.info(f'Current time: {datetime.now()}')

    logging.debug('Parsing page')
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'html.parser')
    uebersicht = soup.find(id='uebersicht')
    collection_type = []
    collection_days = []

    for i in range(len(uebersicht.find_all('h3'))):
        collection_type.append(uebersicht.find_all('h3')[i].text[:-1])
        collection_days.append(uebersicht.find_all('h1')[i].text.split('\n')[0])

    logging.debug(f'Matching collection lengths: {len(collection_type) == len(collection_days)}')

    if len(collection_days) == 4:
        for i, _ in enumerate(collection_days):
            type = collection_type[i]     
            if type in next_collection_date.keys():
                day = collection_days[i]
                if parse(day, fuzzy=False):
                    col_day = datetime.strptime(day, '%d.%m.%Y')
                    time_to_go = col_day - datetime.now()
                    next_collection_date[type]['collection_date'] = day
                    next_collection_date[type]['days_to_go'] = time_to_go.days
                    logging.debug(type)
                    logging.debug(next_collection_date[type])
                else:
                    logging.warning(f'No next collection date found for: {type}')
                    next_collection_date[type] = ''                
    else:
        logging.error('Something went wrong in collecting')
        for key in next_collection_date.keys():
            next_collection_date[key]['days_to_go'] = -1

    logging.info('Done parsing')
    logging.debug(next_collection_date)
    json.dump(next_collection_date, open('next_collection_date.json', 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
    return next_collection_date


def get_correct_date(date: str):
    """Convert collection dates to todoist format"""
    return date.split('.')[2] + '-' + date.split('.')[1] + '-' + date.split('.')[0]


def create_todoist(content: str):
    """Create a todoist task for given collection date"""
    api = TodoistAPI(DOIST_TOKEN)
    api.add_task(content=content, due_string='today', project_id=2312227161)


async def main():
    """Main method"""
    try:
        json.load(open('next_collection_date.json', encoding='utf-8'))
    except:
        logging.error('Collection file not found')

    bot = telegram.Bot(token=BOT_TOKEN)
    logging.info('Telegram bot created')

    async with bot:
        next_collections = json.load(open('next_collection_date.json', encoding='utf-8'))

        logging.debug('Running daily')
        try:
            logging.info('New collection dates found')
            next_collections = get_collection_dates(BOT_URL + CHAT_ID_LOCATION, next_collections)
            for collection in next_collections.keys():
                if next_collections[collection]['days_to_go'] == 0:
                    logging.debug(f'Sending message to {CHAT_ID}')
                    message_text = collection + ' ist morgen (' + next_collections[collection]['collection_date'] + ') dran!'
                    await bot.send_message(chat_id=CHAT_ID, text=message_text)
                    logging.debug('Trying to create Todoist task')
                    try:
                        create_todoist(collection + ' rausstellen @neumarkt')
                        logging.debug('Todoist task created')
                    except Exception as e:
                        await bot.send_message(chat_id=CHAT_ID, text='Todoist task could not be created!')
                        logging.error('Todoist task could not be created!')
                        logging.error(e)
                elif next_collections[collection]['days_to_go'] < 0:
                    logging.debug(f'Sending message to {CHAT_ID}')
                    message_text = collection + ' war am ' + next_collections[collection]['collection_date'] + ' dran.'
                    await bot.send_message(chat_id=CHAT_ID, text=message_text)
                elif next_collections[collection]['days_to_go'] == 6:
                    logging.debug(f'Sending message to {CHAT_ID}')
                    message_text = collection + ' ist am ' + next_collections[collection]['collection_date'] + ' dran.'
                    await bot.send_message(chat_id=CHAT_ID, text=message_text)
                else:
                    #logging.debug(f'Sending message to {CHAT_ID}')
                    #message_text = collection + ' ist erst am ' + next_collections[collection]['collection_date'] + ' dran.'
                    #await bot.send_message(chat_id=CHAT_ID, text=message_text)
                    #logging.info('Daily message sent')
                    pass
        except Exception as e:
            error_text = f'Something went wrong during daily parsing: {e}'
            logging.error(error_text)


if __name__ == "__main__":
    asyncio.run(main())
