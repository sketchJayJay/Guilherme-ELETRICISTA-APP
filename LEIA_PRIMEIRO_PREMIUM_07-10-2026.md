# Guilherme Elétrica e Climatização — versão Executive

Atualização de 07/10/2026.

## O que melhorou

- Nova identidade visual com azul escuro, detalhes dourados, ícones consistentes e telas adaptadas ao celular.
- Painel com faturamento, recebimentos, gastos, lucro, saldo a receber, agenda do dia e próximos atendimentos.
- Movimento dos últimos sete dias e situação dos serviços calculados com os registros existentes.
- Indicadores financeiros de percentual recebido, margem do mês e peso dos gastos, além de barras por categoria.
- Busca por clientes, telefone, serviços e orçamentos. No computador, use Ctrl+K ou Command+K.
- Menu Novo com atalhos para serviço, orçamento, cliente e gasto.
- Listas em cartões no celular, filtros por situação e ações de cliente agrupadas em Mais.
- Navegação entre períodos da agenda, retorno para hoje e destaque verde nos dias concluídos.
- Cartões do financeiro abrem os itens que compõem o valor. A seta Voltar continua nas telas internas.
- O total do orçamento é atualizado imediatamente ao remover um item.
- Login redesenhado, opção de mostrar senha e melhorias de foco e identificação dos campos.
- Arquivo principal app.py recuperado da versão correspondente ao pacote enviado.

## Como ler o financeiro

O painel inicial usa o mesmo fechamento mensal da tela Financeiro:

- Faturado: total dos serviços com data no mês, excluindo os cancelados.
- Recebido: valores recebidos desses mesmos serviços.
- Gastos: despesas pagas e pendentes do mês.
- Lucro: faturado menos gastos.
- A receber: diferença entre o total dos serviços e o valor recebido.
- Caixa realizado: recebido dos serviços menos despesas pagas.

Recebimentos avulsos continuam disponíveis nos lançamentos e no aviso de conferência. Os percentuais aparecem como “—” quando não existe faturamento no mês.

## Atualizar a instalação existente no Coolify

1. No sistema atual, abra Configurações e baixe o backup.
2. Extraia o ZIP e abra a pasta guilherme_eletricista_system.
3. Atualize os arquivos do mesmo repositório que já está vinculado ao aplicativo, incluindo app.py, templates e static. Dockerfile e docker-compose.yaml ficam na raiz desse repositório.
4. Mantenha o mesmo recurso do Coolify, o volume existente montado em /data e a SECRET_KEY atual.
5. Faça o redeploy. Este sistema usa a porta 5000 e a rota /health.
6. Entre com o usuário e a senha existentes. No celular, feche o aplicativo e abra novamente para carregar o visual atualizado.

O banco continua em /data/guilherme_eletrica.db. Fotos e assinaturas continuam em /data/uploads. O pacote contém a aplicação e a documentação; os dados de demonstração usados na revisão não fazem parte da instalação.

Para uma instalação nova, siga COOLIFY_PASSO_A_PASSO.md. O cadastro inicial de usuário é feito na tela Primeiro acesso.

## Verificações realizadas

- 37 páginas e formulários renderizados, mais as telas do ajudante.
- PDF de ordem de serviço, orçamento e resumo mensal.
- Cadastro com dia 31 e baixa de pagamento.
- Busca, proteção da área do administrador e consistência dos números mensais.
- Revisão no navegador em larguras de 360, 390, 768, 1024 e 1440 pixels.
- Atalhos, menu do celular, busca por teclado, cartões clicáveis e recálculo dos itens do orçamento.

As imagens na pasta PREVIAS mostram dados fictícios usados na revisão do visual.
