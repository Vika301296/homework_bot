import os
import sys
import time
import requests
import logging
import telegram

from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler("logger.log", maxBytes=50000000, backupCount=5)
logger.addHandler(handler)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


class NoHomeworkName(Exception):
    """Исключение, которое выпадает, когда нет информации об имени дз."""

    logger.error('В ответе API домашки нет ключа "homework_name"')


def check_tokens():
    """Проверяем наличие всех токенов."""
    return all((PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN))


def send_message(bot, message):
    """Отправляем сообщение в Telegram чат."""
    chat_id = TELEGRAM_CHAT_ID
    try:
        bot.send_message(chat_id, message)
        logger.debug(f'Сообщение {message} успешно отправлено')
    except Exception:
        logger.error('Сбой при отправке сообщения в Telegram')


def get_api_answer(timestamp):
    """Делаем запрос к API Яндекс.Практикума."""
    try:
        params = {"from_date": timestamp}
        response = requests.get(
            url=ENDPOINT, headers=HEADERS, params=params
        )
    except requests.RequestException:
        logger.critical('Ошибка доступа к API')
    if response.status_code != 200:
        logger.critical('Ошибка доступа к API')
        raise requests.RequestException
    return response.json()


def check_response(response_data):
    """Проверяет соответствует ли ответ API документации."""
    if not isinstance(response_data, dict):
        logger.error('Структура данных ответа не соответствует содержанию')
        raise TypeError
    if isinstance(response_data, list):
        logger.error('Структура данных ответа не соответствует содержанию')
        raise TypeError
    if not response_data.get('homeworks'):
        raise KeyError('В ответе сервера нет информации о дз')
    if not isinstance(response_data["homeworks"], list):
        logger.error('В ответе API домашки под ключом `homeworks`'
                     'данные приходят не в виде списка')
        raise TypeError
    homework_list = response_data.get('homeworks')
    return homework_list


def parse_status(homework):
    """Извлекаем из информации о домашней работе статус этой работы."""
    status = homework["status"]
    verdict = HOMEWORK_VERDICTS.get(status)
    homework_name = homework.get("homework_name")

    if 'homework_name' not in homework:
        logger.error('Отсутствует имя работы в ответе сервера')
        raise NoHomeworkName('В ответе API домашки нет ключа "homework_name"')
    if status not in HOMEWORK_VERDICTS:
        logger.error(
            'Неожиданный статус домашней работы в ответе API'
        )
        raise NoHomeworkName
    return (f'Изменился статус проверки работы'
            f' "{homework_name}". {verdict}'
            )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical("Отсутствуют токены", exc_info=True)
        sys.exit(1)
    logger.info('Инициализация бота')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    old_message = ''
    while True:
        try:
            api_response = get_api_answer(timestamp)
            homework_response = check_response(api_response)
            if len(homework_response) > 0:
                message = parse_status(homework_response[0])
                if message != old_message:
                    send_message(bot, message)
                    logger.debug(f'Сообщение {message} успешно отправлено')
                else:
                    logger.debug('Статус не изменился')
                    old_message = message
            timestamp = api_response['current_date']
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            send_message(bot, message)
            logger.debug('Сообщение об ошибке отправлено')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
