# Reprocessamento automático do histórico financeiro

Ao iniciar esta versão, o sistema reconcilia automaticamente os lançamentos antigos sem exigir novo cadastro:

- Valores já recebidos salvos nos serviços passam a aparecer em **Recebido no mês**.
- Somente o saldo restante permanece em **A receber**.
- Gastos de ajudante/equipe já cadastrados são religados ao Financeiro sem duplicar lançamentos equivalentes.
- Lançamentos antigos marcados como pagos, mas sem data de baixa, recebem a data do próprio lançamento para entrar corretamente nos totais mensais.
- A rotina pode rodar em todo redeploy sem duplicar as entradas automáticas.
