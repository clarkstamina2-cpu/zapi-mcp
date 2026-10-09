# 🚀 Servidor MCP Z-API (Streamable HTTP /mcp) para Easypanel / VPS

Servidor MCP moderno utilizando o protocolo oficial **Streamable HTTP** no endpoint **`/mcp`** (substituindo o antigo padrão SSE legado).

---

## 💎 Benefícios desta Arquitetura

1. **Protocolo Moderno:** Roda via **Streamable HTTP** (`/mcp`), padrão atual e de alta performance do Model Context Protocol.
2. **100% Configurado pelo Easypanel:** Credenciais da Z-API e contatos dos Accounts são controlados exclusivamente pelas variáveis de ambiente do painel. Adicionar um novo account no futuro leva 5 segundos.
3. **Agendamento 24/7:** O servidor roda ininterruptamente na VPS. O chefe pode agendar um envio e desligar o computador que a mensagem é disparada pontualmente.
4. **"Pluga o Link e Plau":** O chefe só cola a URL no Claude Desktop e ganha as ferramentas nativas 🔨.
5. **Seguro para Git:** Código 100% limpo, sem nenhum token ou telefone real hardcoded.

---

## 🛠️ Passo a Passo no Easypanel

### 1. Criar o App
- No seu Easypanel, vá em **+ Service** ➔ **App** (ex: `zapi-mcp`).
- Aponte para o repositório Git ou faça upload da pasta `zapi-mcp-easypanel`. O Easypanel detectará o `Dockerfile` automaticamente.

### 2. Porta e Domínio
- **Porta interna:** `8000`
- **Domínio (Domains):** Adicione seu subdomínio (ex: `zapi.suaempresa.com.br`). O Easypanel gera o SSL (HTTPS) automaticamente.

### 3. Variáveis de Ambiente (Aba "Environment")
Cole estas variáveis preenchendo com os seus dados reais:

```env
PORT=8000
HOST=0.0.0.0
ZAPI_INSTANCE_ID=SEU_INSTANCE_ID_AQUI
ZAPI_TOKEN=SEU_TOKEN_AQUI
ZAPI_CLIENT_TOKEN=SEU_CLIENT_TOKEN_AQUI

# Camada de Segurança (Token secreto para barrar acessos não autorizados)
MCP_AUTH_TOKEN=SEU_TOKEN_SECRETO_AQUI

ACCOUNTS=[{"id":"1","name":"Nome do Account 1","phone":"5511999999999","role":"Account Manager","aliases":["account1"]},{"id":"2","name":"Nome do Account 2","phone":"5511888888888","role":"Account Manager","aliases":["account2"]}]
```

Clique em **Deploy**! 🚀

---

## 🌐 Teste de Saúde
Acesse no seu navegador:  
`https://zapi.suaempresa.com.br/health`

Resposta esperada:
```json
{
  "status": "healthy",
  "transport": "streamable-http",
  "endpoint": "/mcp",
  "auth_enabled": true,
  "instance_configured": true,
  "accounts_count": 2,
  "accounts": ["Nome 1 (5511999999999)", "Nome 2 (5511888888888)"]
}
```

---

## 🔒 Como o seu Chefe se Conecta com Segurança

Você pode fornecer o acesso de duas formas super fáceis:

### Opção 1: Via URL com Token (O jeito mais prático - "Pluga o link e plau")
O chefe só cola a URL com o token no `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "whatsapp-accounts": {
      "url": "https://zapi.suaempresa.com.br/mcp?token=SEU_TOKEN_SECRETO_AQUI"
    }
  }
}
```

### Opção 2: Via Header de Autorização Bearer
```json
{
  "mcpServers": {
    "whatsapp-accounts": {
      "url": "https://zapi.suaempresa.com.br/mcp",
      "headers": {
        "Authorization": "Bearer SEU_TOKEN_SECRETO_AQUI"
      }
    }
  }
}
```

### Opção 3: Conexão via Bridge Universal (npx mcp-remote)
```json
{
  "mcpServers": {
    "whatsapp-accounts": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://zapi.suaempresa.com.br/mcp?token=SEU_TOKEN_SECRETO_AQUI"]
    }
  }
}
```

---

## 🔨 Ferramentas Disponíveis no Claude:

- `list_accounts()`: Lista os accounts cadastrados no Easypanel.
- `send_whatsapp(to, messages)`: Disparo imediato para contas ou telefone avulso.
- `schedule_whatsapp(to, run_at, messages)`: Agendamento 24/7 na VPS.
- `list_scheduled_messages()`: Consulta status da fila de agendamentos.
- `cancel_scheduled_message(job_id)`: Cancela agendamento.
