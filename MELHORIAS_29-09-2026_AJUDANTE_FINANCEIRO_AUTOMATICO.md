# Ajudante no Financeiro Automático — 29/09/2026

- Ao concluir um serviço com ajudante e valor definido, o sistema cria automaticamente um gasto **A pagar** no Financeiro.
- O lançamento fica vinculado ao serviço e ao ajudante.
- Ao dar baixa, passa a contar em **Gastos pagos** e no saldo do mês.
- Alterar o valor do ajudante em um serviço concluído atualiza o lançamento automático.
- Remover/trocar ajudante remove somente pendências automáticas ainda não pagas.
- Serviços antigos já concluídos são reprocessados no próximo deploy, sem duplicar lançamentos.
- O valor do ajudante não é marcado como pago automaticamente, pois valor combinado não significa pagamento realizado.
