#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zapi-mcp-easypanel — Servidor MCP Moderno (Streamable HTTP /mcp) para WhatsApp Z-API
Desenvolvido para VPS (Easypanel / Docker).
Utiliza transporte moderno Streamable HTTP no endpoint /mcp (substituto oficial do SSE legado).
Todas as credenciais e accounts são 100% configuráveis via Variáveis de Ambiente no Easypanel.
"""

import os
import sys
import json
import time
import asyncio
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP

# ==============================================================================
# CONFIGURAÇÃO DE LOGS
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("zapi-mcp")

# ==============================================================================
# VARIÁVEIS DE AMBIENTE (CONFIGURÁVEIS NO PAINEL DO EASYPANEL)
# ==============================================================================
ZAPI_INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN", "").strip()

PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")

DATA_DIR = os.getenv("DATA_DIR", "/data" if os.path.exists("/data") else os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(DATA_DIR, "scheduled_messages.json")

def get_zapi_endpoint() -> str:
    return f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"

# ==============================================================================
# GESTÃO DINÂMICA DE ACCOUNTS VIA VARIÁVEL DE AMBIENTE
# ==============================================================================
# Os accounts são lidos dinamicamente da variável de ambiente ACCOUNTS (JSON).
DEFAULT_ACCOUNTS_FALLBACK: List[Dict[str, Any]] = []

def load_accounts() -> List[Dict[str, Any]]:
    """Carrega os accounts exclusivamente a partir da variável ACCOUNTS do Easypanel."""
    raw = os.getenv("ACCOUNTS", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return list(parsed.values())
        except Exception as e:
            logger.error(f"Erro ao parsear ACCOUNTS da variável de ambiente: {e}")
    else:
        logger.warning("⚠️ Variável de ambiente ACCOUNTS não informada. Configure no painel do Easypanel.")
    return DEFAULT_ACCOUNTS_FALLBACK

def resolve_single_account(identifier: str) -> Optional[Dict[str, Any]]:
    raw = str(identifier).strip().lower()
    accounts = load_accounts()

    # 1. Busca por nome, ID ou alias
    for acc in accounts:
        if raw == str(acc.get("id")).lower():
            return acc
        if raw == acc.get("name", "").lower():
            return acc
        aliases = [str(a).lower() for a in acc.get("aliases", [])]
        if raw in aliases:
            return acc

    # 2. Busca por dígitos do telefone
    clean_digits = "".join(c for c in raw if c.isdigit())
    for acc in accounts:
        acc_phone = "".join(c for c in str(acc.get("phone", "")) if c.isdigit())
        if clean_digits and (clean_digits == acc_phone or acc_phone.endswith(clean_digits)):
            return acc

    # 3. Número de telefone avulso direto
    if len(clean_digits) >= 10:
        phone_fmt = clean_digits if clean_digits.startswith("55") else f"55{clean_digits}"
        return {
            "id": "custom",
            "name": f"Contato ({phone_fmt})",
            "phone": phone_fmt,
            "role": "Contato Personalizado"
        }

    return None

def resolve_recipients(targets: Union[str, List[str]]) -> List[Dict[str, Any]]:
    raw_list = []
    if isinstance(targets, str):
        raw_list = [p.strip() for p in targets.split(",") if p.strip()]
    elif isinstance(targets, list):
        for t in targets:
            raw_list.extend([p.strip() for p in str(t).split(",") if p.strip()])

    resolved = []
    seen = set()
    accounts = load_accounts()

    for item in raw_list:
        low = item.lower()
        if low in ("todos", "all", "ambos", "tudo", "os dois", "time"):
            for acc in accounts:
                phone = acc.get("phone")
                if phone not in seen:
                    seen.add(phone)
                    resolved.append(acc)
            continue

        acc = resolve_single_account(item)
        if acc:
            phone = acc.get("phone")
            if phone not in seen:
                seen.add(phone)
                resolved.append(acc)
        else:
            logger.warning(f"Destinatário não reconhecido: {item}")

    return resolved

# ==============================================================================
# DISPARO VIA Z-API (DOCUMENTAÇÃO OFICIAL)
# ==============================================================================
async def send_zapi_message(phone: str, message: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    POST https://api.z-api.io/instances/{instanceId}/token/{token}/send-text
    Headers: Client-Token e Content-Type: application/json
    Payload: {"phone": "...", "message": "...", "delayMessage": 2}
    """
    clean_phone = "".join(c for c in str(phone) if c.isdigit())
    if not clean_phone.startswith("55"):
        clean_phone = f"55{clean_phone}"

    if dry_run:
        logger.info(f"[DRY-RUN] Simulação de envio para {clean_phone}: {message[:40]}...")
        return {
            "success": True,
            "dry_run": True,
            "phone": clean_phone,
            "status": "SIMULATED"
        }

    if not ZAPI_INSTANCE_ID or not ZAPI_TOKEN or not ZAPI_CLIENT_TOKEN:
        err_msg = "Credenciais da Z-API incompletas. Configure ZAPI_INSTANCE_ID, ZAPI_TOKEN e ZAPI_CLIENT_TOKEN no Easypanel."
        logger.error(err_msg)
        return {"success": False, "phone": clean_phone, "error": err_msg}

    url = get_zapi_endpoint()
    headers = {
        "Client-Token": ZAPI_CLIENT_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "phone": clean_phone,
        "message": message.strip(),
        "delayMessage": 2  # Parâmetro oficial da Z-API para delay humanizado anti-ban
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            data = resp.json() if resp.content else {}
            is_ok = resp.status_code in (200, 201)
            if not is_ok:
                logger.error(f"Erro Z-API ({resp.status_code}): {data}")
            return {
                "success": is_ok,
                "status_code": resp.status_code,
                "phone": clean_phone,
                "response": data
            }
    except Exception as e:
        logger.error(f"Erro de conexão com Z-API: {e}")
        return {
            "success": False,
            "phone": clean_phone,
            "error": str(e)
        }

# ==============================================================================
# FILA DE AGENDAMENTOS NA VPS (EXECUTA 24/7 MESMO COM PC DESLIGADO)
# ==============================================================================
def _load_queue() -> List[Dict[str, Any]]:
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_queue(queue: List[Dict[str, Any]]):
    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erro ao salvar fila: {e}")

def parse_time_expression(expr: str) -> datetime:
    raw = expr.strip().lower()
    now = datetime.now()

    if raw.startswith("+"):
        unit = raw[-1]
        val = int(raw[1:-1])
        if unit == "m":
            return now + timedelta(minutes=val)
        elif unit == "h":
            return now + timedelta(hours=val)
        elif unit == "d":
            return now + timedelta(days=val)

    if any(w in raw for w in ("minuto", "minute", "min")):
        digits = "".join(c for c in raw if c.isdigit())
        if digits:
            return now + timedelta(minutes=int(digits))
    if any(w in raw for w in ("hora", "hour", "h")):
        digits = "".join(c for c in raw if c.isdigit())
        if digits:
            return now + timedelta(hours=int(digits))

    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            parsed_time = datetime.strptime(raw, fmt).time()
            target = datetime.combine(now.date(), parsed_time)
            if target <= now:
                target += timedelta(days=1)
            return target
        except ValueError:
            pass

    for fmt in (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S"
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass

    raise ValueError(f"Formato de horário não reconhecido: '{expr}'. Use '17:30', '+30m', '+2h' ou 'YYYY-MM-DD HH:MM'.")

async def _scheduler_loop():
    logger.info("Worker de agendamentos 24/7 iniciado na VPS.")
    while True:
        try:
            now = datetime.now()
            queue = _load_queue()
            dirty = False

            for job in queue:
                if job.get("status") == "PENDING":
                    target = datetime.strptime(job["scheduled_for"], "%Y-%m-%d %H:%M:%S")
                    if now >= target:
                        logger.info(f"Disparando agendamento {job['job_id']} para {job['recipient_name']}")
                        msgs = job.get("messages", [])
                        phone = job.get("phone")
                        dry_run = job.get("dry_run", False)

                        results = []
                        for idx, m in enumerate(msgs):
                            res = await send_zapi_message(phone, m, dry_run=dry_run)
                            results.append(res)
                            if idx < len(msgs) - 1:
                                await asyncio.sleep(2)

                        job["status"] = "SENT" if all(r.get("success") for r in results) else "FAILED"
                        job["executed_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
                        job["results"] = results
                        dirty = True

            if dirty:
                _save_queue(queue)

        except Exception as e:
            logger.error(f"Erro no loop do scheduler: {e}")

        await asyncio.sleep(5)

def start_scheduler_thread():
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_scheduler_loop())

    t = threading.Thread(target=run, daemon=True)
    t.start()

# ==============================================================================
# FASTMCP SERVER (STREAMABLE HTTP)
# ==============================================================================
mcp = FastMCP("zapi-whatsapp")

# Rotas operacionais e de Health Check para o Easypanel
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    accounts = load_accounts()
    return JSONResponse({
        "status": "healthy",
        "transport": "streamable-http",
        "endpoint": "/mcp",
        "instance_configured": bool(ZAPI_INSTANCE_ID),
        "accounts_count": len(accounts),
        "accounts": [f"{a.get('name')} ({a.get('phone')})" for a in accounts]
    })

@mcp.custom_route("/", methods=["GET"])
async def root_view(request: Request) -> JSONResponse:
    return JSONResponse({
        "service": "Z-API WhatsApp MCP Server",
        "protocol": "Streamable HTTP",
        "mcp_endpoint": "/mcp",
        "health": "/health",
        "docs": "Conecte o Claude Desktop informando a URL terminando com /mcp"
    })

# Ferramentas do MCP
@mcp.tool()
def list_accounts() -> str:
    """Lista todos os accounts configurados no sistema (lidos das variáveis do Easypanel)."""
    accounts = load_accounts()
    lines = ["📋 Accounts Cadastrados no Easypanel:"]
    for acc in accounts:
        lines.append(f"• [{acc.get('id')}] {acc.get('name')} — WhatsApp: {acc.get('phone')} ({acc.get('role', 'Account')})")
    return "\n".join(lines)

@mcp.tool()
async def send_whatsapp(
    to: Union[str, List[str]],
    messages: Union[str, List[str]],
    dry_run: bool = False
) -> str:
    """
    Envia uma ou mais mensagens imediatas via WhatsApp Z-API.
    
    Args:
        to: Destinatário(s). Aceita 'junior', 'jorge', 'todos' (para ambos), lista ['junior', 'jorge'] ou número de WhatsApp.
        messages: Mensagem única de texto ou lista de mensagens sequenciais (balões separados).
        dry_run: Se True, apenas simula o envio sem disparar no WhatsApp real.
    """
    recipients = resolve_recipients(to)
    if not recipients:
        return f"❌ Erro: Nenhum destinatário válido encontrado para '{to}'."

    msg_list = [messages] if isinstance(messages, str) else [str(m) for m in messages]
    total_msgs = 0
    results_summary = []

    for r_idx, acc in enumerate(recipients):
        acc_name = acc.get("name")
        phone = acc.get("phone")
        acc_res = []

        for m_idx, msg in enumerate(msg_list):
            res = await send_zapi_message(phone, msg, dry_run=dry_run)
            acc_res.append(res)
            total_msgs += 1
            if m_idx < len(msg_list) - 1:
                await asyncio.sleep(2)

        ok = all(r.get("success") for r in acc_res)
        results_summary.append(f"• {acc_name} ({phone}): {'✅ Enviado' if ok else '❌ Falha'}")
        if r_idx < len(recipients) - 1:
            await asyncio.sleep(2)

    mode = " (SIMULAÇÃO / DRY-RUN)" if dry_run else ""
    return (
        f"🚀 Disparo finalizado{mode}!\n"
        f"Total de mensagens: {total_msgs}\n"
        f"Status:\n" + "\n".join(results_summary)
    )

@mcp.tool()
def schedule_whatsapp(
    to: Union[str, List[str]],
    run_at: str,
    messages: Union[str, List[str]],
    dry_run: bool = False
) -> str:
    """
    Agenda uma ou mais mensagens para envio em horário futuro na VPS.
    O agendamento roda 24/7 na VPS, funcionando mesmo se o computador do usuário estiver desligado.
    
    Args:
        to: Destinatário(s) ('junior', 'jorge', 'todos', etc.).
        run_at: Horário ou expressão futura (ex: '17:30', '+30m', '+2h', 'YYYY-MM-DD HH:MM').
        messages: Mensagem única ou lista de mensagens sequenciais.
        dry_run: Se True, simula o agendamento.
    """
    recipients = resolve_recipients(to)
    if not recipients:
        return f"❌ Erro: Nenhum destinatário válido para '{to}'."

    try:
        target_dt = parse_time_expression(run_at)
    except Exception as e:
        return f"❌ Erro no formato do horário: {e}"

    now = datetime.now()
    if target_dt <= now:
        return f"❌ O horário ({target_dt.strftime('%d/%m/%Y %H:%M')}) precisa ser no futuro."

    msg_list = [messages] if isinstance(messages, str) else [str(m) for m in messages]
    queue = _load_queue()
    scheduled = []

    for acc in recipients:
        job_id = f"job_{now.strftime('%Y%m%d_%H%M%S')}_{acc.get('name', 'user').lower()}_{os.urandom(2).hex()}"
        job = {
            "job_id": job_id,
            "recipient_name": acc.get("name"),
            "phone": acc.get("phone"),
            "messages": msg_list,
            "scheduled_for": target_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "PENDING",
            "dry_run": dry_run
        }
        queue.append(job)
        scheduled.append(job)

    _save_queue(queue)

    lines = [f"🕒 {len(scheduled)} agendamento(s) salvo(s) na VPS!"]
    for j in scheduled:
        lines.append(f"• ID: {j['job_id']} | Para: {j['recipient_name']} ({j['phone']}) | Previsto: {j['scheduled_for']}")
    lines.append("\n💡 Como o servidor roda na VPS, a mensagem será enviada pontualmente mesmo se o seu PC estiver desligado.")
    return "\n".join(lines)

@mcp.tool()
def list_scheduled_messages() -> str:
    """Lista todos os agendamentos registrados na fila da VPS com status."""
    queue = _load_queue()
    if not queue:
        return "📅 Nenhum agendamento pendente na fila da VPS."
    lines = [f"📅 Fila de Agendamentos na VPS ({len(queue)} registros):"]
    for j in queue:
        lines.append(f"• [{j.get('status')}] ID: {j.get('job_id')} | Para: {j.get('recipient_name')} | Previsto: {j.get('scheduled_for')}")
    return "\n".join(lines)

@mcp.tool()
def cancel_scheduled_message(job_id: str) -> str:
    """Cancela um agendamento pendente na VPS usando o seu ID (job_id)."""
    queue = _load_queue()
    found = False
    for j in queue:
        if j.get("job_id") == job_id.strip() and j.get("status") == "PENDING":
            j["status"] = "CANCELLED"
            j["cancelled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            found = True
    if found:
        _save_queue(queue)
        return f"✅ Agendamento '{job_id}' cancelado com sucesso na VPS."
    return f"❌ Agendamento '{job_id}' não encontrado ou já executado."

# ==============================================================================
# INICIALIZAÇÃO VIA STREAMABLE HTTP (/mcp)
# ==============================================================================
if __name__ == "__main__":
    start_scheduler_thread()
    logger.info(f"Iniciando Z-API MCP Server (Streamable HTTP) em http://{HOST}:{PORT}/mcp")
    mcp.run(
        transport="http",
        host=HOST,
        port=PORT,
        path="/mcp"
    )
