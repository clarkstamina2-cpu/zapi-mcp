"""
Suíte de testes do servidor MCP WhatsApp (Evolution API).

Uso:
  MCP_URL=http://localhost:8000 MCP_TOKEN=xxx python test_server.py
  Opcional:
    TEST_PHONE=5585999999999      -> faz um envio REAL (número precisa estar conectado na instância)
    EXPECT_SEND_FAILURE=1         -> espera que o envio real falhe com erro claro (ex: Evolution fora do ar)
"""
import asyncio
import os
import httpx
from fastmcp import Client

BASE = os.environ.get("MCP_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ["MCP_TOKEN"]
TEST_PHONE = os.environ.get("TEST_PHONE", "").strip()
EXPECT_SEND_FAILURE = os.environ.get("EXPECT_SEND_FAILURE") == "1"


def text_of(result) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


async def main():
    async with httpx.AsyncClient() as h:
        r = await h.get(f"{BASE}/health")
        assert r.status_code == 200, f"/health falhou: {r.status_code}"
        body = r.json()
        assert "accounts" not in body, "/health não deve expor nomes/telefones"
        print(f"OK  /health público -> {body}")
        r = await h.post(f"{BASE}/mcp", json={})
        assert r.status_code == 401, f"sem token deveria ser 401, veio {r.status_code}"
        print("OK  sem token -> 401")
        r = await h.post(f"{BASE}/mcp?token=errado", json={})
        assert r.status_code == 401, f"token errado deveria ser 401, veio {r.status_code}"
        print("OK  token errado -> 401")
        r = await h.post(f"{BASE}/mcp", json={}, headers={"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 401, f"token só no header deveria ser 401, veio {r.status_code}"
        print("OK  token só no header -> 401 (apenas ?token= é aceito)")

    async with Client(f"{BASE}/mcp?token={TOKEN}") as c:
        tools = {t.name for t in await c.list_tools()}
        expected = {"list_accounts", "send_whatsapp", "schedule_whatsapp", "list_scheduled_messages", "cancel_scheduled_message"}
        assert expected <= tools, f"tools faltando: {expected - tools}"
        print(f"OK  token certo -> tools: {sorted(tools)}")

        out = text_of(await c.call_tool("list_accounts", {}))
        assert "Accounts" in out or "Nenhum account" in out, out
        print("OK  list_accounts")

        out = text_of(await c.call_tool("send_whatsapp", {"to": "5511999999999", "messages": ["oi", "tudo bem?"], "dry_run": True}))
        assert "SIMULAÇÃO" in out and "✅" in out, out
        print("OK  send_whatsapp (dry_run, 2 mensagens)")

        out = text_of(await c.call_tool("send_whatsapp", {"to": "xyz", "messages": "oi", "dry_run": True}))
        assert "Nenhum destinatário válido" in out, out
        print("OK  send_whatsapp com destinatário inválido -> erro claro")

        out = text_of(await c.call_tool("schedule_whatsapp", {"to": "5511999999999", "run_at": "+2h", "messages": "teste agendado", "dry_run": True}))
        assert "agendamento(s) salvo(s)" in out, out
        job_id = out.split("ID: ")[1].split(" |")[0]
        print(f"OK  schedule_whatsapp -> {job_id}")

        out = text_of(await c.call_tool("schedule_whatsapp", {"to": "5511999999999", "run_at": "amanhã cedo", "messages": "x", "dry_run": True}))
        assert "Erro no formato do horário" in out, out
        print("OK  schedule_whatsapp com horário inválido -> erro claro")

        out = text_of(await c.call_tool("list_scheduled_messages", {}))
        assert job_id in out, out
        print("OK  list_scheduled_messages mostra o agendamento")

        out = text_of(await c.call_tool("cancel_scheduled_message", {"job_id": job_id}))
        assert "cancelado com sucesso" in out, out
        out = text_of(await c.call_tool("cancel_scheduled_message", {"job_id": job_id}))
        assert "não encontrado" in out, out
        print("OK  cancel_scheduled_message (e cancelar de novo -> erro claro)")

        if TEST_PHONE:
            out = text_of(await c.call_tool("send_whatsapp", {"to": TEST_PHONE, "messages": "✅ Teste do MCP WhatsApp (Evolution API)"}))
            if EXPECT_SEND_FAILURE:
                assert "❌ Falha" in out, out
                print("OK  envio real com Evolution indisponível -> falha reportada sem quebrar")
            else:
                assert "✅ Enviado" in out, out
                print(f"OK  envio REAL para {TEST_PHONE}")
        else:
            print("--  envio real NÃO testado (defina TEST_PHONE)")

    print("\nTODOS OS TESTES PASSARAM")


asyncio.run(main())
