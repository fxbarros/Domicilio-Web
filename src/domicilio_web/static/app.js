"use strict";
// Painel local do Domicílio. Não existe aqui chamada para inteiro teor, ticket ou ciência.

const $ = (s) => document.querySelector(s);
const estado = { itens: [], filtrados: [], pagina: 0, ord: "dataFinalCiencia", asc: true, perfil: null, dados: null };

const fmtData = (v) => {
  if (!v) return "—";
  const s = String(v);
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/);
  if (!m) return s;
  return `${m[3]}/${m[2]}/${m[1]}` + (m[4] ? ` ${m[4]}:${m[5]}` : "");
};
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const sim = (v) => v === true || v === "S" || v === "s";
const moeda = (v) => {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(/[^\d,.-]/g, "").replace(/\.(?=\d{3}(\D|$))/g, "").replace(",", "."));
  return Number.isFinite(n) ? esc(n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })) : esc(v);
};
const nomes = (lista) => (lista || []).map((p) => p.nome).filter(Boolean).join("; ");

async function api(caminho) {
  const r = await fetch(caminho);
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try { msg = (await r.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return r.json();
}

function aviso(msg) {
  const el = $("#aviso");
  el.hidden = !msg;
  el.textContent = msg || "";
}

async function iniciar() {
  const hoje = new Date();
  const ini = new Date(hoje); ini.setDate(hoje.getDate() - 6);
  $("#inicio").value = iso(ini);
  $("#fim").value = iso(hoje);
  try {
    const st = await api("/api/status");
    const tk = $("#token");
    tk.textContent = st.token.valido ? `token ${st.token.minutos} min` : "sem token";
    tk.classList.toggle("ruim", !st.token.valido);
    if (!st.token.valido) {
      aviso("Sem token válido do Domicílio. Faça login uma vez com:\n  cd ~/Desenvolvimento/domicilio-mcp && uv run domicilio-mcp login\ne recarregue a página.");
      return;
    }
    $("#pessoa").textContent = st.pessoa || "";
    const sel = $("#perfil");
    sel.innerHTML = "";
    const aptos = st.perfis.filter((p) => p.podeLer);
    // Prefere o perfil do próprio órgão (CNPJ), como o "Procurador Chefe".
    aptos.sort((a, b) => (b.cnpj ? 1 : 0) - (a.cnpj ? 1 : 0));
    for (const p of st.perfis) {
      const o = document.createElement("option");
      o.value = p.tenantId;
      o.disabled = !p.podeLer;
      o.textContent = `${p.cargo || "Perfil"} — ${p.tenantNome || ""}${p.cnpj ? " (CNPJ " + p.cnpj + ")" : ""}${p.podeLer ? "" : " · sem acesso"}`;
      sel.append(o);
    }
    if (aptos[0]) sel.value = aptos[0].tenantId;
    estado.perfil = sel.value;
    await Promise.all([carregarTribunais(), pesquisar(false), carregarEmCurso()]);
  } catch (e) {
    aviso(e.message);
  }
}

async function carregarTribunais() {
  try {
    const lista = await api(`/api/tribunais?tenant=${encodeURIComponent(estado.perfil)}`);
    const sel = $("#tribunal");
    sel.innerHTML = '<option value="">Todos</option>';
    for (const t of lista) sel.append(new Option(`${t.sigla} — ${t.nome}`, t.sigla));
  } catch {}
}

async function carregarEmCurso() {
  try {
    const r = await api(`/api/em-curso?tenant=${encodeURIComponent(estado.perfil)}`);
    $("#emCursoGeral").textContent = r.resultado != null ? `gateway, últimos 7 dias: ${r.resultado}` : "";
  } catch { $("#emCursoGeral").textContent = ""; }
}

async function pesquisar(recarregar) {
  aviso("");
  const q = new URLSearchParams({ tenant: estado.perfil, inicio: $("#inicio").value, fim: $("#fim").value, situacao: $("#situacao").value });
  if (recarregar) q.set("recarregar", "true");
  $("#grid tbody").innerHTML = "";
  $("#vazio").hidden = false;
  $("#vazio").textContent = "Consultando o Domicílio (de 7 em 7 dias)…";
  try {
    const d = await api(`/api/comunicacoes?${q}`);
    estado.dados = d;
    estado.itens = d.itens;
    $("#consultado").textContent = `consulta às ${new Date(d.consultadoEm * 1000).toLocaleTimeString("pt-BR")}`;
    const tipos = [...new Set(d.itens.map((i) => i.tipoComunicacao).filter(Boolean))].sort();
    const selT = $("#tipo"); const atual = selT.value;
    selT.innerHTML = '<option value="">Todos</option>';
    for (const t of tipos) selT.append(new Option(t, t));
    selT.value = tipos.includes(atual) ? atual : "";
    filtrar();
  } catch (e) {
    $("#vazio").textContent = "";
    aviso(e.message);
  }
}

function filtrar() {
  const tipo = $("#tipo").value, trib = $("#tribunal").value, prazo = $("#prazo").value;
  const busca = $("#busca").value.trim().toLowerCase();
  const digitos = busca.replace(/\D/g, "");
  estado.filtrados = estado.itens.filter((i) => {
    if (tipo && i.tipoComunicacao !== tipo) return false;
    if (trib && i.siglaTribunal !== trib) return false;
    if (prazo === "curso" && !i.emCurso) return false;
    if (prazo === "encerrado" && i.emCurso) return false;
    if (busca) {
      const alvo = [i.processoFormatado, i.numeroProcessoAntigo, i.assunto, i.assuntoComunicacao, i.orgaoLegal, nomes(i.autoresReclamantes), nomes(i.reus)].join(" ").toLowerCase();
      const numOk = digitos.length >= 7 && String(i.numeroProcesso || "").includes(digitos);
      if (!alvo.includes(busca) && !numOk) return false;
    }
    return true;
  });
  ordenar();
  estado.pagina = 0;
  const curso = estado.filtrados.filter((i) => i.emCurso).length;
  $("#emCurso").textContent = curso;
  $("#encerrados").textContent = estado.filtrados.length - curso;
  $("#total").textContent = estado.filtrados.length;
  desenhar();
}

function ordenar() {
  const k = estado.ord, s = estado.asc ? 1 : -1;
  estado.filtrados.sort((a, b) => String(a[k] ?? "").localeCompare(String(b[k] ?? ""), "pt-BR", { numeric: true }) * s);
  document.querySelectorAll("th[data-ord]").forEach((th) => {
    th.classList.toggle("asc", th.dataset.ord === k && estado.asc);
    th.classList.toggle("desc", th.dataset.ord === k && !estado.asc);
  });
}

function formaCiencia(i) {
  if (i.ciente) return i.foiCienciaAutomatica ? '<span class="tag auto">Ciência automática</span>' : `<span class="tag curso">Ciência ${fmtData(i.dataCiente)}</span>`;
  return esc(i.situacao || "Aguardando ciência");
}

function desenhar() {
  const tam = Number($("#tamanho").value);
  const ini = estado.pagina * tam;
  const pag = estado.filtrados.slice(ini, ini + tam);
  const tb = $("#grid tbody");
  tb.innerHTML = pag.map((i, n) => `
    <tr>
      <td class="proc">${esc(i.processoFormatado)}${sim(i.urgente) ? ' <span class="tag urgente">urgente</span>' : ""}</td>
      <td>${esc(i.assunto || i.assuntoComunicacao || "—")}</td>
      <td>${esc(i.tipoComunicacao || "—")}</td>
      <td class="data">${fmtData(i.dataComunicacao)}</td>
      <td class="data">${fmtData(i.dataFinalCiencia)} <span class="tag ${i.emCurso ? "curso" : "encerrado"}">${i.emCurso ? "em curso" : "encerrado"}</span></td>
      <td>${formaCiencia(i)}</td>
      <td>${esc(i.tipoIntimacao || "—")}</td>
      <td>${esc(i.siglaTribunal || "—")}</td>
      <td>${esc(i.numeroProcessoAntigo || "—")}</td>
      <td><button type="button" data-det="${ini + n}">Detalhar</button></td>
      <td class="bloq" title="Abrir o teor registra a ciência do Município. Use o portal oficial.">🔒 só no portal</td>
    </tr>`).join("");
  $("#vazio").hidden = pag.length > 0;
  $("#vazio").textContent = "Nenhuma comunicação no período e filtros escolhidos.";
  const total = estado.filtrados.length;
  $("#faixa").textContent = total ? `${ini + 1}–${Math.min(ini + tam, total)} de ${total}` : "0 de 0";
  $("#ant").disabled = estado.pagina === 0;
  $("#prox").disabled = ini + tam >= total;
}

function campos(pares) {
  return `<dl class="campos">${pares.filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl>`;
}

const TITULOS_LOG = [
  ["ciencia", "Ciência"], ["comunicacaoDisponibilizada", "Comunicação disponibilizada"],
  ["comunicacaoCancelada", "Comunicação cancelada"], ["expiradaEm", "Expirado"], ["obtidoEm", "Link obtido"],
  ["mudancas", "Data final de ciência alterada"],
];

function itemLog(l) {
  const p = l.payload || {};
  const [chave, titulo] = TITULOS_LOG.find(([k]) => p[k] != null) || [null, "Evento"];
  const quando = chave && typeof p[chave] === "string" ? p[chave] : l.criadoEm;
  const extra = chave === "mudancas" ? `<small>${esc(JSON.stringify(p.mudancas))}</small>` : "";
  return `<li><strong>${esc(titulo)}</strong>${fmtData(quando)}<br><small>registrado por ${esc(l.criadoPor || "—")}</small>${extra}</li>`;
}

async function detalhar(i) {
  const dlg = $("#detalhe");
  $("#dTitulo").textContent = `Processo ${i.processoFormatado} · comunicação ${i.numeroComunicacao}`;
  dlg.querySelector('[data-painel="dados"]').innerHTML = campos([
    ["Tipo de comunicação", esc(i.tipoComunicacao)], ["Tipo de intimação", esc(i.tipoIntimacao)],
    ["Assunto", esc(i.assunto || i.assuntoComunicacao)], ["Classe", esc(i.classe)],
    ["Tribunal", esc([i.siglaTribunal, i.tribunalOrigem].filter((v, n, a) => v && a.indexOf(v) === n).join(" — "))],
    ["Órgão julgador", esc(i.orgaoLegal || i.varaJudicial)], ["Instância", esc(i.instancia)],
    ["Sistema", esc(i.sistemaProcesso)], ["Magistrado", esc(i.magistrado)],
    ["Disponibilização", fmtData(i.dataComunicacao)], ["Data final da ciência", fmtData(i.dataFinalCiencia)],
    ["Ciência em", i.ciente ? fmtData(i.dataCiente) + (i.foiCienciaAutomatica ? " (automática)" : "") : "sem ciência"],
    ["Quem deu ciência", esc(i.nomeUsuarioCiente)], ["Prazo", esc([i.prazo, i.tipoPrazo].filter(Boolean).join(" "))],
    ["Data certa", fmtData(i.dataCerta)], ["Situação", esc(i.situacao)], ["Meio de envio", esc(i.meioEnvio)],
    ["Valor da causa", moeda(i.valorCausa)],
    ["Ajuizamento", fmtData(i.dataAjuizamento)], ["Nº antigo", esc(i.numeroProcessoAntigo)],
    ["Segredo de justiça", sim(i.segredoJustica) ? "sim" : null], ["Tutela de urgência", sim(i.tutelaUrgencia) ? "sim" : null],
    ["Urgente", sim(i.urgente) ? "sim" : null],
    ["Inteiro teor", "🔒 Não é aberto aqui: abrir registra a ciência. Use o portal oficial."],
  ]);
  dlg.querySelector('[data-painel="partes"]').innerHTML = campos([
    ["Autores/reclamantes", esc(nomes(i.autoresReclamantes)) || "—"], ["Réus", esc(nomes(i.reus)) || "—"],
    ["Destinatário", esc(i.nomeDestinatario)],
  ]);
  const aud = dlg.querySelector('[data-painel="auditoria"]');
  aud.innerHTML = '<p class="carregando">Consultando o log de auditoria…</p>';
  trocarAba("dados");
  dlg.showModal();
  try {
    const q = new URLSearchParams({ tenant: estado.perfil, processo: i.numeroProcesso, comunicacao: i.numeroComunicacao });
    const logs = await api(`/api/logs?${q}`);
    logs.sort((a, b) => String(a.criadoEm).localeCompare(String(b.criadoEm)));
    aud.innerHTML = logs.length ? `<ol class="linha-tempo">${logs.map(itemLog).join("")}</ol>` : "<p>Sem registros.</p>";
  } catch (e) {
    aud.innerHTML = `<p class="aviso">${esc(e.message)}</p>`;
  }
}

function trocarAba(nome) {
  document.querySelectorAll(".abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === nome));
  document.querySelectorAll("[data-painel]").forEach((p) => (p.hidden = p.dataset.painel !== nome));
}

$("#filtros").addEventListener("submit", (e) => { e.preventDefault(); pesquisar(false); });
$("#recarregar").addEventListener("click", () => pesquisar(true));
$("#exportar").addEventListener("click", () => {
  const q = new URLSearchParams({ tenant: estado.perfil, inicio: $("#inicio").value, fim: $("#fim").value, situacao: $("#situacao").value });
  location.href = `/api/exportar?${q}`;
});
["#tipo", "#tribunal", "#prazo"].forEach((s) => $(s).addEventListener("change", filtrar));
$("#busca").addEventListener("input", filtrar);
$("#tamanho").addEventListener("change", () => { estado.pagina = 0; desenhar(); });
$("#ant").addEventListener("click", () => { estado.pagina--; desenhar(); });
$("#prox").addEventListener("click", () => { estado.pagina++; desenhar(); });
$("#perfil").addEventListener("change", async (e) => {
  estado.perfil = e.target.value;
  await Promise.all([carregarTribunais(), pesquisar(false), carregarEmCurso()]);
});
document.querySelectorAll("th[data-ord]").forEach((th) => th.addEventListener("click", () => {
  estado.asc = estado.ord === th.dataset.ord ? !estado.asc : true;
  estado.ord = th.dataset.ord;
  ordenar(); desenhar();
}));
$("#grid tbody").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-det]");
  if (b) detalhar(estado.filtrados[Number(b.dataset.det)]);
});
document.querySelectorAll(".abas button").forEach((b) => b.addEventListener("click", () => trocarAba(b.dataset.aba)));
$("#dFechar").addEventListener("click", () => $("#detalhe").close());

iniciar();
