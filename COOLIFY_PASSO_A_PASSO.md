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


## Fotos e assinaturas
As fotos e assinaturas ficam dentro de `/data/uploads`. Por isso, mantenha o volume persistente montado em `/data`; assim esses arquivos também sobrevivem aos redeploys.

## Notificações do ajudante
A versão atual usa notificações push. No Coolify, mantenha HTTPS habilitado no domínio.

Variáveis opcionais:
- `APP_TIMEZONE=America/Sao_Paulo`
- `HELPER_NOTIFICATION_HOUR=7`
- `HELPER_NOTIFICATION_MINUTE=0`

O ajudante precisa entrar no sistema pelo celular e tocar em **Ativar notificações** uma vez. No iPhone, instale o sistema na Tela de Início antes de ativar.
