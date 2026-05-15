#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$APP_DIR/.env.deploy"
COMPOSE_FILE="$APP_DIR/docker-compose.deploy.yaml"

cd "$APP_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  SECRET="$(openssl rand -hex 32 2>/dev/null || python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  cat > "$ENV_FILE" <<ENV
WEBUI_SECRET_KEY=$SECRET
WEBUI_IMAGE=ghcr.io/nanashiwang/open-webui
WEBUI_DOCKER_TAG=main
OPEN_WEBUI_PORT=3000
ENV
  echo "已自动生成 $ENV_FILE"
fi

case "${1:-update}" in
  install|up)
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
    docker image prune -f >/dev/null
    docker ps --filter name=open-webui
    ;;
  update)
    if [[ -d "$APP_DIR/.git" ]]; then
      git -C "$APP_DIR" pull --ff-only "${APP_GIT_REMOTE:-origin}" "${APP_GIT_BRANCH:-main}"
    fi
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
    docker image prune -f >/dev/null
    docker ps --filter name=open-webui
    ;;
  install-command|link)
    install -m 0755 "$APP_DIR/open" /usr/local/bin/open
    echo "已安装命令：open update"
    ;;
  restart)
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" restart
    ;;
  logs)
    docker logs -f --tail=200 open-webui
    ;;
  down)
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down
    ;;
  *)
    echo "用法: open [install|update|restart|logs|down|install-command]"
    exit 1
    ;;
esac
