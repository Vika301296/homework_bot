class NoHomeworkNameError(Exception):
    """Исключение, которое выпадает, когда нет информации об имени дз."""

    pass


class WrongApiResponseCodeError(Exception):
    """Ошибка доступа к API."""

    pass
