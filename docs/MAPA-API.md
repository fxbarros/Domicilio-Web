# Mapa do front-end e da API do Domicílio Judicial Eletrônico

Levantamento de 23/11/2026, feito com o REA (`analyze_javascript_application`)
e leitura dirigida dos bundles públicos do portal
`https://domicilio-eletronico.pdpj.jus.br`. Não há source map publicado (a URL
`.map` devolve o `index.html`). O código do CNJ **não** está neste repositório:
aqui ficam só as conclusões, e o painel é código próprio.

## Arquitetura do front oficial

- Angular (build com `main-es2015`, `runtime`, `polyfills`, 19 chunks lazy).
- Configuração em `assets/config/env.js` (`window.__env`):

| Chave | Valor |
|---|---|
| `domicilioUrl` | `https://gateway.cloud.pje.jus.br/domicilio-eletronico` |
| `comunicacaoUrl` | `https://gateway.cloud.pje.jus.br/comunicacao-processual` |
| `repositorioUrl` | `https://gateway.cloud.pje.jus.br/repositorio` |
| `ssoUrl` / `realm` / `clientId` | `https://sso.cloud.pje.jus.br/auth/` / `pje` / `domicilio-eletronico-frontend` |

- Login: Keycloak (`keycloak-js`, fluxo com `silentrefresh`), com botão gov.br.
  O token (JWT, 8 h) segue como `Authorization: Bearer` e o perfil escolhido
  segue no header `tenantId`.
- Rotas da SPA: `home`, `comunicacoes`, `orgaos-publicos`, `selecionar-perfil`,
  `filiais`, `coligadas`, `incorporadas`, `usuarios`, `noticias`,
  `gerenciar-credenciais`, `editar-perfil`, `admin` etc.
- A tela de comunicações fica no chunk lazy `14` (`ComunicacoesModule`).

## Endpoints de consulta (usados pelo painel)

| Método | Rota | Uso |
|---|---|---|
| GET | `/web/eu` | pessoa, perfis (`tenantId`, `cargo`, `orgaoPublico`, `recursos`) e termo |
| GET | `/api/v1/representados` | entes representados pelo perfil |
| POST | `/web/comunicacoes/orgaos-publicos` | grid do perfil do próprio órgão (CNPJ) |
| POST | `/web/publica/comunicacoes-representantes` | grid do perfil de representante |
| POST | `…/qtd-em-curso` | contador "Prazos em curso" |
| POST | `…/filtros` | opções de filtro (autores, órgãos, tribunais) |
| GET | `/web/comunicacoes/orgaos-publicos/listatribunais` | lista de tribunais (`jtr`, `sigla`, `nome`) |
| GET | `/api/v1/processos/{cnj}/logs?numeroComunicacao=` | log de auditoria da comunicação |

Paginação por query (`size`, `page`, `sort=numeroProcesso,asc`) **e** no corpo
(`pagina`). O corpo do perfil de órgão público exige `ciente` (`A`/`L`/`N`) e
`datas`; sem eles o gateway responde 400. Janelas acima de 7 dias trazem
contagens incoerentes, e por isso o front (e o painel) consulta de 7 em 7 dias.

Resposta do grid: `grid[]` (cerca de 70 campos por comunicação), `totalEmCurso`,
`totalEncerrado`, `paginacao`, `possuiDataCerta`. Campos booleanos do tribunal
vêm como `"S"`/`"N"` (`urgente`, `tutelaUrgencia`); `valorCausa` vem como texto
no formato `10.739,08`.

Sem `numeroComunicacao`, o log traz os eventos de todas as comunicações do processo
(paginado por `size`/`page`). Instantes com `Z` são UTC: as ciências por decurso caem às
23:59:59 de Brasília. O `criadoEm` de algumas contas de serviço vem deslocado em 3 h e não
serve como horário do fato. Na ciência, `foiTribunal: true` indica ciência informada pelo
sistema do tribunal.

Eventos do log de auditoria (`payload`): `comunicacaoDisponibilizada`,
`ciencia`, `comunicacaoCancelada`, `expiradaEm`, `obtidoEm` ("Link Obtido") e
`mudancas` (data final de ciência alterada).

## Endpoints que alteram estado (BLOQUEADOS no painel)

| Método | Rota | O que faz no front oficial |
|---|---|---|
| PUT | `/api/v1/processos/{cnj}/comunicacoes/{n}` | `comunicacaoAceite()` ← `aceitarTeor()`: **registra a ciência** |
| GET | `/api/v1/processo/{cnj}/comunicacao/{n}/ticket` | `obterCertidao()`/`startPolling()`: gera o link do teor ("Link Obtido") |
| POST | `/api/v1/processos/{cnj}/comunicacoes/{n}/peticoes` | peticionamento pelo Domicílio |
| GET | `/web/tribunal-portal/{jtr}/peticionamento/permitido` | checagem de peticionamento |
| GET | `repositorio /arquivos/uploads/url?hash=…` | URL do arquivo do teor |
| PATCH | `/api/v1/pessoas/{id}/termos/{t}/aceitar-termo` | aceite de termo de uso |
| várias | `/filiais`, `/coligadas`, `/vinculos-orgaos-publicos`, `/admin/1/...` | cadastro e administração |

O `linksDocumentos` do grid também fica fora da resposta do painel.
