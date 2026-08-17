# Образ для запуска Strix (autonomous pentest agent) на Windows через Docker.
#
# Зачем он нужен. strix-agent требует Python 3.12+ и собран только под
# Linux/macOS — на Windows нативно не ставится. Внутри стандартного
# python:3.12-slim его тоже мало: Strix запускает свою песочницу командой
# `docker`, а в базовом образе клиента нет. Пакет docker.io в этом Debian
# кладёт только демон, поэтому берём статический бинарник клиента.
#
# Сборка:
#   docker build -t ntfast-strix:local tools/strix
#
# Запуск (localhost — ваш сервер, авторизация на его тест у вас есть).
# Ключ модели ставите вы; для Ollama подойдёт любая непустая строка:
#   docker run --rm \
#     --add-host=host.docker.internal:host-gateway \
#     -v //var/run/docker.sock:/var/run/docker.sock \
#     -e STRIX_LLM=ollama/qwen2.5:7b-instruct \
#     -e LLM_API_BASE=http://host.docker.internal:11434 \
#     -e LLM_API_KEY=ollama-local \
#     ntfast-strix:local \
#     -n -m quick --max-turns 4 \
#     -t http://host.docker.internal:8000 \
#     --instruction "Проверь аутентификацию и ограничение частоты на /api/auth/login."
#
# Реалистичное ожидание. Strix рассчитан на frontier-модели (в примерах
# gpt-5.4). На qwen2.5:7b, работающей частично на процессоре, один ход
# агента — под минуту, а Strix ведёт долгую петлю из десятков ходов и
# спавнит несколько агентов. Прогон займёт часы, и качество находок будет
# ниже, чем у прицельных тестов, которые уже есть в проекте (инъекция через
# назначение платежа, обход rate-limit, доступ к чужим анализам).
FROM python:3.12-slim

ARG DOCKER_CLI_VERSION=27.5.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" \
       -o /tmp/docker.tgz \
    && tar -xzf /tmp/docker.tgz -C /tmp \
    && install /tmp/docker/docker /usr/local/bin/docker \
    && rm -rf /tmp/docker* /var/lib/apt/lists/* \
    && pip install --no-cache-dir strix-agent

ENTRYPOINT ["strix"]
