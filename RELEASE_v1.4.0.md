# v1.4.0 - Entregaveis completos e Dashboard Python

Esta versao consolida os entregaveis do projeto Acatalog, com catalogo funcional, autenticacao, carrinho, checkout, pedidos, cupons, wishlist, reviews, melhorias de UX, area administrativa e documentacao atualizada.

## Entregaveis implementados

- Entregavel 1: catalogo funcional, seed inicial, carrinho basico e imagens reais de produtos.
- Entregavel 2: autenticacao tradicional e Google, conta de usuario, checkout, cupons e pedidos.
- Entregavel 3: wishlist, reviews, filtros/refinamentos de UX e dashboard administrativa.
- Entrega final: sistema backend/frontend integrado, documentacao atualizada e demonstracao completa.

## Dashboard com Python

A versao inclui uma dashboard renderizada diretamente pelo Django em `/python-dashboard/`, que redireciona para `/dashboard/`.

Essa tela funciona assim:

1. O Django le o cookie `refresh_token` gerado no login administrativo.
2. O backend valida o JWT com `RefreshToken` e confirma se o usuario e admin/operador.
3. A view `admin_dashboard` consulta o banco usando Python e ORM do Django.
4. Os dados sao agregados para faturamento, pedidos, ticket medio, alertas de estoque, produtos mais vendidos, clientes, promocoes e status dos pedidos.
5. O template `backend/commerce/templates/commerce/python_dashboard.html` recebe esse contexto e renderiza o HTML final no servidor.

A diferenca principal e que essa dashboard nao depende do Next.js nem de requisicoes React no navegador. O proprio backend calcula os dados e entrega a pagina pronta.

## Principais rotas

- Loja Next.js: `/`
- Admin Next.js: `/admin`
- Dashboard Python/Django: `/python-dashboard/`
- API: `/api/`
- Swagger/OpenAPI: `/api/docs/`

## Observacoes

- O frontend foi marcado como `1.4.0`.
- Os arquivos `.env.local` e `.env.*.local` foram adicionados ao `.gitignore` para evitar publicar configuracoes locais.
- O README foi atualizado com instrucoes de execucao, Google Identity Services, entregaveis e dashboard Python.
