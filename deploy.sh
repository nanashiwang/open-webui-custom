#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$APP_DIR/.env.deploy"
COMPOSE_FILE="$APP_DIR/docker-compose.deploy.yaml"

cd "$APP_DIR"

compose_up() {
  if docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull; then
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
  else
    echo "镜像拉取失败，改为在服务器本地构建..."
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build
  fi
  docker image prune -f >/dev/null
  docker ps --filter name=open-webui
}

if [[ ! -f "$ENV_FILE" ]]; then
  SECRET="$(openssl rand -hex 32 2>/dev/null || python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  cat > "$ENV_FILE" <<ENV
WEBUI_SECRET_KEY=$SECRET
WEBUI_IMAGE=ghcr.io/nanashiwang/open-webui-custom
WEBUI_DOCKER_TAG=main
OPEN_WEBUI_PORT=3000
ENV
  echo "已自动生成 $ENV_FILE"
fi

case "${1:-update}" in
  install|up)
    compose_up
    ;;
  update)
    if [[ -d "$APP_DIR/.git" ]]; then
      git -C "$APP_DIR" pull --ff-only "${APP_GIT_REMOTE:-origin}" "${APP_GIT_BRANCH:-main}"
    fi
    compose_up
    ;;
  install-command|link)
    ln -sf "$APP_DIR/open" /usr/local/bin/open
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
