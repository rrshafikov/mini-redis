# MINI-REDIS

Небольшой Redis-подобный TCP-кэш на чистом Python (без сторонних зависимостей в рантайме).  
Поддерживает RESP2-протокол и базовые команды, TTL с ленивой и фоновой очисткой, простого клиента, тесты на pytest и Dockerfile.

**Выполнил:** Руслан Шафиков  
Email: [rs31113@yandex.ru](mailto:rs31113@yandex.ru)  
TG: [@rrshafikov](https://t.me/rrshafikov)  
Телефон: +7 915 417-26-06  

## Содержание
- [Возможности](#возможности)
- [Быстрый старт](#быстрый-старт)
- [Команды](#команды)
- [Протокол](#протокол)
- [TTL и очистка](#ttl-и-очистка)
- [Расширяемость (как добавить команду)](#расширяемость-как-добавить-команду)
- [Тестирование](#тестирование)
- [Docker](#docker)
- [CI](#ci)
- [Дизайн и альтернативы](#дизайн-и-альтернативы)

---

## Возможности
- RESP2 парсер/энкодер (+ inline-команды).
- Команды:
  - `PING`
  - `SET` (`EX`/`PX`/`NX`/`XX`/`KEEPTTL`)
  - `GET`
  - `TTL`
  - `EXPIRE`, `PEXPIRE`
  - `DEL`, `EXISTS`
- TTL хранится как абсолютный дедлайн (Unix-время).
- Ленивое удаление при обращениях + фоновая задача-свипер.
- Асинхронный TCP-сервер на `asyncio`.
- Простой клиент-REPL.
- Тесты на `pytest`.
- Dockerfile.

---

## Быстрый старт

### Локально (Python 3.12+)
```bash
python -m redis_tcp.server --host 127.0.0.1 --port 6380
```

Во второй вкладке:
```bash
python -m redis_tcp.client 127.0.0.1 6380
> PING
PONG
> SET a 1
OK
> GET a
1
> SET t val EX 1
OK
> TTL t
1
```

> Если используете Homebrew-Python, создайте виртуальную среду:  
> `python3.12 -m venv .venv && source .venv/bin/activate`

---

## Команды

- `PING [message]` - Проверка связи;
- `SET key value [EX sec] [PX ms] [NX|XX] [KEEPTTL]` - Записать значение;
- `GET key` - Прочитать;
- `TTL key` - Остаток TTL, сек;
- `EXPIRE key sec` - Задать TTL в секундах;
- `PEXPIRE key ms` - Задать TTL в миллисекундах;
- `DEL key [key ...]` - Удалить ключи;
- `EXISTS key [key ...]` - Проверить существование.

Примеры:
```
SET k v EX 2      -> OK
TTL k             -> 2 (или 1)
PEXPIRE k 150     -> 1
GET missing       -> (nil)
SET x v NX        -> OK, SET x v2 NX -> (nil)
SET x v2 XX       -> OK только если x существует
```

---

## Протокол

Сервер понимает RESP2:  
- `+simple string\r\n`  
- `-error\r\n`  
- `:integer\r\n`  
- `$len\r\n...data...\r\n`  
- `*N\r\n ...`  

Также допускаются inline-команды вида `PING\r\n` (разбираются в массив).

---

## TTL и очистка

- TTL хранится как абсолютная отметка времени.  
- **Ленивая очистка**: при любом обращении к ключу проверяется истечение.  
- **Фоновая очистка**: периодическая задача удаляет просроченные ключи (по умолчанию ~раз/сек).

---

## Расширяемость (как добавить команду)

Открой `redis_tcp/commands.py` и зарегистрируй обработчик:

```python
from .protocol import encode_error, encode_integer

@registry.register("INCR")
async def cmd_incr(args, store):
    if len(args) != 1:
        return encode_error("ERR wrong number of arguments for 'INCR' command")
    key = args[0]
    raw = await store.get(key)
    try:
        n = int(raw.decode()) if raw is not None else 0
    except Exception:
        return encode_error("ERR value is not an integer or out of range")
    n += 1
    await store.set(key, str(n).encode())
    return encode_integer(n)
```

Если нужно новое поведение хранилища - добавь методы в `datastore.py`, покрой тестами.

---

## Тестирование

Тесты - интеграционные поверх TCP-сокета, запускают реальный сервер на случайном порту.  
Запуск:
```bash
PYTHONPATH=$PWD pytest -q
```

**Покрытие**: PING, SET/GET (с флагами), TTL/EXPIRE/PEXPIRE, DEL/EXISTS, ошибки арности, неизвестные команды, PX/KEEPTTL.  
**Риски**: возможны флаки по времени в TTL - заложены допуски (используем короткие sleep и допускаем 0/1 в секундах).

---

## Docker

Собрать и запустить:
```bash
docker build -t mini-redis .
docker run --rm -p 6380:6380 mini-redis
```

Переменные окружения: `HOST` (по умолчанию `0.0.0.0`), `PORT` (по умолчанию `6380`).

---

## CI

Готов GitHub Actions workflow `.github/workflows/ci.yml`:  
- Python 3.12  
- `pytest`  
- `docker build` (без публикации образа)

---

## Дизайн и альтернативы

- **Asyncio vs Threads**: выбран `asyncio` - простой неблокирующий сервер на стримах. Альтернатива: `socketserver.ThreadingMixIn` - больше блокировок/boilerplate.  
- **RESP2 vs свой протокол**: RESP позволяет легко пользоваться стандартными тулзами (типа `redis-cli`), реалистичнее для SDET-задачи. Свой протокол проще, но менее показателен.  
- **TTL**: абсолютные таймстемпы + ленивая очистка + периодический свипер. Альтернативы: тайм-вилл, приоритетная куча для точной выемки - сложнее, без нужды в этой задаче.  
- **Хранилище**: `dict[bytes -> (value, expiry)]`. Можно поддержать LRU/макс-память - вне скоупа ТЗ.  
- **Ошибки/арность**: имитация поведения Redis (wrong number of arguments, value is not an integer...).
