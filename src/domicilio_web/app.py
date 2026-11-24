"""Servidor local do painel (FastAPI). Só escuta em 127.0.0.1."""

from __future__ import annotations

import io
import os
import time
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import gateway as gw

ESTATICO = Path(__file__).parent / "static"
app = FastAPI(title="Domicílio — painel local (somente leitura)", docs_url=None, redoc_url=None)

_cache: dict[tuple, tuple[float, dict]] = {}
CACHE_S = 300

# Campos do grid levados à tela. "linksDocumentos" fica de fora de propósito:
# abrir esses links é o caminho do inteiro teor.
_SAIDA = ("numeroComunicacao", "numeroProcesso", "numeroProcessoAntigo", "assunto", "assuntoComunicacao",
          "tipoComunicacao", "tipoIntimacao", "dataComunicacao", "dataFinalCiencia", "dataCiente",
          "dataCerta", "prazo", "tipoPrazo", "emCurso", "ciente", "foiCienciaAutomatica",
          "nomeUsuarioCiente", "siglaTribunal", "tribunalOrigem", "varaJudicial", "orgaoLegal",
          "instancia", "classe", "sistemaProcesso", "valorCausa", "urgente", "tutelaUrgencia",
          "segredoJustica", "nivelSigilo", "meioEnvio", "magistrado", "nomeDestinatario",
          "documentoDestinatario", "dataAjuizamento", "audiencia", "motivoIntimacao", "uf",
          "ramoJustica", "status", "autoresReclamantes", "reus", "parteInteressada", "jtr")


def _cnj(d: str) -> str:
    d = "".join(c for c in str(d or "") if c.isdigit())
    return f"{d[:7]}-{d[7:9]}.{d[9:13]}.{d[13]}.{d[14:16]}.{d[16:]}" if len(d) == 20 else d


def _enxugar(it: dict) -> dict:
    out = {k: it.get(k) for k in _SAIDA}
    out["processoFormatado"] = _cnj(it.get("numeroProcesso"))
    st = it.get("status")
    out["situacao"] = st.get("descricao") if isinstance(st, dict) else st
    return out


async def _perfil(tenant: str) -> dict:
    try:
        eu = await gw.eu()
    except gw.SemToken as e:
        raise HTTPException(401, str(e))
    for p in eu.get("perfis") or []:
        if p.get("tenantId") == tenant:
            if not gw.pode_ler(p):
                raise HTTPException(403, "Este perfil não pode ler comunicações no Domicílio.")
            return p
    raise HTTPException(404, "Perfil não encontrado para este usuário.")


def _datas(inicio: str | None, fim: str | None) -> tuple[date, date]:
    f = date.fromisoformat(fim) if fim else date.today()
    i = date.fromisoformat(inicio) if inicio else f - timedelta(days=6)
    if i > f:
        raise HTTPException(400, "Data inicial depois da final.")
    if (f - i).days > 92:
        raise HTTPException(400, "Período máximo de 93 dias (o gateway é consultado de 7 em 7 dias).")
    return i, f


@app.exception_handler(gw.SemToken)
async def _sem_token(_, e):
    return JSONResponse({"detail": str(e)}, status_code=401)


@app.exception_handler(gw.ErroGateway)
async def _erro_gw(_, e):
    return JSONResponse({"detail": str(e)}, status_code=502 if e.status >= 500 else e.status)


@app.exception_handler(gw.Bloqueado)
async def _bloqueado(_, e):
    return JSONResponse({"detail": str(e)}, status_code=403)


@app.get("/api/status")
async def status():
    v = gw.validade()
    if not v["valido"]:
        return {"token": v, "pessoa": None, "perfis": []}
    eu = await gw.eu()
    perfis = [{"tenantId": p.get("tenantId"), "cargo": (p.get("cargo") or {}).get("descricao"),
               "funcao": p.get("funcao"), "tenantNome": p.get("tenantName"),
               "cnpj": p.get("tenantDocumento") if len(p.get("tenantDocumento") or "") == 14 else None,
               "orgaoPublico": gw.eh_orgao_publico(p), "podeLer": gw.pode_ler(p)}
              for p in eu.get("perfis") or []]
    pessoa = eu.get("pessoa") or {}
    return {"token": v, "pessoa": pessoa.get("nome") or eu.get("nome"), "perfis": perfis}


@app.get("/api/comunicacoes")
async def comunicacoes(tenant: str, inicio: str | None = None, fim: str | None = None,
                       situacao: str = Query("todas", pattern="^(todas|lidas|nao_lidas)$"),
                       recarregar: bool = False):
    i, f = _datas(inicio, fim)
    chave = (tenant, i, f, situacao)
    agora = time.time()
    if not recarregar and chave in _cache and agora - _cache[chave][0] < CACHE_S:
        return _cache[chave][1]
    perfil = await _perfil(tenant)
    g = await gw.grid(perfil, i, f, situacao)
    res = {"inicio": str(i), "fim": str(f), "situacao": situacao,
           "totalEmCurso": g["totalEmCurso"], "totalEncerrado": g["totalEncerrado"],
           "itens": [_enxugar(x) for x in g["itens"]], "consultadoEm": int(agora)}
    _cache[chave] = (agora, res)
    return res


@app.get("/api/em-curso")
async def em_curso(tenant: str):
    return {"resultado": await gw.qtd_em_curso(await _perfil(tenant))}


@app.get("/api/tribunais")
async def tribunais(tenant: str):
    return await gw.tribunais(await _perfil(tenant))


@app.get("/api/logs")
async def logs(tenant: str, processo: str, comunicacao: str):
    return await gw.logs(await _perfil(tenant), processo, comunicacao)


@app.get("/api/exportar")
async def exportar(tenant: str, inicio: str | None = None, fim: str | None = None, situacao: str = "todas"):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    dados = await comunicacoes(tenant, inicio, fim, situacao)
    colunas = [("Nº do processo", "processoFormatado"), ("Nº antigo", "numeroProcessoAntigo"),
               ("Comunicação", "numeroComunicacao"), ("Tipo", "tipoComunicacao"),
               ("Tipo de intimação", "tipoIntimacao"), ("Assunto", "assunto"),
               ("Tribunal", "siglaTribunal"), ("Órgão", "orgaoLegal"), ("Disponibilização", "dataComunicacao"),
               ("Data final da ciência", "dataFinalCiencia"), ("Ciência em", "dataCiente"),
               ("Ciência automática", "foiCienciaAutomatica"), ("Prazo", "prazo"), ("Tipo de prazo", "tipoPrazo"),
               ("Situação", "situacao"), ("Em curso", "emCurso"), ("Urgente", "urgente")]
    wb = Workbook()
    ws = wb.active
    ws.title = "Comunicações"
    ws.append([c for c, _ in colunas])
    for c in ws[1]:
        c.font = Font(bold=True)
    for it in dados["itens"]:
        ws.append([it.get(k) if not isinstance(it.get(k), (dict, list)) else str(it.get(k)) for _, k in colunas])
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    nome = f"domicilio_{dados['inicio']}_{dados['fim']}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@app.get("/")
async def raiz():
    return FileResponse(ESTATICO / "index.html")


app.mount("/static", StaticFiles(directory=ESTATICO), name="static")


def main() -> None:
    import uvicorn

    porta = int(os.environ.get("DOMICILIO_WEB_PORTA", "8777"))
    print(f"Painel em http://127.0.0.1:{porta}")
    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="warning")


if __name__ == "__main__":
    main()
