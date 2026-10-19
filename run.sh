#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT="$SCRIPT_DIR"
BACKEND_DIR="$PROJECT/backend"
FRONTEND_DIR="$PROJECT/frontend"
BACKEND_PORT=8001
FRONTEND_PORT=5173

BACKEND_PID=""
FRONTEND_PID=""

pid_na_porta() {
    ss -ltnpH "sport = :$1" 2>/dev/null | grep -oE 'pid=[0-9]+' | head -n1 | cut -d= -f2 || true
}

cmdline_do() {
    tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null || true
}

matar_arvore() {
    local pid=$1 filho
    for filho in $(pgrep -P "$pid" 2>/dev/null || true); do
        matar_arvore "$filho"
    done
    kill "$pid" 2>/dev/null || true
}

esperar_porta_livre() {
    local porta=$1 tentativa
    for tentativa in $(seq 1 40); do
        [ -z "$(pid_na_porta "$porta")" ] && return 0
        sleep 0.25
    done
    return 1
}

liberar_porta() {
    local porta=$1 papel=$2 pid cmd
    pid=$(pid_na_porta "$porta")
    [ -z "$pid" ] && return 0
    cmd=$(cmdline_do "$pid")
    case "$cmd" in
        *"$PROJECT"*)
            echo "  :$porta ($papel) — instância anterior do Very Easy Calc (PID $pid), encerrando..."
            matar_arvore "$pid"
            if ! esperar_porta_livre "$porta"; then
                echo "ERRO: não consegui liberar a porta $porta."
                exit 1
            fi
            ;;
        *)
            echo "ERRO: porta $porta ($papel) está ocupada por OUTRO serviço (PID $pid):"
            echo "      $cmd"
            echo "      Nenhum processo foi encerrado. Encerre esse serviço manualmente"
            echo "      ou ajuste as portas no run.sh."
            exit 1
            ;;
    esac
}

encerrar_tudo() {
    trap - INT TERM EXIT
    echo
    echo "Encerrando Very Easy Calc..."
    [ -n "$FRONTEND_PID" ] && matar_arvore "$FRONTEND_PID"
    [ -n "$BACKEND_PID" ] && matar_arvore "$BACKEND_PID"
    wait 2>/dev/null || true
}

aguardar_http() {
    local url=$1 tentativa
    for tentativa in $(seq 1 60); do
        if curl -fsS -m 2 -o /dev/null "$url"; then
            return 0
        fi
        sleep 0.5
    done
    return 1
}

LAN_IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") {print $(i + 1); exit}}')

echo "======================================"
echo "       VERY EASY CALC"
echo "======================================"

if [ ! -x "$BACKEND_DIR/.venv/bin/uvicorn" ]; then
    echo "ERRO: uvicorn não encontrado em $BACKEND_DIR/.venv/bin/uvicorn"
    exit 1
fi

echo "[0/2] Verificando portas $BACKEND_PORT (backend) e $FRONTEND_PORT (frontend)..."
liberar_porta "$BACKEND_PORT" "backend"
liberar_porta "$FRONTEND_PORT" "frontend"

trap encerrar_tudo INT TERM EXIT

echo "[1/2] Iniciando backend (cwd: backend)..."
cd "$BACKEND_DIR"
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

echo "[2/2] Iniciando frontend (cwd: frontend)..."
cd "$FRONTEND_DIR"
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

echo
echo "Aguardando backend e frontend ficarem prontos..."
if ! aguardar_http "http://127.0.0.1:$BACKEND_PORT/api/health"; then
    echo "ERRO: backend não respondeu em http://127.0.0.1:$BACKEND_PORT/api/health."
    echo "      Confira a saída acima."
    exit 1
fi
if ! aguardar_http "http://127.0.0.1:$FRONTEND_PORT/"; then
    echo "ERRO: frontend não respondeu em http://127.0.0.1:$FRONTEND_PORT."
    echo "      Confira a saída acima."
    exit 1
fi

echo
echo "======================================"
echo " Backend (API):  http://localhost:$BACKEND_PORT"
echo " Frontend:       http://localhost:$FRONTEND_PORT"
if [ -n "$LAN_IP" ]; then
    echo "                 http://$LAN_IP:$FRONTEND_PORT   (rede local — mesma interface)"
fi
echo "                 O frontend repassa /api/* ao backend (proxy do Vite)."
echo "======================================"
echo
echo "Pressione Ctrl+C para encerrar."
echo

wait
