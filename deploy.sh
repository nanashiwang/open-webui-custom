#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$APP_DIR/.env.deploy"
COMPOSE_FILE="$APP_DIR/docker-compose.deploy.yaml"

cd "$APP_DIR"

compose_up() {
  source "$ENV_FILE"

  if [[ "${LOCAL_BUILD:-}" == "true" || "${WEBUI_IMAGE:-}" != ghcr.io/* ]]; then
    echo "使用服务器本地构建镜像..."
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build
  elif docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull; then
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
  else
    echo "镜像拉取失败，改为在服务器本地构建..."
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build
  fi

  docker image prune -f >/dev/null
  docker ps --filter name=open-webui
}

wait_webui() {
  source "$ENV_FILE"
  local port="${OPEN_WEBUI_PORT:-3000}"

  echo "等待服务恢复..."
  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      echo "服务已恢复：http://127.0.0.1:${port}"
      return 0
    fi
    sleep 2
  done

  echo "服务仍未就绪，请执行：open logs"
  return 1
}

restart_webui() {
  if docker ps -a --format '{{.Names}}' | grep -qx 'open-webui'; then
    docker restart -t 2 open-webui >/dev/null
  else
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
  fi

  wait_webui
  docker ps --filter name=open-webui
}

run_data_python() {
  source "$ENV_FILE"
  local image="${WEBUI_IMAGE:-ghcr.io/nanashiwang/open-webui-custom}:${WEBUI_DOCKER_TAG:-main}"

  docker run --rm \
    --entrypoint python \
    -v open-webui:/app/backend/data \
    "$image" "$@"
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
ENABLE_SIGNUP=true
ENV
  echo "已自动生成 $ENV_FILE"
fi

if ! grep -q '^ENABLE_SIGNUP=' "$ENV_FILE"; then
  cat >> "$ENV_FILE" <<'ENV'
ENABLE_SIGNUP=true
ENV
fi

set_signup() {
  local enabled="$1"
  run_data_python - "$enabled" <<'PY'
import json
import sqlite3
import sys

enabled = sys.argv[1].lower() == "true"
db_path = "/app/backend/data/webui.db"

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT id, data FROM config ORDER BY id DESC LIMIT 1")
row = cur.fetchone()
if row is None:
    data = {"version": 0, "ui": {"enable_signup": enabled}}
    cur.execute("INSERT INTO config (data, version) VALUES (?, 0)", (json.dumps(data),))
else:
    config_id, raw = row
    data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    data.setdefault("ui", {})["enable_signup"] = enabled
    cur.execute("UPDATE config SET data = ? WHERE id = ?", (json.dumps(data), config_id))
conn.commit()
conn.close()
print("用户注册入口已" + ("开启" if enabled else "关闭"))
PY
  restart_webui
}

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
  signup)
    case "${2:-status}" in
      on|enable|true)
        set_signup true
        ;;
      off|disable|false)
        set_signup false
        ;;
      status)
        run_data_python - <<'PY'
import json
import sqlite3

conn = sqlite3.connect("/app/backend/data/webui.db")
cur = conn.cursor()
cur.execute("SELECT data FROM config ORDER BY id DESC LIMIT 1")
row = cur.fetchone()
enabled = None
if row:
    data = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
    enabled = data.get("ui", {}).get("enable_signup")
print("用户注册入口：" + ("开启" if enabled else "关闭"))
PY
        ;;
      *)
        echo "用法: open signup [on|off|status]"
        exit 1
        ;;
    esac
    ;;
  *)
    echo "用法: open [install|update|restart|logs|down|signup|install-command]"
    exit 1
    ;;
esac
