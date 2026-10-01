# Ajudante x Financeiro V2 — 01/10/2026

Correção para o valor do ajudante não ficar apenas dentro do serviço/lucro e não aparecer corretamente no Financeiro.

## O que mudou
- A atribuição do ajudante agora guarda também a situação do pagamento: **Já paguei** ou **Ainda vou pagar**.
- O valor do ajudante é sincronizado com o Financeiro assim que é salvo:
  - **Já paguei** -> entra em **Gastos**.
  - **Ainda vou pagar** -> entra em **A pagar**.
- Não depende mais exclusivamente de o serviço estar concluído para criar o lançamento financeiro.
- Ao dar baixa pelo Financeiro ou pela área da equipe, a situação também fica gravada na atribuição do serviço para não voltar ao estado anterior em sincronizações futuras.
- Na primeira inicialização desta versão, instalações antigas recebem a nova coluna automaticamente.
- Para preservar o fluxo que vinha sendo usado, valores de ajudante de serviços antigos já concluídos são migrados como **pagos** e entram no mês do serviço, sem exigir novo lançamento.
- A sincronização continua idempotente, evitando duplicar o lançamento automático a cada redeploy.

## Tela do serviço
Agora o cadastro mostra claramente a situação do pagamento do ajudante e informa onde o valor aparecerá no Financeiro.
