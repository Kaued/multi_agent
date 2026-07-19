# Assistente AI

Interface de chat em Angular com respostas em streaming via SSE e suporte a Markdown.

## Executar

Com a API disponível em `http://127.0.0.1:5000`, rode:

```bash
npm install
npm start
```

Acesse `http://localhost:4200`. O servidor de desenvolvimento encaminha `/api` para a API local por meio do arquivo `proxy.conf.json`, evitando problemas de CORS.

## Integração

Cada mensagem faz um `POST` para `/api/v1/agent/stream`:

```json
{
  "thread_id": "conversation-1",
  "message": "Qual é o clima em São Paulo?"
}
```

O identificador da conversa é gerado automaticamente e guardado no `sessionStorage`: recarregar a mesma guia mantém a conversa, enquanto outra guia inicia com um novo `thread_id`.

A interface trata os eventos SSE `metadata`, `token`, `final`, `interrupt`, `error` e `done`. Tokens de agentes especialistas e de ferramentas não são exibidos como falas da IA. Eventos `interrupt` também descartam qualquer conteúdo intermediário, preservam os detalhes da operação, deixam a conversa aguardando a decisão do usuário e exibem as ações **Autorizar** e **Não autorizar**. Depois da decisão, a pergunta permanece no histórico como uma interação respondida. A decisão (ou uma resposta digitada) retoma o checkpoint na mesma conversa por meio do campo `resume`. Se a API responder com `checkpoint_requires_resume`, a solicitação é repetida uma única vez nesse formato.

Links presentes no Markdown da resposta são sanitizados pelo Angular, abertos em uma nova aba e apresentados como botões destacados.
