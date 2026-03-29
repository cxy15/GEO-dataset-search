#!/usr/bin/env bash
# GEO 数据检索：配置 API → 自然语言/手工检索式 → 推荐报告（全程日志可追溯）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PY="${SCRIPT_DIR}/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "错误：未找到 ${SCRIPT_DIR}/.venv/bin/python，请先创建虚拟环境并安装依赖。" >&2
  exit 1
fi

ENV_FILE="${SCRIPT_DIR}/.env"
EXAMPLE="${SCRIPT_DIR}/.env.example"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*"; }
section() {
  echo ""
  echo "========== [$(ts)] $* =========="
}

write_env_kv() {
  local key="$1"
  local val="$2"
  local tmp
  tmp="$(mktemp)"
  if [[ -f "$ENV_FILE" ]]; then
    grep -v "^[[:space:]]*${key}=" "$ENV_FILE" >"$tmp" || true
    mv "$tmp" "$ENV_FILE"
  else
    : >"$ENV_FILE"
  fi
  printf '%s=%q\n' "$key" "$val" >>"$ENV_FILE"
  chmod 600 "$ENV_FILE" 2>/dev/null || true
}

load_dotenv() {
  if [[ ! -f "$ENV_FILE" ]]; then
    return 0
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

prompt_if_empty() {
  local var_name="$1"
  local prompt_text="$2"
  local secret="${3:-0}"
  local current="${!var_name-}"
  if [[ -n "${current// /}" ]]; then
    return 0
  fi
  if [[ "$secret" == "1" ]]; then
    read -r -s -p "${prompt_text}" input
    echo
  else
    read -r -p "${prompt_text}" input
  fi
  if [[ -z "${input// /}" ]]; then
    echo "错误：${var_name} 不能为空。" >&2
    exit 1
  fi
  printf -v "$var_name" '%s' "$input"
  write_env_kv "$var_name" "${!var_name}"
  export "$var_name"
}

if [[ ! -f "$ENV_FILE" ]] && [[ -f "$EXAMPLE" ]]; then
  log "未找到 .env，从 .env.example 复制..."
  cp "$EXAMPLE" "$ENV_FILE"
  chmod 600 "$ENV_FILE" 2>/dev/null || true
fi

load_dotenv

if [[ "${ENTREZ_EMAIL:-}" == *"your_email"* ]] || [[ "${ENTREZ_EMAIL:-}" == "your_email@example.com" ]]; then
  ENTREZ_EMAIL=""
fi
if [[ "${OPENAI_API_KEY:-}" == "sk-..." ]]; then
  OPENAI_API_KEY=""
fi

section "环境与 API 配置"
log "检查 NCBI 联系信息与 LLM 配置..."

prompt_if_empty ENTREZ_EMAIL "请输入 NCBI E-utilities 联系邮箱 ENTREZ_EMAIL（政策要求，非 API Key）: " 0

if [[ -z "${NCBI_API_KEY:-}" ]]; then
  echo ""
  echo "说明：NCBI_API_KEY 可选；请求会附带 api_key=…，用于提高速率。"
  read -r -p "输入 NCBI API Key（可选，回车跳过）: " _nk
  if [[ -n "${_nk// /}" ]]; then
    NCBI_API_KEY="$_nk"
    write_env_kv NCBI_API_KEY "$NCBI_API_KEY"
    export NCBI_API_KEY
  fi
fi

prompt_if_empty OPENAI_API_KEY "请输入兼容服务的密钥 OPENAI_API_KEY（Bearer，输入不回显）: " 1

if [[ -z "${OPENAI_BASE_URL:-}" ]]; then
  echo ""
  read -r -p "OPENAI_BASE_URL [回车默认 https://api.openai.com/v1]: " _base
  if [[ -n "${_base// /}" ]]; then
    OPENAI_BASE_URL="$_base"
    write_env_kv OPENAI_BASE_URL "$OPENAI_BASE_URL"
    export OPENAI_BASE_URL
  else
    export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
    log "使用默认 OPENAI_BASE_URL=${OPENAI_BASE_URL}"
  fi
fi

if [[ -z "${OPENAI_MODEL:-}" ]]; then
  read -r -p "模型名称 [回车默认 gpt-4o-mini]: " _model
  if [[ -n "${_model// /}" ]]; then
    OPENAI_MODEL="$_model"
    write_env_kv OPENAI_MODEL "$OPENAI_MODEL"
    export OPENAI_MODEL
  else
    export OPENAI_MODEL="${OPENAI_MODEL:-gpt-4o-mini}"
    log "使用默认 OPENAI_MODEL=${OPENAI_MODEL}"
  fi
fi

log "配置就绪。"

section "检索参数"
RETMAX_DEFAULT="40"
read -r -p "单次检索最大条数 retmax [默认 ${RETMAX_DEFAULT}]: " _retmax
RETMAX="${_retmax:-$RETMAX_DEFAULT}"

OUT_DEFAULT="geo_report_$(date '+%Y%m%d_%H%M%S').txt"
read -r -p "输出报告路径 [默认 ${OUT_DEFAULT}]: " _out
OUTPUT_REPORT="${_out:-$OUT_DEFAULT}"

echo ""
echo "说明：默认开启对 NCBI GEO HTTPS 的远程文件探测（HEAD）；关闭可加速但可用性判断变弱。"
read -r -p "关闭远程探测? [y/N]: " _nop

section "检索意图与检索式"
echo "  - 可输入自然语言研究需求；或填写手工 gds 检索式（等价 -q）。"
read -r -p "研究意图（必填，将用于相关性与最终报告）: " USER_INTENT
if [[ -z "${USER_INTENT// /}" ]]; then
  echo "错误：研究意图不能为空。" >&2
  exit 1
fi
read -r -p "手工 gds 检索式（可选，回车则根据上一行由 LLM 生成）: " RAW_Q

ARGS=("-n" "$RETMAX" "-o" "$OUTPUT_REPORT")
if [[ "$_nop" =~ ^[yY]$ ]]; then
  ARGS+=(--no-probe)
fi
if [[ -n "${RAW_Q// /}" ]]; then
  ARGS+=("-q" "$RAW_Q")
fi
ARGS+=("$USER_INTENT")

PIPELINE_HINT=$'  A) （若未选手工检索式）LLM：自然语言 → gds 检索式\n  B) 打印「实际用于检索的 gds 表达式（完整）」\n  C) NCBI：esearch + esummary\n  D) （默认）HTTPS HEAD：矩阵/SOFT 可用性标注\n  E) LLM：相关性分级 + 中文数据推荐报告\n  F) 写入 UTF-8 文本报告与 logs/ 快照\n  G) （终端交互时）输入 GSE 编号 → LLM 解读 → 可选下载至 downloads/（输入 q 退出）'

mkdir -p "${SCRIPT_DIR}/logs"
LOG_FILE="${SCRIPT_DIR}/logs/run_$(date '+%Y%m%d_%H%M%S').log"

section "即将执行的流水线"
echo "$PIPELINE_HINT"

section "启动 Python"
log "命令: $VENV_PY -u -m geo_reporter ${ARGS[*]}"
log "日志文件: $LOG_FILE"
echo "----------"

set +e
"$VENV_PY" -u -m geo_reporter "${ARGS[@]}" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e

echo "----------"
section "运行结束"
if [[ "$EXIT_CODE" -eq 0 ]]; then
  log "任务成功结束 (exit 0)。"
else
  log "任务失败，退出码: $EXIT_CODE（详见日志：$LOG_FILE）。"
fi

exit "$EXIT_CODE"
