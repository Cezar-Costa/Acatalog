# Acatalog Tech

Monolito com backend Django REST e frontend Next.js para e-commerce de hardware, perifericos, mobile e componentes gamer/profissionais.

## Estrutura

- `backend/`: Django, DRF, SimpleJWT, django-filter, DRF Spectacular.
- `frontend/`: Next.js App Router, React, TypeScript, Tailwind CSS e React Query.
- Banco local inicial: SQLite.
- PostgreSQL: pronto via `DATABASE_URL`.

## Backend

```powershell
cd "C:\Users\cezar\Desktop\loja informatica"
Copy-Item backend\.env.example backend\.env
backend\venv\Scripts\pip.exe install -r backend\requirements.txt
backend\venv\Scripts\python.exe backend\manage.py migrate
backend\venv\Scripts\python.exe backend\manage.py seed_demo
backend\venv\Scripts\python.exe backend\manage.py runserver
```

API: `http://127.0.0.1:8000/api/`
Docs: `http://127.0.0.1:8000/api/docs/`
Dashboard Python: `http://127.0.0.1:8000/python-dashboard/`

Variaveis principais em `backend/.env`:

```env
DJANGO_SECRET_KEY=troque-esta-chave-em-producao
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001
SQLITE_NAME=db.sqlite3
DATABASE_URL=postgresql://usuario:senha@localhost:5432/acatalog
GOOGLE_CLIENT_ID=
REFRESH_COOKIE_SECURE=False
REFRESH_COOKIE_SAMESITE=Lax
```

Para login com Google Identity Services, use o **Client ID** OAuth em `GOOGLE_CLIENT_ID` no backend e em
`NEXT_PUBLIC_GOOGLE_CLIENT_ID` no frontend. Nao use Client Secret no frontend. No Google Cloud, mantenha em
"Origens JavaScript autorizadas" pelo menos:

- `https://acatalog1.cezarvault.uk`
- `http://localhost:3000`

O fluxo usado envia o ID token para `/api/auth/google/`; URI de redirecionamento nao e obrigatoria para esse botao,
mas pode ficar cadastrada sem impacto. Se algum Client Secret foi compartilhado fora do Google Cloud, revogue e gere
outro segredo.

Dados demo criados por `seed_demo`:

- Admin: `admin@acatalog.local` / `Admin@12345`
- Cliente: `cliente@acatalog.local` / `Cliente@12345`
- Cupom: `RAD10`

Para outro login administrativo pelo dashboard, o usuario precisa ser `is_staff=True` ou ter `role=admin/operator`.

## Dashboard Python

A rota `http://127.0.0.1:8000/python-dashboard/` redireciona para `/dashboard/`, uma tela administrativa renderizada diretamente pelo Django.
Ela usa Python no backend para validar o cookie JWT `refresh_token`, checar se o usuario e admin/operador, consultar pedidos, faturamento,
estoque, clientes, promocoes e produtos mais vendidos, montar o contexto e entregar um HTML pronto pelo template
`backend/commerce/templates/commerce/python_dashboard.html`.

Diferenca para a dashboard Next.js: a area `/admin` do frontend consome a API via React/React Query; ja a dashboard Python nao depende de
Next.js no navegador, porque o proprio Django consulta o banco e renderiza os cards, graficos simples e listas no servidor.

## Frontend

```powershell
cd "C:\Users\cezar\Desktop\loja informatica\frontend"
npm.cmd install
npm.cmd run dev -- -p 3001
```

Loja: `http://localhost:3001/`
Dashboard Next.js: `http://localhost:3001/admin`

Se no Windows aparecer `Error: spawn EPERM` no `npm run dev`, use modo estavel:

```powershell
cd "C:\Users\cezar\Desktop\loja informatica\frontend"
npm.cmd run build
npm.cmd run start -- -H 127.0.0.1 -p 3001
```

Nesse ambiente, prefira acessar por `http://127.0.0.1:3001/` (em vez de `localhost`).

Se usar outra API:

```powershell
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8000/api"
$env:NEXT_PUBLIC_GOOGLE_CLIENT_ID="882473535632-hc6n6kvnv3dlhsashmtcohn7l8nfc6ii.apps.googleusercontent.com"
npm.cmd run dev -- -p 3001
```

## Entregaveis v1.4.0

- Entregavel 1: catalogo funcional, seed inicial, carrinho basico e imagens reais de produtos.
- Entregavel 2: autenticacao tradicional e Google, conta de usuario, checkout, cupons e pedidos.
- Entregavel 3: wishlist, reviews, filtros/refinamentos de UX e area administrativa.
- Entrega final: backend/frontend integrados, documentacao atualizada, dashboard Next.js e dashboard Python renderizada pelo Django.

## Fluxo manual

1. Criar conta em `/login`.
2. Navegar em `/catalogo`.
3. Abrir produto, adicionar ao carrinho e salvar na wishlist.
4. Ver `/carrinho`, aplicar cupom criado no admin e conferir totais vindos da API.
5. Criar endereco em `/checkout`, selecionar pagamento mock e criar pedido.
6. Ver pedido em `/conta`.
7. Entrar em `/admin/login`, cadastrar produtos/categorias/cupons e acompanhar pedidos.
8. Acessar `/python-dashboard/` no backend para validar a dashboard renderizada por Python.

## Validacao

```powershell
backend\venv\Scripts\python.exe backend\manage.py check
backend\venv\Scripts\python.exe backend\manage.py test
cd frontend
npm.cmd run lint
npm.cmd run build
```

## Observacoes

- O frontend agora exibe erro claro quando a API falha; mocks ficam isolados em `frontend/src/lib/mock-data.ts` para desenvolvimento visual, sem fallback silencioso na camada de API.
- Login Google exige `GOOGLE_CLIENT_ID` no backend e `NEXT_PUBLIC_GOOGLE_CLIENT_ID` no frontend; o backend valida o token pelo Google Identity Services.
- Pagamentos externos e frete real continuam previstos; o MVP usa pagamento mock e frete simplificado.
