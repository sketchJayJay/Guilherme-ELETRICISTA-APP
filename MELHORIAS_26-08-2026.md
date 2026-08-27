# Melhorias 26/08/2026

- Push para o ajudante quando um serviço é atribuído ou alterado.
- Lembrete automático diário de serviços e tarefas às 07:00, configurável por ambiente.
- Botão para ativar notificações no celular do ajudante.
- Service Worker para notificações em PWA/iPhone/Android.
- Botão de WhatsApp no serviço para notificar o ajudante manualmente também.
- Campo de valor específico do ajudante em cada serviço.
- Ajudante vê somente a própria parte, com total de hoje e total concluído no mês.
- Orçamento para cliente ainda não cadastrado.
- Ao aprovar orçamento avulso, o cliente é cadastrado automaticamente.
- Migração automática de banco para as novas colunas, sem apagar dados existentes.

## Correção orçamento zerando ao salvar
- Corrigido caso em que o usuário preenchia apenas quantidade/unidade/valor e deixava a descrição do item vazia.
- A linha agora é salva normalmente e recebe automaticamente a descrição "Serviço" ou "Material".
- Adicionado total do orçamento em tempo real no formulário para conferir antes de salvar.
- Campos de quantidade/valor atualizam o total imediatamente no celular.

## PDF direto no WhatsApp
- Novo botão **PDF no WhatsApp** na tela do orçamento.
- O sistema gera o PDF real no servidor e, no smartphone/PWA, abre o compartilhamento nativo do iOS/Android com o arquivo anexado.
- Basta escolher **WhatsApp** e o contato do cliente.
- Em navegador sem suporte a compartilhamento de arquivos, o PDF é baixado como alternativa.
