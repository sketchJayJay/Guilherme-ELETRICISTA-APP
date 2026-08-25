# Guilherme Elétrica

Sistema web responsivo para a rotina de um eletricista, pensado em **serviços por dia**, com horário opcional e cronômetro quando o trabalho for cobrado por tempo.

## O que já está pronto

- Dashboard com serviços do dia, próximos, atrasados e resumo financeiro
- Clientes com busca, endereço, WhatsApp e histórico
- Agenda por dia, semana e mês
- Serviço com data e **horário opcional**
- Cronômetro com iniciar, pausar e zerar
- Cobrança por valor fechado ou por hora
- Ordem de serviço imprimível / salvável em PDF pelo navegador
- Orçamentos com itens, materiais, mão de obra, desconto e validade
- Aprovar orçamento e transformar em serviço
- Financeiro com entradas, despesas, pendências e baixa de pagamento
- Materiais / estoque com entrada e saída
- Uso de material do estoque diretamente no serviço
- Relatórios por período + exportação CSV
- Backup do banco de dados
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

No sistema, abra **Configurações → Baixar backup agora**. O arquivo `.db` contém os dados do sistema.

## Observações

- Impressão de OS e orçamento usa a impressão do navegador. No celular ou computador, escolha **Salvar como PDF** para gerar o PDF.
- WhatsApp abre a conversa do cliente usando o número cadastrado.
- Para instalações no Brasil, cadastre o telefone com DDD. O botão considera o código do país `55`.
- O sistema é ideal para um profissional ou pequena equipe usando um único login.
