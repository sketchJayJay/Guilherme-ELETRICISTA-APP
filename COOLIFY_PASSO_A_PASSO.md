# Subindo no Coolify

## 1. GitHub
Envie todos os arquivos desta pasta para um repositório. O `docker-compose.yaml` precisa ficar na raiz.

## 2. Criar no Coolify
- New Resource
- Public/Private Repository conforme o seu GitHub
- Selecione o repositório
- Build Pack: **Docker Compose**
- Compose file: `/docker-compose.yaml`

## 3. Variável de ambiente
Crie:

`SECRET_KEY=uma-chave-grande-e-aleatoria`

## 4. Banco persistente
O compose já cria um volume nomeado e monta em `/data`. Não remova o volume.

## 5. Deploy
Clique em Deploy. A aplicação escuta a porta `5000` e possui `/health` para teste.

## 6. Primeiro acesso
Ao abrir o domínio pela primeira vez, o sistema vai pedir:
- nome da empresa
- nome do eletricista
- usuário
- senha

Depois disso o primeiro usuário já fica salvo no banco.

## 7. Domínio
No Coolify, associe o domínio ao serviço `guilherme-eletrica` na porta `5000`.

## 8. Backup
Dentro do sistema: **Configurações > Baixar backup agora**.

> Importante: se algum dia trocar de servidor, preserve o volume `/data` ou leve o backup `.db` junto.
