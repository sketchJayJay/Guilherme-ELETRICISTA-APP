# Guilherme Elétrica

Sistema web responsivo para a rotina de um eletricista, pensado em **serviços por dia**, com horário opcional e cronômetro quando o trabalho for cobrado por tempo.

## O que já está pronto

- Dashboard com serviços do dia, próximos, atrasados e resumo financeiro
- Clientes com busca por nome/telefone, endereço, WhatsApp, Maps e histórico
- Agenda por dia, semana e mês
- Serviço com cadastro ultrarrápido: cliente → serviço → dia → salvar, com opções avançadas recolhidas
- Serviço com data e **horário opcional**
- Cronômetro com iniciar, pausar e zerar
- Cobrança por valor fechado ou por hora
- Ordem de serviço imprimível / salvável em PDF pelo navegador
- Fotos de **antes e depois** tiradas pelo celular e vinculadas ao serviço
- Assinatura do cliente direto na tela do smartphone, incluída na OS
- Botão de endereço para abrir direto no Google Maps
- Cálculo de **lucro real por serviço** com custo de materiais, ajudante e outros gastos
- Orçamentos com itens, materiais, mão de obra, desconto e validade
- Aprovar orçamento e transformar em serviço
- Financeiro com entradas, despesas, pendências e baixa de pagamento
- Materiais / estoque com entrada e saída
- Uso de material do estoque diretamente no serviço
- Relatórios por período + exportação CSV
- Backup completo em ZIP com banco de dados, fotos e assinaturas
- Layout responsivo para celular
- Primeiro acesso cria usuário e senha
- Dockerfile e `docker-compose.yaml` prontos para deploy

## Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

Acesse `http://localhost:5000`.

No primeiro acesso o sistema pede:

1. Nome da empresa
2. Nome do profissional
3. Usuário
4. Senha

## Rodar com Docker

```bash
docker compose up -d --build
```

Acesse `http://localhost:5000`.

## Deploy no Coolify

### Opção recomendada: Docker Compose

1. Coloque esta pasta em um repositório GitHub.
2. No Coolify, crie um novo recurso a partir do repositório.
3. Escolha **Docker Compose**.
4. O arquivo já está na raiz com o nome `docker-compose.yaml`.
5. Adicione a variável `SECRET_KEY` com uma chave aleatória grande.
6. Faça o deploy.
7. Configure o domínio para a porta `5000` se o Coolify não detectar automaticamente.

O banco fica no volume Docker `guilherme_eletrica_data`, montado em `/data`. Isso evita perder clientes e serviços em redeploys normais.

### Opção Dockerfile

Também é possível escolher build por Dockerfile. Nesse caso, **configure um volume persistente em `/data`** no Coolify.

## Backup

No sistema, abra **Configurações → Baixar backup agora**. O arquivo `.zip` contém o banco de dados e também as fotos/assinaturas salvas em `/data/uploads`.

## Observações

- Impressão de OS e orçamento usa a impressão do navegador. No celular ou computador, escolha **Salvar como PDF** para gerar o PDF.
- WhatsApp abre a conversa do cliente usando o número cadastrado.
- Para instalações no Brasil, cadastre o telefone com DDD. O botão considera o código do país `55`.
- O sistema atende Guilherme e uma pequena equipe, com acesso administrativo e login restrito para ajudantes.

## Uso no smartphone
Esta versão foi ajustada para uso diário no celular:
- navegação inferior fixa com Início, Agenda, Novo Serviço, Financeiro e Clientes;
- botão central de Novo Serviço destacado para uso rápido em campo;
- menu lateral por toque para Orçamentos, Materiais, Relatórios e Configurações;
- tabelas viram cartões no celular, sem precisar arrastar a tela para os lados;
- formulários em uma coluna, campos maiores e fonte de 16px para evitar zoom automático;
- seleção de cliente com busca rápida por nome ou telefone nos serviços, orçamentos, financeiro e tarefas;
- botões e áreas de toque ampliados;
- suporte a área segura de iPhone e barra inferior;
- layout de agenda, cronômetro, financeiro e detalhes pensado para tela estreita;
- manifest e ícones para adicionar o sistema à tela inicial do celular.

### Adicionar à tela inicial
**Android / Chrome:** abra o sistema, toque no menu do navegador e escolha **Adicionar à tela inicial** ou **Instalar app**.

**iPhone / Safari:** abra o sistema, toque em **Compartilhar** e depois em **Adicionar à Tela de Início**.

## Equipe / Ajudante
A versão atual também atende quando Guilherme trabalha com ajudante:

- cadastro de um ou mais ajudantes;
- usuário e senha próprios para o ajudante;
- acesso restrito no celular, sem financeiro geral, valores de clientes ou configurações;
- atribuição de responsável diretamente no cadastro do serviço;
- tarefas avulsas com dia, horário opcional, prioridade, cliente, endereço e instruções;
- cronômetro próprio do ajudante em tarefa ou serviço;
- acompanhamento de horas trabalhadas por período;
- lançamento de diária, alimentação, combustível, adiantamento, pagamento e outros gastos;
- cada gasto pode ser geral ou vinculado a um serviço específico;
- gastos da equipe entram automaticamente no módulo Financeiro como despesas;
- controle de valores pagos e ainda pendentes com o ajudante;
- visão rápida da equipe no Dashboard e uma área exclusiva “Equipe / Ajudante”.

O ajudante entra pelo **mesmo link do sistema** com o usuário e senha criados em `Equipe / Ajudante`. O sistema reconhece o perfil e abre apenas a tela **Meu dia**, com tarefas e serviços atribuídos.


## Exclusões e correção de cadastros

A interface administrativa possui opção de **Excluir** nos cadastros principais: clientes, serviços, orçamentos, lançamentos financeiros manuais, materiais, ajudantes, tarefas, gastos da equipe e materiais usados em serviços. Todas as exclusões exibem confirmação. Registros que fazem parte de histórico importante recebem proteção: por exemplo, um cliente com serviços/orçamentos precisa ter esse histórico removido primeiro; material já utilizado em serviço também não é apagado diretamente.
