"""A trava de leitura é o que separa o painel de registrar ciência: precisa de teste."""

import pytest

from domicilio_web.gateway import Bloqueado, checar_rota

PROC = "00000012320268180140"


@pytest.mark.parametrize("metodo,rota", [
    ("GET", "/web/eu"),
    ("GET", "/api/v1/representados"),
    ("GET", "/web/comunicacoes/orgaos-publicos/listatribunais"),
    ("POST", "/web/comunicacoes/orgaos-publicos"),
    ("POST", "/web/comunicacoes/orgaos-publicos/filtros"),
    ("POST", "/web/comunicacoes/orgaos-publicos/qtd-em-curso"),
    ("POST", "/web/publica/comunicacoes-representantes"),
    ("GET", f"/api/v1/processos/{PROC}/logs"),
])
def test_consultas_passam(metodo, rota):
    checar_rota(metodo, rota)


@pytest.mark.parametrize("metodo,rota", [
    # aceitarTeor() do front oficial: registra a ciência.
    ("PUT", f"/api/v1/processos/{PROC}/comunicacoes/1234567"),
    # link do inteiro teor ("Link Obtido" no log).
    ("GET", f"/api/v1/processo/{PROC}/comunicacao/1234567/ticket"),
    ("POST", f"/api/v1/processos/{PROC}/comunicacoes/1234567/peticoes"),
    ("PATCH", "/api/v1/pessoas/1/termos/2/aceitar-termo"),
    ("GET", "/web/comunicacoes/exportar"),
    ("GET", "/api/v1/codigoqr/abc"),
    ("DELETE", "/web/eu"),
    ("PUT", "/web/eu"),
    ("GET", "/api/v1/processos/123/logs"),            # número fora do padrão CNJ
    ("GET", f"/api/v1/processos/{PROC}/logs/../comunicacoes/1"),
    ("POST", "/web/comunicacoes"),                      # rota não usada pelo painel
])
def test_rotas_perigosas_barradas(metodo, rota):
    with pytest.raises(Bloqueado):
        checar_rota(metodo, rota)
