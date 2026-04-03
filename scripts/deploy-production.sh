#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE_DEFAULT="$SCRIPT_DIR/deploy-production.env"

if [[ -f "$ENV_FILE_DEFAULT" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE_DEFAULT"
fi

APP_ROOT="${APP_ROOT:-$APP_ROOT_DEFAULT}"
BRANCH="${BRANCH:-main}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"
VERTEX_SOURCE_DIR="${VERTEX_SOURCE_DIR:-vertex}"
VERTEX_POOL_FILE="${VERTEX_POOL_FILE:-config/vertex-pool.json}"
VERTEX_CREDENTIALS_DIR="${VERTEX_CREDENTIALS_DIR:-credentials/imported}"
VERTEX_PROJECTS="${VERTEX_PROJECTS:-}"
VERTEX_MAX_PER_PROJECT="${VERTEX_MAX_PER_PROJECT:-}"
VERTEX_LOCATION="${VERTEX_LOCATION:-global}"
VERTEX_MODELS="${VERTEX_MODELS:-}"
LITELLM_OUTPUT_FILE="${LITELLM_OUTPUT_FILE:-config/litellm.generated.yaml}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8080/healthz}"
PUBLIC_URL="${PUBLIC_URL:-}"
HEALTHCHECK_ATTEMPTS="${HEALTHCHECK_ATTEMPTS:-10}"
HEALTHCHECK_INTERVAL="${HEALTHCHECK_INTERVAL:-3}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REQUIRE_ROOT="${REQUIRE_ROOT:-0}"
ALLOW_DIRTY="${ALLOW_DIRTY:-0}"
DRY_RUN="${DRY_RUN:-0}"

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "[deploy] 缺少必填变量: $name" >&2
    exit 1
  fi
}

run() {
  echo "+ $*"
  if [[ "$DRY_RUN" == "1" ]]; then
    return 0
  fi
  "$@"
}

retry() {
  local attempts="$1"
  local interval="$2"
  shift 2
  local i
  for ((i = 1; i <= attempts; i++)); do
    if "$@"; then
      return 0
    fi
    if [[ "$i" -lt "$attempts" ]]; then
      sleep "$interval"
    fi
  done
  return 1
}

docker_compose() {
  docker compose -f "$DOCKER_COMPOSE_FILE" "$@"
}

write_build_info() {
  local commit short_commit deployed_at
  commit="$(git rev-parse HEAD)"
  short_commit="$(git rev-parse --short HEAD)"
  deployed_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  cat > "$APP_ROOT/build-info.json" <<EOF
{
  "commit": "$commit",
  "short_commit": "$short_commit",
  "deployed_at": "$deployed_at"
}
EOF
}

main() {
  require_var APP_ROOT

  if [[ "$REQUIRE_ROOT" == "1" && "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "[deploy] 当前部署要求 root 身份运行" >&2
    exit 1
  fi

  cd "$APP_ROOT"

  if [[ ! -d .git ]]; then
    echo "[deploy] APP_ROOT 不是 git 仓库: $APP_ROOT" >&2
    exit 1
  fi

  local worktree_status
  worktree_status="$(git status --porcelain)"
  if [[ -n "$worktree_status" && "$ALLOW_DIRTY" != "1" ]]; then
    echo "[deploy] 工作区不干净，先处理本地改动再部署" >&2
    echo "$worktree_status" >&2
    exit 1
  fi

  echo "[deploy] APP_ROOT=$APP_ROOT"
  echo "[deploy] BRANCH=$BRANCH"
  echo "[deploy] GIT_REMOTE=$GIT_REMOTE"
  echo "[deploy] 旧提交：$(git rev-parse --short HEAD 2>/dev/null || echo none)"

  run git fetch --prune "$GIT_REMOTE" "$BRANCH"
  run git pull --ff-only "$GIT_REMOTE" "$BRANCH"

  echo "[deploy] 新提交：$(git rev-parse --short HEAD)"

  if [[ ! -f "$ENV_FILE" ]]; then
    echo "[deploy] 缺少环境文件: $ENV_FILE" >&2
    exit 1
  fi

  if [[ ! -d "$VERTEX_SOURCE_DIR" ]]; then
    echo "[deploy] 缺少 Vertex JSON 目录: $VERTEX_SOURCE_DIR" >&2
    exit 1
  fi

  local build_vertex_args=(
    scripts/build_vertex_pool_from_dir.py
    --vertex-dir "$VERTEX_SOURCE_DIR"
    --output-config "$VERTEX_POOL_FILE"
    --output-credentials-dir "$VERTEX_CREDENTIALS_DIR"
    --location "$VERTEX_LOCATION"
  )
  if [[ -n "$VERTEX_PROJECTS" ]]; then
    build_vertex_args+=(--projects "$VERTEX_PROJECTS")
  fi
  if [[ -n "$VERTEX_MAX_PER_PROJECT" ]]; then
    build_vertex_args+=(--max-per-project "$VERTEX_MAX_PER_PROJECT")
  fi
  if [[ -n "$VERTEX_MODELS" ]]; then
    build_vertex_args+=(--models "$VERTEX_MODELS")
  fi

  run "$PYTHON_BIN" "${build_vertex_args[@]}"
  run "$PYTHON_BIN" scripts/build_litellm_config.py --input "$VERTEX_POOL_FILE" --output "$LITELLM_OUTPUT_FILE"
  run "$PYTHON_BIN" scripts/check_project.py

  if [[ "$DRY_RUN" != "1" ]] && ! command -v docker >/dev/null 2>&1; then
    echo "[deploy] 缺少 docker 命令，无法继续部署" >&2
    exit 1
  fi

  run docker_compose pull
  run docker_compose up -d --build

  if [[ "$DRY_RUN" != "1" ]]; then
    retry "$HEALTHCHECK_ATTEMPTS" "$HEALTHCHECK_INTERVAL" curl --fail --silent --show-error -o /dev/null "$HEALTHCHECK_URL"
    if [[ -n "$PUBLIC_URL" ]]; then
      retry "$HEALTHCHECK_ATTEMPTS" "$HEALTHCHECK_INTERVAL" curl --fail --silent --show-error --head "$PUBLIC_URL"
    fi
    write_build_info
    echo "[deploy] 已写入版本信息：$APP_ROOT/build-info.json"
  fi

  echo "[deploy] 生产部署完成"
}

main "$@"
