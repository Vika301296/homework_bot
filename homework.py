import os
import sys
import time
from typing import Any
import requests
import logging
import telegram

from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

# А тут установлены настройки логгера для текущего файла
logger = logging.getLogger(__name__)
# Устанавливаем уровень, с которого логи будут сохраняться в файл
logger.setLevel(logging.INFO)
# Указываем обработчик логов
handler = RotatingFileHandler("logger.log", maxBytes=50000000, backupCount=5)
logger.addHandler(handler)
# Создаем форматер
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Применяем его к хэндлеру
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


def check_tokens():
    """Проверяем наличие всех токенов."""
    tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    for token in tokens.items():
        if token is None:
            logging.critical(
                f"Отсутствует обязательная переменная окружения: {token}."
                "Программа принудительно остановлена."
            )
            sys.exit(1)
        else:
            return True


def send_message(bot, message):
    """Отправляем сообщение в Telegram чат."""
    chat_id = TELEGRAM_CHAT_ID
    try:
        bot.send_message(chat_id, message)
        logging.debug('Сообщение успешно отправлено')
    except Exception:
        logging.error('Сбой при отправке сообщения в Telegram')


def get_api_answer(timestamp) -> Any:
    """Делаем запрос к API Яндекс.Практикума."""
    try:
        params = {"from_date": timestamp}
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        ).json()
        if response.status_code != 200:
            logging.critical('Ошибка доступа к API')
            raise ConnectionError
    except Exception:
        logging.error("Эндпоинт недоступен")
    return response


def check_response(response_data):
    """Проверяет соответствует ли ответ API документации."""
    if not isinstance(response_data, dict):
        logging.error('Структура данных ответа не соответствует содержанию')
        raise TypeError
    if isinstance(response_data, list):
        logging.error('Структура данных ответа не соответствует содержанию')
        raise TypeError
    if not response_data.get('homeworks'):
        raise KeyError('В ответе сервера нет информации о дз')
    if not isinstance(response_data["homeworks"], list):
        logging.error('В ответе API домашки под ключом `homeworks`'
                      'данные приходят не в виде списка')
        raise TypeError
        # 'homeworks' in response.keys():
        #     if 'current_date' in response.keys():
        #         return response.get('homeworks')
        #     else:
        #         raise KeyError(
        #             'В ответе сервера нет информации о вреиени запроса')
        # else:
        #     raise KeyError('В ответе сервера нет информации о дз')
        # logging.error("Получен неожиданный ключ при запросе к API")
        # raise KeyError


def parse_status(homework):
    """Извлекаем из информации о  домашней работе статус этой работы."""
    # if isinstance(homework, dict):
    #    if isinstance(homework['homeworks'], list):

    status = homework.get("status")
    try:
        verdict = HOMEWORK_VERDICTS.get(status)
    except Exception:
        logging.error(
            f'Неожиданный статус домашней работы в ответе API: {verdict}'
        )
    try:
        homework_name = homework.get("homework_name")
    except KeyError:
        logging.error('Отсутствует имя работы в ответе сервера')
    return (f'Изменился статус проверки работы'
            f'"{homework_name}". {verdict}'
            )


def main():
    """Основная логика работы бота."""
    logging.info('Инициализация бота')
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            api_response = get_api_answer(timestamp)
            homework_response = check_response(api_response)
            if len(homework_response) > 0:
                send_message(bot, parse_status(homework_response[0]))
            timestamp = api_response['current_date']

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
