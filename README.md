# kurs-mayak

Telegram-бот для мониторинга курсов валют и криптовалют.

## Контракты backend

В `contracts.py` описаны данные и ошибки, в `ports.py` интерфейсы внешних зависимостей, в `services.py` операции сервисов. Для работы с БД модуль открывает транзакцию через `async with open_uow() as uow`, обращается к её репозиториям и вызывает `await uow.commit()` после изменений.

`build_application` в `application.py` принимает адаптеры и фабрики модулей, собирает сервисы и передаёт их боту и фоновому обработчику. Пример подмены источника котировок, времени и Telegram приведён в `tests/test_application.py`.

Для запуска проверок из корня проекта нужен Python 3.12.

```sh
python -m pip install pytest pytest-asyncio
python -m pytest -q
```
