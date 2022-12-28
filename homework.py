import sys
import time
import requests
import logging
import telegram
import os
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler


from exceptions import NoHomeworkNameError, WrongApiResponseCodeError

load_dotenv()

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
    return all((PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN))


def send_message(bot, message):
    """Отправляем сообщение в Telegram чат."""
    logging.debug(f'Отправляем сообщение "{message}"')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f"Сообщение {message} успешно отправлено")
    except Exception:
        raise ConnectionError


def get_api_answer(timestamp) -> dict:
    """Делаем запрос к API Яндекс.Практикума."""
    logging.debug(f'Делаем запрос к API в "{timestamp}"')
    try:
        params = {"from_date": timestamp}
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except Exception:
        requests.exceptions.RequestException
    if response.status_code != 200:
        logging.error("Ошибка доступа к API")
        raise WrongApiResponseCodeError(
            f'Код ответа от API {response.status_code}')
    return response.json()


def check_response(response_data) -> list:
    """Проверяет соответствует ли ответ API документации."""
    if not isinstance(response_data, dict):
        raise TypeError("Данные ответа не соответствуют документации API")
    if not response_data.get("homeworks"):
        raise KeyError("В ответе сервера нет информации о дз")
    if not isinstance(response_data["homeworks"], list):
        raise TypeError
    return response_data.get("homeworks")


def parse_status(homework) -> str:
    """Извлекаем из информации о домашней работе статус этой работы."""
    status = homework.get("status")
    if "homework_name" not in homework:
        logging.error("Отсутствует имя работы в ответе сервера")
        raise NoHomeworkNameError(
            'В ответе API домашки нет ключа "homework_name"')
    if status not in HOMEWORK_VERDICTS:
        logging.error("Неожиданный статус домашней работы в ответе API")
        raise NoHomeworkNameError

    verdict = HOMEWORK_VERDICTS.get(status)
    homework_name = homework.get("homework_name")
    return f"Изменился статус проверки работы" f' "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical("Отсутствуют токены", exc_info=True)
        sys.exit(1)
    logging.info("Инициализация бота")
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    old_message = ""
    while True:
        try:
            api_response = get_api_answer(timestamp)
        except Exception:
            logging.error("Ошибка доступа к API")
        try:
            homework_response = check_response(api_response)
        except Exception:
            logging.error('Ответ API не соответствует документации')
        try:
            if len(homework_response) > 0:
                message = parse_status(homework_response[0])
                if message != old_message:
                    send_message(bot, message)
                    logging.debug(f"Сообщение {message} успешно отправлено")
                else:
                    logging.debug("Статус не изменился")
                    old_message = message
            timestamp = api_response["current_date"]
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            send_message(bot, message)
            logging.error(f"Сообщение об ошибке {error} отправлено")
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    handler = RotatingFileHandler(
        "logger.log", maxBytes=50000000, backupCount=5)
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
        handlers=[handler],
    )

    main()
