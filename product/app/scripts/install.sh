#!/usr/bin/env bash

# app 子系统安装脚本。
#
# 职责：
# - 安装后端和前端依赖。
# - 初始化私密配置模板。
# - 保持与顶层安装入口兼容。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/product/app/backend"
FRONTEND_DIR="$ROOT_DIR/product/app/frontend"
PRIVATE_CONFIG="$ROOT_DIR/product/app/config/private.local.toml"
PRIVATE_CONFIG_EXAMPLE="$ROOT_DIR/product/app/config/private.local.toml.example"
CHECKER="$ROOT_DIR/product/app/backend/infrastructure/deployment_checks.py"

info() {
  printf '\033[1;32m%s\033[0m\n' "$1"
}

warn() {
  printf '\033[1;33m%s\033[0m\n' "$1"
}

error() {
  printf '\033[1;31m错误：%s\033[0m\n' "$1" >&2
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

ensure_node_runtime() {
  if command_exists node && command_exists npm; then
    return
  fi

  if [ -s "$HOME/.nvm/nvm.sh" ]; then
    # shellcheck disable=SC1090
    . "$HOME/.nvm/nvm.sh"
    nvm install 22 >/dev/null
    nvm use 22 >/dev/null
    return
  fi

  if command_exists brew; then
    brew install node@22
    export PATH="$(brew --prefix node@22)/bin:$PATH"
    return
  fi

  error "未找到 node/npm，且没有可用的 nvm 或 brew。请先安装 Node.js 22 及以上版本。"
  exit 1
}

ensure_private_config_template() {
  if [ -f "$PRIVATE_CONFIG" ]; then
    info "已存在私密配置文件：$PRIVATE_CONFIG"
    return
  fi

  if [ -f "$PRIVATE_CONFIG_EXAMPLE" ]; then
    cp "$PRIVATE_CONFIG_EXAMPLE" "$PRIVATE_CONFIG"
    info "已初始化私密配置模板：$PRIVATE_CONFIG"
    return
  fi

  cat >"$PRIVATE_CONFIG" <<'EOF'
# 本地私密配置文件
#
# 该文件用于独立部署时保存 SMTP 密码、MySQL 账号和模型/数据源密钥。
# 已被 `.gitignore` 忽略，不会提交到远端仓库。

[smtp]
password = ""

[secrets]
deepseek_api_key = ""
tushare_token = ""

[mysql]
user = ""
password = ""
EOF
  info "已初始化私密配置模板：$PRIVATE_CONFIG"
}

show_detection_summary() {
  info "正在检测安装条件…"

  if command_exists python3; then
    printf '  [OK] python3\n'
  else
    printf '  [缺失] python3\n'
  fi

  if command_exists git; then
    printf '  [OK] git\n'
  else
    printf '  [缺失] git\n'
  fi

  if command_exists node && command_exists npm; then
    printf '  [OK] node/npm\n'
  else
    printf '  [缺失] node/npm\n'
  fi

  if [ -f "$PRIVATE_CONFIG" ]; then
    printf '  [OK] private.local.toml\n'
  else
    printf '  [缺失] private.local.toml\n'
  fi

  if command_exists docker && docker compose version >/dev/null 2>&1; then
    printf '  [OK] docker compose\n'
  elif command_exists mysql.server; then
    printf '  [OK] mysql.server\n'
  elif command_exists brew; then
    printf '  [提示] brew 可用，但需要确认已安装 mysql@8.0 或 mysql\n'
  else
    printf '  [缺失] MySQL runtime\n'
  fi
}

confirm_install() {
  printf '\n'
  read -r -p "是否继续安装缺失依赖并初始化私密配置模板？[y/N] " answer
  case "${answer:-}" in
    y|Y)
      return 0
      ;;
    *)
      warn "用户取消安装。"
      exit 1
      ;;
  esac
}

install_backend() {
  if [ ! -x "$BACKEND_DIR/.venv/bin/python" ]; then
    info "正在创建后端 Python 虚拟环境…"
    python3 -m venv "$BACKEND_DIR/.venv"
  fi

  info "正在安装后端依赖…"
  "$BACKEND_DIR/.venv/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"
}

install_frontend() {
  ensure_node_runtime
  info "正在安装前端依赖…"
  (cd "$FRONTEND_DIR" && npm install)
}

post_install_check() {
  info "正在校验安装结果…"
  if ! "$BACKEND_DIR/.venv/bin/python" "$CHECKER" backend-deps --python "$BACKEND_DIR/.venv/bin/python"; then
    error "后端依赖校验未通过。"
    exit 1
  fi

  if ! python3 "$CHECKER" frontend-deps --frontend-dir "$FRONTEND_DIR"; then
    error "前端依赖校验未通过。"
    exit 1
  fi

  if ! python3 "$CHECKER" private-config --config "$PRIVATE_CONFIG"; then
    warn "私密配置仍有空值或缺项，请补齐后再执行 start.sh。"
  else
    info "私密配置校验通过。"
  fi
}

show_detection_summary
confirm_install
ensure_private_config_template
install_backend
install_frontend
post_install_check

printf '\n'
info "安装完成。"
printf '  下一步请先填写：%s\n' "$PRIVATE_CONFIG"
printf '  如需启动 MySQL，请先准备本地运行时或 Docker Compose。\n'
printf '  然后执行：%s\n' "$ROOT_DIR/product/scripts/start.sh"
