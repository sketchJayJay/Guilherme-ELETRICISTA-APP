# Melhorias 27/08/2026

## Enviar serviço direto para o ajudante
- Na tela do serviço existe agora o bloco **Enviar serviço para o ajudante**.
- O Guilherme escolhe o ajudante, informa somente o valor que será pago a ele e toca em **Enviar serviço para o ajudante**.
- O serviço aparece imediatamente na área **Meu dia** do ajudante.
- O sistema cria um aviso interno e tenta enviar a notificação push sem travar a página.
- Se o mesmo serviço já estiver atribuído ao ajudante, o botão atualiza o valor e reenvia o aviso.
- Ao aprovar um orçamento, também é possível escolher o ajudante e o valor dele antes de tocar em **Aprovar e criar serviço**.
- Orçamentos já convertidos mostram um atalho **Enviar para o ajudante**.

## Pagamento em um clique
- Serviços pendentes agora mostram **✓ Pago** diretamente na listagem.
- Na tela do serviço existe **✓ Dar como pago agora**.
- O clique marca o valor total como recebido e sincroniza o lançamento no Financeiro.
- Pagamento parcial continua disponível em uma área separada.

## Correção de tarefas da equipe
- O envio da tarefa foi reorganizado para salvar a tarefa primeiro.
- Falha de push ou serviço externo não derruba mais a página nem perde a tarefa.
- O push agora é disparado em segundo plano para o celular não ficar esperando a resposta do serviço de notificação.
- Foram adicionados tratamento de erro e rollback para evitar tela de erro em problemas de banco/notificação.
- Inscrições push inválidas são tratadas sem interromper a operação do sistema.
