"""Interface Streamlit do Tech Lead Agêntico.

Executar:  streamlit run app.py
Mostra, para cada resposta: a trajetória de ferramentas (com o tipo de cada uma), o
relatório de verificação (afirmações, NLI, coerência) e as memórias de longo prazo usadas.
Registros no backlog e issues no GitHub só acontecem depois do clique em "Aprovar".
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from fabrica_agentica.config import descrever_ambiente, modo_demo, provedor

st.set_page_config(page_title="Tech Lead Agêntico", page_icon="🛠️", layout="wide")


@st.cache_resource(show_spinner="Carregando modelos locais (embeddings, NLI e índice FAISS)...")
def aquecer_modelos() -> bool:
    from fabrica_agentica.ferramentas import rag
    from fabrica_agentica.verificacao.verificador import _modelo_nli

    rag.carregar_indice()
    _modelo_nli()
    return True


def novo_agente(usuario: str, motor: str, verificar: bool):
    from fabrica_agentica.agentes.integrador import TechLeadAgentico

    return TechLeadAgentico(usuario=usuario, motor=motor, verificar_respostas=verificar)


# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.title("🛠️ Tech Lead Agêntico")
    st.caption("1º agente da fábrica agêntica de software · NovaForja (empresa fictícia)")
    if modo_demo():
        st.warning("Modo demonstração: modelo roteirizado, sem chave de API e sem custo.")
    usuario = st.text_input("Usuário (escopo da memória de longo prazo)", value="adriano")
    motor = st.radio("Motor do agente", ["executor", "langgraph"], format_func={
        "executor": "AgentExecutor + RunnableWithMessageHistory", "langgraph": "LangGraph (create_agent + HITL)"}.get)
    verificar = st.toggle("Verificar respostas (NLI + coerência)", value=True)
    configuracao = (usuario, motor, verificar)
    if st.button("🆕 Nova sessão", use_container_width=True) or st.session_state.get("configuracao") != configuracao:
        st.session_state.configuracao = configuracao
        st.session_state.agente = novo_agente(*configuracao)
        st.session_state.mensagens = []
        st.session_state.decisoes = {}
    if st.button("💾 Encerrar sessão (gravar episódio)", use_container_width=True):
        episodio = st.session_state.agente.encerrar_sessao()
        st.success(f"Episódio gravado: {episodio['conteudo'] if episodio else 'sessão vazia'}")
    with st.expander("⚙️ Ambiente"):
        st.code(descrever_ambiente())
        st.caption(f"Sessão: {st.session_state.agente.sessao_id}")
    with st.expander("🧠 Memória de longo prazo"):
        for m in st.session_state.agente.memoria_longa.listar():
            st.markdown(f"- `{m['tipo']}` {m['conteudo']}")
    st.markdown(
        "<br>" * 5
        + "<div style='font-size:0.85em; opacity:0.75'>©2026 Adriano de Carvalho<br><br>"
        "MBA Engenharia de IA<br>Instituto Infnet</div>",
        unsafe_allow_html=True,
    )

aquecer_modelos()
agente = st.session_state.agente


# ------------------------------------------------------------------ painéis de cada resposta
def painel_turno(turno: dict, indice: int) -> None:
    v = turno.get("verificacao")
    if v:
        selo = "✅ Verificação: APROVADA" if v["aprovado"] else "⚠️ Verificação: REPROVADA"
        if turno.get("corrigida"):
            selo += " (resposta corrigida automaticamente)"
        st.caption(selo)
    colunas = st.columns(3)
    with colunas[0].expander(f"🔧 Trajetória ({len(turno['trajetoria'])} ferramentas)"):
        if turno["trajetoria"]:
            st.dataframe(pd.DataFrame([{"tipo": p["tipo"], "ferramenta": p["ferramenta"], "argumentos": json.dumps(p["argumentos"], ensure_ascii=False)[:120]}
                                       for p in turno["trajetoria"]]), hide_index=True, use_container_width=True)
        else:
            st.write("Nenhuma ferramenta usada neste turno.")
    with colunas[1].expander("🛡️ Verificação"):
        if v:
            st.dataframe(pd.DataFrame([{"tipo": a["tipo"], "NLI": a["nli"], "contradição": a["prob_contradicao"], "afirmação": a["texto"]}
                                       for a in v["afirmacoes"]]), hide_index=True, use_container_width=True)
            st.markdown(f"**Coerência lógica:** {v['coerencia']['veredito']} · falhas: {', '.join(v['coerencia']['falhas'])}")
            if v["motivos"]:
                st.markdown("**Motivos da reprovação:** " + " | ".join(v["motivos"]))
            st.caption(v["coerencia"]["justificativa"])
            if turno.get("corrigida") and turno.get("verificacao_rascunho"):
                st.markdown("**Rascunho reprovado:**")
                st.caption(turno["resposta_rascunho"][:1500])
                st.markdown("**Motivos:** " + " | ".join(turno["verificacao_rascunho"]["motivos"]))
        else:
            st.write("Sem ferramentas neste turno: nada a verificar.")
    with colunas[2].expander(f"🧠 Memórias usadas ({len(turno['memorias_usadas'])})"):
        for m in turno["memorias_usadas"] or ["(nenhuma)"]:
            st.markdown(f"- {m}")

    for j, pendencia in enumerate(turno.get("pendencias", [])):
        chave = f"{indice}-{j}"
        with st.container(border=True):
            st.markdown("**📝 Aprovação humana necessária**")
            if pendencia.get("tipo") == "langgraph_hitl":
                st.json(pendencia["requisicao"], expanded=False)
            else:
                st.markdown(f"Projeto **{pendencia['projeto']}** · sprint {pendencia['sprint']} · {pendencia['total_pontos']} pontos · "
                            f"abrir issues: {'sim' if pendencia['abrir_issues'] else 'não'}")
                for h in pendencia["historias"]:
                    st.markdown(f"- {h}")
            decisao = st.session_state.decisoes.get(chave)
            if decisao:
                if decisao.startswith("Aprovado"):
                    st.success(decisao)
                else:
                    st.info(decisao)
            else:
                c1, c2 = st.columns(2)
                if c1.button("✅ Aprovar e gravar", key=f"ok-{chave}"):
                    with st.spinner("Gravando no backlog e abrindo issues..."):
                        r = agente.aprovar(pendencia, aprovado_por=usuario)
                    issues = r.get("issues") if isinstance(r, dict) else None
                    texto = f"Aprovado: {len(r.get('historias_criadas', []))} histórias gravadas" if "historias_criadas" in r else f"Aprovado. {r.get('resposta', '')[:400]}"
                    if issues:
                        texto += " · issues: " + ", ".join(f"[#{i['numero']}]({i['url']})" if str(i.get("url", "")).startswith("http") else f"#{i['numero']} ({i.get('modo')})" for i in issues)
                    st.session_state.decisoes[chave] = texto
                    st.rerun()
                if c2.button("❌ Rejeitar", key=f"no-{chave}"):
                    agente.rejeitar(pendencia, "Rejeitado na interface.")
                    st.session_state.decisoes[chave] = "Rejeitado: nada foi gravado."
                    st.rerun()


# ------------------------------------------------------------------ chat
st.header("Planeje demandas, consulte o backlog, normas e bibliotecas")
st.caption(f"Provedor: **{provedor()}** · motor: **{motor}** · verificação: **{'ligada' if verificar else 'desligada'}**")

for i, (papel, texto, turno) in enumerate(st.session_state.mensagens):
    with st.chat_message(papel):
        st.markdown(texto)
        if turno:
            painel_turno(turno, i)

if pergunta := st.chat_input("Ex.: Quero login com Google no projeto Portal na próxima sprint."):
    st.session_state.mensagens.append(("user", pergunta, None))
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"):
        from langchain_community.callbacks.streamlit import StreamlitCallbackHandler

        agente.callbacks = [StreamlitCallbackHandler(st.container(), expand_new_thoughts=False)]
        with st.spinner("Pensando, consultando ferramentas e verificando a resposta..."):
            turno = agente.conversar(pergunta)
        from fabrica_agentica.agentes.integrador import turno_como_dict

        dados = turno_como_dict(turno)
        st.markdown(turno.resposta)
        st.caption(f"⏱️ {turno.duracao_s}s")
        painel_turno(dados, len(st.session_state.mensagens))
    st.session_state.mensagens.append(("assistant", turno.resposta, dados))
    st.rerun()
