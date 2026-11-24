<h1 align="center">
    <img alt="Domicílio-Web" src="docs/assets/banner.svg">
    <br>
    <small>A tela de comunicações do Domicílio, rodando no seu Mac, sem o risco de dar ciência</small>
</h1>

<p align="center">
    <img alt="Python" src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white">
    <img alt="Testes" src="https://img.shields.io/badge/testes-19%20%E2%9C%93-brightgreen">
    <img alt="Somente leitura" src="https://img.shields.io/badge/ci%C3%AAncia-bloqueada-8b0000">
    <img alt="Local" src="https://img.shields.io/badge/servidor-127.0.0.1-black">
</p>

Painel local, **somente leitura**, das citações e intimações recebidas no
Domicílio Judicial Eletrônico (CNJ). Reproduz a tela de comunicações do portal
(perfil, prazos em curso e encerrados, filtros, grid, detalhamento e log de
auditoria) sobre a mesma API do gateway, rodando só em `127.0.0.1`.

Ferramenta não oficial, sem vínculo com o CNJ. O mapa do front e da API, obtido
por engenharia reversa dos bundles públicos, está em
[`docs/MAPA-API.md`](docs/MAPA-API.md).

## Regra que não se negocia

Abrir o inteiro teor ou dar ciência **registra a ciência e começa a contar
prazo**. No front oficial isso é `PUT /api/v1/processos/{cnj}/comunicacoes/{n}`
(e o `…/ticket` gera o link do teor). O painel não tem essas chamadas:
`gateway.checar_rota` só deixa passar a lista fechada de rotas de consulta e
recusa o resto antes de abrir conexão. `tests/test_bloqueio.py` cobre isso.

## Uso

O token vem do login do [`domicilio-mcp`](../domicilio-mcp), feito pelo gov.br
e gravado em `~/.domicilio-mcp/token.json` (válido por 8 h).

```bash
cd ~/Desenvolvimento/domicilio-mcp && uv run domicilio-mcp login   # se o token venceu
cd ~/Desenvolvimento/domicilio-web && uv run domicilio-web          # http://127.0.0.1:8777
```

Porta: `DOMICILIO_WEB_PORTA`. Pasta do token: `DOMICILIO_HOME`.

## O que tem

- Seleção de perfil, com o perfil do órgão (CNPJ) como padrão.
- Cartões: prazos em curso, prazos encerrados e total no período, além do
  contador oficial `qtd-em-curso`.
- Filtros: período (consultado de 7 em 7 dias, até 93 dias), ciência
  (ambas, com ou sem ciência), tipo, tribunal, prazo e busca por número CNJ,
  número antigo, assunto ou parte.
- Grid ordenável e paginado, com as colunas do portal (nº do processo,
  assunto, tipo, disponibilização, data final da ciência, forma de ciência,
  tipo de intimação, tribunal, nº antigo, detalhamento). Inteiro teor aparece
  só como cadeado.
- Detalhamento: dados da comunicação, partes e log de auditoria
  (disponibilização, ciência, link obtido, alteração de data final).
- Exportação `.xlsx`.
- Cache de 5 min por consulta; o botão "Atualizar" ignora o cache.

## Testes

```bash
uv run pytest
```
