"""Cliente do gateway do Domicílio Judicial Eletrônico — SOMENTE LEITURA.

Rotas levantadas no front oficial (Angular, chunks ``main`` e ``14``) com o REA
em 23/11/2026; ver ``docs/MAPA-API.md``.

REGRA DURA: no front oficial, ``aceitarTeor()`` chama
``PUT /api/v1/processos/{processo}/comunicacoes/{numero}`` e isso REGISTRA A
CIÊNCIA do Município (começa a contar prazo). ``GET .../comunicacao/{n}/ticket``
gera o link do inteiro teor ("Link Obtido" no log). Nenhuma das duas existe
aqui: o cliente só aceita as rotas de consulta da lista ``_PERMITIDAS`` e recusa
qualquer outro método, rota ou termo suspeito, antes de abrir conexão.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

GATEWAY = "https://gateway.cloud.pje.jus.br/domicilio-eletronico"

# Token compartilhado com o domicilio-mcp (login pelo gov.br: ``uv run domicilio-mcp login``).
TOKEN = Path(os.environ.get("DOMICILIO_HOME", Path.home() / ".domicilio-mcp")) / "token.json"
MARGEM_TOKEN = 120  # s

# (método, regex da rota). Tudo o que não casar aqui é recusado.
_PERMITIDAS: tuple[tuple[str, re.Pattern], ...] = tuple(
    (m, re.compile(p)) for m, p in (
        ("GET", r"^/web/eu$"),
        ("GET", r"^/api/v1/representados$"),
        ("GET", r"^/web/comunicacoes/orgaos-publicos/listatribunais$"),
        ("POST", r"^/web/comunicacoes/orgaos-publicos$"),
        ("POST", r"^/web/comunicacoes/orgaos-publicos/filtros$"),
        ("POST", r"^/web/comunicacoes/orgaos-publicos/qtd-em-curso$"),
        ("POST", r"^/web/publica/comunicacoes-representantes$"),
        ("POST", r"^/web/publica/comunicacoes-representantes/qtd-em-curso$"),
        ("GET", r"^/api/v1/processos/\d{20}/logs$"),
    )
)
_TERMOS_PROIBIDOS = ("teor", "cienc", "aceite", "aceitar", "ticket", "certidao", "codigoqr",
                     "peticao", "peticoes", "download", "documento", "exportar", "termo")


class Bloqueado(PermissionError):
    """Rota fora da lista de consulta: poderia registrar ciência ou alterar dados."""


class SemToken(RuntimeError):
    """Não há token válido em cache."""


class ErroGateway(RuntimeError):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


def checar_rota(metodo: str, caminho: str) -> None:
    metodo = metodo.upper()
    baixo = caminho.lower()
    if any(t in baixo for t in _TERMOS_PROIBIDOS):
        raise Bloqueado(f"Rota bloqueada (pode registrar ciência): {metodo} {caminho}")
    if not any(metodo == m and rx.match(caminho) for m, rx in _PERMITIDAS):
        raise Bloqueado(f"Rota fora da lista de consulta: {metodo} {caminho}")


def _exp(token: str) -> float:
    carga = token.split(".")[1]
    carga += "=" * (-len(carga) % 4)
    return float(json.loads(base64.urlsafe_b64decode(carga))["exp"])


def token() -> str:
    try:
        d = json.loads(TOKEN.read_text())
        t = d["token"]
        if float(d.get("exp") or _exp(t)) - time.time() > MARGEM_TOKEN:
            return t
    except FileNotFoundError:
        pass
    except Exception:
        pass
    raise SemToken("Sem token válido do Domicílio. Faça login com: "
                   "cd ~/Desenvolvimento/domicilio-mcp && uv run domicilio-mcp login")


def validade() -> dict:
    try:
        d = json.loads(TOKEN.read_text())
        resta = float(d.get("exp") or _exp(d["token"])) - time.time()
        return {"valido": resta > MARGEM_TOKEN, "minutos": max(0, int(resta // 60))}
    except Exception:
        return {"valido": False, "minutos": 0}


async def requisitar(metodo: str, caminho: str, *, tenant: str | None = None,
                     params: dict | None = None, corpo: dict | None = None) -> Any:
    checar_rota(metodo, caminho)
    headers = {"Authorization": f"Bearer {token()}", "Accept": "application/json"}
    if tenant:
        headers["tenantId"] = tenant
    async with httpx.AsyncClient(timeout=60) as cli:
        r = await cli.request(metodo.upper(), GATEWAY + caminho, headers=headers, params=params, json=corpo)
    if r.status_code in (401, 403):
        raise ErroGateway(r.status_code, "Acesso negado pelo gateway (token vencido ou perfil sem permissão).")
    if r.status_code >= 400:
        raise ErroGateway(r.status_code, f"{metodo} {caminho} → HTTP {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else None


# ------------------------------------------------------------------ perfis

def eh_orgao_publico(perfil: dict) -> bool:
    return bool(perfil.get("orgaoPublico")) and len(perfil.get("tenantDocumento") or "") == 14


def pode_ler(perfil: dict) -> bool:
    for r in perfil.get("recursos") or []:
        if r.get("nome") == "COMUNICACOES":
            return bool(r.get("podeLer"))
    return bool(perfil.get("podeRepresentar"))


async def eu() -> dict:
    return await requisitar("GET", "/web/eu")


# ------------------------------------------------------------------ comunicações

CIENTE = {"todas": "A", "lidas": "L", "nao_lidas": "N"}


def corpo_grid(perfil: dict, ini: date, fim: date, ciente: str, pagina: int, tamanho: int) -> dict:
    """Corpo idêntico ao que o front oficial monta (classe de filtro do chunk main)."""
    if eh_orgao_publico(perfil):
        return {"tipoComunicacao": "", "assunto": "",
                "datas": {"dataFim": str(fim), "dataInicio": str(ini)},
                "documentoRepresentanteDestinatario": "", "dataCiencia": "", "dataFinalCiencia": "",
                "ciente": ciente,
                "filtros": {"autoresReclamantes": [], "tribunalOrigem": [], "orgaoLegal": [], "status": []},
                "pagina": {"size": tamanho, "page": pagina}, "jtrProprietario": "",
                "modalidadeComunicacaoProcessual": "G"}
    return {"tipoComunicacao": "", "assunto": "",
            "datas": {"dataInicio": str(ini), "dataFim": str(fim)},
            "ciente": ciente, "pagina": {"size": tamanho, "page": pagina},
            "modalidadeComunicacaoProcessual": "G"}


def janelas(ini: date, fim: date, passo: int = 7):
    """O gateway dá contagens incoerentes acima de 7 dias: o front consulta de 7 em 7."""
    b = fim
    while b >= ini:
        a = max(ini, b - timedelta(days=passo - 1))
        yield a, b
        b = a - timedelta(days=1)


async def grid(perfil: dict, ini: date, fim: date, situacao: str = "todas") -> dict:
    ciente = CIENTE.get(situacao, "A")
    orgao = eh_orgao_publico(perfil)
    rota = "/web/comunicacoes/orgaos-publicos" if orgao else "/web/publica/comunicacoes-representantes"
    vistos: dict[str, dict] = {}
    for a, b in janelas(ini, fim):
        pagina = 0
        while True:
            params = {"size": 100, "page": pagina, "sort": "numeroProcesso,asc"}
            if not orgao:
                params["modalidadeComunicacaoProcessual"] = "G"
            j = await requisitar("POST", rota, tenant=perfil["tenantId"], params=params,
                                 corpo=corpo_grid(perfil, a, b, ciente, pagina, 100)) or {}
            itens = j.get("grid") or []
            for it in itens:
                vistos.setdefault(str(it.get("numeroComunicacao") or it.get("idAviso")), it)
            if len(itens) < 100 or pagina >= 50:
                break
            pagina += 1
    itens = list(vistos.values())
    em_curso = sum(1 for i in itens if i.get("emCurso"))
    return {"itens": itens, "totalEmCurso": em_curso, "totalEncerrado": len(itens) - em_curso}


async def qtd_em_curso(perfil: dict) -> int | None:
    rota = ("/web/comunicacoes/orgaos-publicos/qtd-em-curso" if eh_orgao_publico(perfil)
            else "/web/publica/comunicacoes-representantes/qtd-em-curso")
    hoje = date.today()
    j = await requisitar("POST", rota, tenant=perfil["tenantId"],
                         corpo=corpo_grid(perfil, hoje - timedelta(days=6), hoje, "A", 0, 10))
    return (j or {}).get("resultado")


async def tribunais(perfil: dict) -> list[dict]:
    j = await requisitar("GET", "/web/comunicacoes/orgaos-publicos/listatribunais", tenant=perfil["tenantId"])
    return sorted((j or {}).get("tribunais") or [], key=lambda t: t.get("sigla") or "")


async def logs(perfil: dict, processo: str, numero_comunicacao: str) -> list[dict]:
    processo = re.sub(r"\D", "", processo)
    j = await requisitar("GET", f"/api/v1/processos/{processo}/logs", tenant=perfil["tenantId"],
                         params={"numeroComunicacao": numero_comunicacao})
    return (j or {}).get("data") or []
