# 🚀 Servidor MCP WhatsApp (Evolution API) — Streamable HTTP /mcp para Easypanel / VPS

Servidor MCP moderno utilizando o protocolo oficial **Streamable HTTP** no endpoint **`/mcp`**, enviando mensagens de WhatsApp pela **Evolution API v2**.

---

## 💎 Benefícios desta Arquitetura

1. **Protocolo Moderno:** Roda via **Streamable HTTP** (`/mcp`), padrão atual do Model Context Protocol.
2. **100% Configurado pelo Easypanel:** Credenciais da Evolution API e contatos dos Accounts são controlados exclusivamente pelas variáveis de ambiente do painel.
3. **Agendamento 24/7:** O servidor roda ininterruptamente na VPS, no fuso de Brasília. Dá pra agendar um envio e desligar o computador.
4. **"Pluga o Link e Plau":** É só colar a URL no Claude e ganhar as ferramentas 🔨.
5. **Seguro:** Token obrigatório na URL, nenhuma credencial no código. O servidor não sobe se faltar alguma variável.

---

## 🛠️ Passo a Passo no Easypanel

### 1. Criar o App
- No Easypanel, vá em **+ Service** ➔ **App**.
- Aponte para este repositório Git. O Easypanel detecta o `Dockerfile` automaticamente.

### 2. Porta e Domínio
- **Porta interna:** `8000`
- **Domínio (Domains):** adicione o subdomínio com HTTPS ligado.

### 3. Volume (para a fila de agendamentos sobreviver a deploys)
- Aba **Mounts** ➔ volume montado em `/data`.

### 4. Variáveis de Ambiente (Aba "Environment")

```env
MCP_TOKEN=SEU_TOKEN_SECRETO_AQUI
EVOLUTION_API_URL=https://sua-evolution.suaempresa.com.br
EVOLUTION_API_KEY=SUA_API_KEY_AQUI
EVOLUTION_INSTANCE=Nome da Instancia
ACCOUNTS=[{"id":"1","name":"Nome do Account 1","phone":"5511999999999","role":"Account Manager","aliases":["account1"]}]
```

Gerar um `MCP_TOKEN` forte: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

Clique em **Deploy**! 🚀

---

## 🌐 Teste de Saúde
`https://<seu-dominio>/health` (público, não expõe nomes nem telefones)

```json
{"status": "ok", "transport": "streamable-http", "endpoint": "/mcp", "provider": "evolution-api", "accounts_count": 2}
```

---

## 🔒 Conectando no Claude

```json
{
  "mcpServers": {
    "whatsapp-accounts": {
      "url": "https://<seu-dominio>/mcp?token=SEU_TOKEN_SECRETO_AQUI"
    }
  }
}
```

Ou via bridge (`npx mcp-remote`):
```json
{
  "mcpServers": {
    "whatsapp-accounts": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://<seu-dominio>/mcp?token=SEU_TOKEN_SECRETO_AQUI"]
    }
  }
}
```

---

## 🧪 Testes

```bash
MCP_URL=https://<seu-dominio> MCP_TOKEN=xxx python test_server.py
```

Para incluir um envio real (o número precisa estar conectado na instância):
```bash
MCP_URL=https://<seu-dominio> MCP_TOKEN=xxx TEST_PHONE=5585999999999 python test_server.py
```

---

## 🔨 Ferramentas Disponíveis no Claude

- `list_accounts()`: Lista os accounts cadastrados no Easypanel.
- `send_whatsapp(to, messages)`: Disparo imediato para contas ou telefone avulso.
- `schedule_whatsapp(to, run_at, messages)`: Agendamento 24/7 na VPS.
- `list_scheduled_messages()`: Consulta status da fila de agendamentos.
- `cancel_scheduled_message(job_id)`: Cancela agendamento.
