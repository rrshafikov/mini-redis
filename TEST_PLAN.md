# TEST PLAN
- Протокол RESP: простые/целые/bulk/array.
- Команды: PING, GET/SET(+флаги), TTL, EXPIRE/PEXPIRE, DEL, EXISTS.
- Риски: тайминги TTL, NX/XX, очистка.
- Сценарии: happy path + ошибки арity/типов/неизвестные команды.
