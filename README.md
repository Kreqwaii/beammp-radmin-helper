# BeamMP Radmin VPN Helper (Free OSS Lite Edition)

Zero-dependency Python 3 utility to help you host a **BeamMP Private Server** over **Radmin VPN** in seconds without manually hunting for adapter IPs or writing `ServerConfig.toml` from scratch.

Keywords: `BeamMP`, `Radmin VPN`, `Private Server`, `ServerConfig.toml`, `BeamNG.drive Multiplayer`, `Port 30814`

---

## English Documentation

### What It Does
- **Auto-detects your Radmin VPN IP (`26.x.x.x`)** from Windows `ipconfig` (and Linux/macOS fallback).
- **Checks TCP + UDP port `30814`** availability before you launch `BeamMP-Server.exe` (and shows the PID if another process holds the port on Windows).
- **Generates a valid `ServerConfig.toml`** configured for `Private = true` Direct Connect via Radmin VPN, with built-in map shortcuts (`west_coast_usa`, `italy`, `utah`, `johnson_valley`, etc.).
- **Zero external dependencies** — pure Python 3 standard library (`--self-test` verified).

### Quick Start
```bash
# Auto-detect Radmin VPN IP, check port 30814, and create ServerConfig.toml
python beammp_radmin_helper.py --name "My Drift Server" --map west_coast_usa --max-players 8

# Diagnostic check only (do not write ServerConfig.toml)
python beammp_radmin_helper.py --check-only

# Overwrite existing ServerConfig.toml with custom port and map
python beammp_radmin_helper.py --port 30814 --map italy --max-cars 2 --force

# Run built-in self-tests
python beammp_radmin_helper.py --self-test
```

### How Friends Join
1. Both host and friends install **Radmin VPN** and join the same Radmin network.
2. Put the generated `ServerConfig.toml` next to `BeamMP-Server.exe` and launch the server.
3. Friends open **BeamNG.drive -> Multiplayer -> Direct Connect** and enter your `26.x.x.x:30814` address printed by the script.

---

### Need Full Turnkey Pro Kit? (Auto-Downloader + Map Auto-Scanner + Nested Car Pack Fixer + Lua Admin Plugin)

This free Lite CLI solves initial IP detection and basic `ServerConfig.toml` generation. If you want a **complete turnkey BeamMP + Radmin VPN server suite** with zero manual troubleshooting:
- Automatic `BeamMP-Server.exe` downloader & launcher
- Automatic custom map scanner (reads mod `.zip` files and configures `Map = "/levels/.../info.json"` without typos)
- **Nested Car Pack Fixer** (automatically detects and fixes double-zipped / broken mod folders that fail to load for friends)
- Built-in **Lua Admin Plugin** (kick, teleport, announce, vehicle limits, anti-spam)
- Windows Firewall rule helper + step-by-step setup

👉 **Get the Full Turnkey Pro Kit (Instant Auto-Delivery on FunPay):**
- EN: https://funpay.com/en/lots/offer?id=82596043
- RU: https://funpay.com/lots/offer?id=82596043

---

## Документация на русском (RU)

### Что умеет бесплатная Lite-утилита
- **Автоматически находит ваш локальный IP в Radmin VPN (`26.x.x.x`)** через разбор сетевых адаптеров (`ipconfig`).
- **Проверяет занятость порта `30814` (TCP и UDP)** и подсказывает PID процесса на Windows, если порт уже занят.
- **Генерирует готовый `ServerConfig.toml`** для приватного сервера BeamMP (`Private = true`, быстрые алиасы карт `west_coast_usa`, `italy`, `utah`, `gridmap_v2` и др.).
- **Без сторонних библиотек** — только стандартная библиотека Python 3, встроенный `--self-test`.

### Быстрый запуск
```bash
# Определить IP Radmin VPN, проверить порт 30814 и создать ServerConfig.toml
python beammp_radmin_helper.py --name "Drift Radmin Server" --map west_coast_usa --max-players 8

# Только диагностика (без создания файла)
python beammp_radmin_helper.py --check-only

# Перезаписать существующий ServerConfig.toml
python beammp_radmin_helper.py --map italy --max-cars 2 --force

# Самопроверка скрипта
python beammp_radmin_helper.py --self-test
```

### Нужен полный Pro-комплект «под ключ»? (Auto-Downloader + Map Auto-Scanner + Nested Car Pack Fixer + Lua Admin Plugin)

Если не хочется вручную скачивать сервер, искать пути до кастомных карт в архивах, чинить вложенные кар-паки (когда машины у друзей не прогружаются) и настраивать админ-команды, забирайте готовый **Pro-набор с автовыдачей**:
- EN: https://funpay.com/en/lots/offer?id=82596043
- RU: https://funpay.com/lots/offer?id=82596043
