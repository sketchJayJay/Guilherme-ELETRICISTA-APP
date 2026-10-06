# Financeiro reconstruído — 06/10/2026

- Faturamento mensal agora vem diretamente dos serviços cadastrados no mês, e não depende de lançamento financeiro automático.
- O total de cada serviço antigo é recalculado no redeploy antes da reconciliação.
- Gastos do mês consideram pagos + pendentes, permitindo calcular lucro real por competência.
- Novos cards: Faturado, Gastos do mês, Lucro, Recebido, A receber, A pagar e Caixa realizado.
- Todos os cards abrem os itens que formam o valor.
- PDF mensal passa a listar serviço por serviço e gasto por gasto.
- Adicionado botão “Conferir financeiro” para forçar reconciliação do histórico.
- Corrigida duplicidade histórica quando a mesma diária do ajudante foi lançada manualmente e também criada automaticamente pelo serviço.
- A reconciliação preserva o mesmo banco em /data e é idempotente.
