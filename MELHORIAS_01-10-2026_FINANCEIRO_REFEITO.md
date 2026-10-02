# Financeiro V3 — refeito para caixa real e pendências

Objetivo: parar de depender de lançamentos duplicados/manuais e fazer Serviço, Ajudante e Financeiro conversarem entre si.

## Regra nova

- Dinheiro recebido do cliente = Entrada paga no caixa.
- Parte ainda não recebida = A receber.
- Ajudante marcado como pago = Saída paga no caixa na data do pagamento.
- Ajudante ainda não pago = A pagar.
- Lançamentos manuais ficam somente para despesas/receitas avulsas.
- Serviço cancelado não continua gerando cobrança pendente.

## Correções estruturais

- Financeiro reconcilia automaticamente serviços e gastos da equipe ao abrir.
- Tela inicial usa o mesmo livro-caixa do Financeiro.
- Lançamentos pagos são filtrados pela data real de pagamento; pendências pelo vencimento.
- Pendências vencidas de meses anteriores aparecem no resumo do mês atual.
- Origem de cada lançamento aparece como Serviço, Ajudante ou Manual.
- Novo botão “Conferir agora” reprocessa o livro-caixa de forma idempotente.
- Pagamento do ajudante ganhou data real de baixa.
- Botão direto no serviço para “Marcar como pago” / “Voltar para A pagar”.
- Conversão de orçamento para serviço agora também sincroniza o valor do ajudante.
- Histórico antigo recebe identificação de origem e datas faltantes são recuperadas.
- Proteção contra duplicação dos lançamentos automáticos da equipe.

## Migração automática

As colunas novas são criadas automaticamente no banco existente durante o redeploy. O banco em /data continua sendo reutilizado; não é necessário apagar nem recriar o volume.
