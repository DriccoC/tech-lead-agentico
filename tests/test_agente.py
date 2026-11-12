import json
import sqlite3

from langchain_core.exceptions import OutputParserException
import pytest

from fabrica_agentica.esquemas import AnaliseDemanda, PlanoTrabalho


# ------------------------------------------------------------------ Fase 1: chain e parser
def test_chain_lcel_e_imperativa_devolvem_esquema():
    from fabrica_agentica.chains.fase1 import analisar_demanda_imperativa, chain_analise_lcel

    d = "Quero login com Google no projeto Portal."
    assert isinstance(chain_analise_lcel().invoke({"demanda": d}), AnaliseDemanda)
    assert isinstance(analisar_demanda_imperativa.invoke(d), AnaliseDemanda)


def test_parser_rejeita_json_incompleto():
    from fabrica_agentica.chains.fase1 import parser_analise

    with pytest.raises(OutputParserException):
        parser_analise.parse('{"resumo": "faltam campos"}')


# ------------------------------------------------------------------ Fase 3: intenção e fluxos
def test_lacunas_do_fluxo():
    from fabrica_agentica.memoria import intencao

    assert intencao.lacunas("planejar_demanda", {}) and not intencao.lacunas("planejar_demanda", {"projeto": "Portal"})
    assert intencao.entidades_da_trajetoria([{"argumentos": {"pacote": "authlib", "projeto": "Portal"}}]) == {"pacote": "authlib", "projeto": "Portal"}


def test_memoria_longo_prazo_atualiza_em_vez_de_duplicar(tmp_path):
    from fabrica_agentica.memoria.longo_prazo import MemoriaLongoPrazo

    m = MemoriaLongoPrazo("teste", caminho=tmp_path / "m.db")
    m.lembrar("Adriano prefere histórias de no máximo 5 pontos.")
    r = m.lembrar("Adriano prefere histórias de no máximo 3 pontos.")
    assert r["acao"] == "atualizada" and len(m.listar()) == 1
    m.lembrar("O time usa pytest.")
    assert len(m.listar()) == 2


def test_historico_sqlite_e_janela_com_resumo(tmp_path):
    from fabrica_agentica.memoria.historico import HistoricoSQLite, comprimir

    h = HistoricoSQLite("s1", caminho=tmp_path / "h.db")
    for i in range(5):
        h.add_user_message(f"pergunta {i}")
        h.add_ai_message(f"resposta {i}")
    h.substituir_ultima_resposta("resposta corrigida")
    assert h.messages[-1].content == "resposta corrigida" and len(h.messages) == 10
    comprimidas = comprimir(h.messages, "s1", janela=4)
    assert len(comprimidas) == 5 and comprimidas[0].content.startswith("[Contexto] Resumo")


# ------------------------------------------------------------------ Fase 5: verificação
def _evidencias():
    from fabrica_agentica.ferramentas.catalogo import calcular_capacidade_sprint, consultar_vulnerabilidades
    from fabrica_agentica.verificacao.evidencias import verbalizar

    ev = verbalizar("calcular_capacidade_sprint", calcular_capacidade_sprint.invoke({"projeto": "Portal", "remover_integrantes": ["Bruno"]}))
    return ev + verbalizar("consultar_vulnerabilidades", consultar_vulnerabilidades.invoke({"pacote": "authlib", "versao": "1.3.0"}))


def test_nli_detecta_contradicao_de_fato():
    from fabrica_agentica.verificacao.verificador import nli

    p = "A versão 1.3.0 de authlib tem 34 vulnerabilidades conhecidas, com CVSS máximo de 9.1."
    assert nli(p, "A authlib 1.3.0 não tem vulnerabilidades.")["contradiction"] > 0.8
    assert nli(p, "A authlib 1.3.0 tem vulnerabilidades conhecidas.")["entailment"] > 0.6


def test_verificador_reprova_resposta_forjada_e_contradicao_interna():
    from fabrica_agentica.verificacao.verificador import verificar

    ev = _evidencias()
    assert not verificar("A authlib 1.3.0 não tem vulnerabilidades e pode ser usada.", ev).aprovado
    assert not verificar("Sim, o plano ainda cabe sem o Bruno. Sem o Bruno o plano não cabe, faltam 2 pontos.", ev).aprovado


# ------------------------------------------------------------------ ações com aprovação humana
def test_nada_e_gravado_sem_aprovacao(banco_temporario):
    from fabrica_agentica.ferramentas import acoes

    plano = PlanoTrabalho(epico="Teste", objetivo="x", riscos=[], historias=[
        {"titulo": "Como usuário, quero A, para B", "criterios_aceite": ["Dado x, quando y, então z"], "pontos": 3, "tarefas": ["t"]}])
    contar = lambda: sqlite3.connect(banco_temporario).execute("SELECT COUNT(*) FROM historias").fetchone()[0]
    antes = contar()
    pendencia = acoes.propor_registro(plano, "Portal", 13)
    assert contar() == antes and pendencia["status"] == "aguardando_aprovacao"
    resultado = acoes.executar_registro(pendencia["pendencia_id"], aprovado_por="teste")
    assert contar() == antes + 1 and resultado["issues"][0]["modo"] == "simulado"
    with pytest.raises(ValueError):
        acoes.executar_registro(pendencia["pendencia_id"], aprovado_por="teste")  # não executa duas vezes


# ------------------------------------------------------------------ avaliação
def test_avaliadores_de_trajetoria():
    from fabrica_agentica.observabilidade.avaliacao import cobertura_trajetoria, trajetoria_exata

    ex = {"outputs": {"ferramentas": ["consultar_pypi", "consultar_vulnerabilidades"]}}
    assert cobertura_trajetoria({"ferramentas": ["consultar_pypi"]}, ex)["score"] == 0.5
    assert trajetoria_exata({"ferramentas": ["consultar_vulnerabilidades", "consultar_pypi"]}, ex)["score"] == 1
    assert cobertura_trajetoria({"ferramentas": []}, {"outputs": {"ferramentas": []}})["score"] == 1.0


def test_agente_integrador_modo_demo(tmp_path, monkeypatch):
    from fabrica_agentica.memoria import historico, longo_prazo

    monkeypatch.setattr(historico, "CAMINHO_HISTORICO", tmp_path / "h.db")
    monkeypatch.setattr(longo_prazo, "CAMINHO_MEMORIA", tmp_path / "m.db")
    from fabrica_agentica.agentes.integrador import TechLeadAgentico

    agente = TechLeadAgentico(usuario="pytest", gravar_memorias=False)
    turno = agente.conversar("Qual o saldo de pontos da sprint 13 do Portal?")
    assert "calcular_capacidade_sprint" in turno.ferramentas and "14" in turno.resposta
    assert turno.verificacao is not None and turno.verificacao.aprovado
    assert json.loads(json.dumps(turno.trajetoria, default=str))


def test_progresso_amigavel_no_modo_demo(tmp_path, monkeypatch):
    from fabrica_agentica.memoria import historico, longo_prazo
    from fabrica_agentica.observabilidade.progresso import ETAPAS, ProgressoCallback, mensagem_ferramenta

    assert "feriados" in mensagem_ferramenta("calcular_capacidade_sprint", {"projeto": "Portal", "numero_sprint": 13})
    assert "pyjwt 2.8.0" in mensagem_ferramenta("consultar_vulnerabilidades", {"pacote": "pyjwt", "versao": "2.8.0"})

    monkeypatch.setattr(historico, "CAMINHO_HISTORICO", tmp_path / "h.db")
    monkeypatch.setattr(longo_prazo, "CAMINHO_MEMORIA", tmp_path / "m.db")
    from fabrica_agentica.agentes.integrador import TechLeadAgentico

    avisos: list[str] = []
    agente = TechLeadAgentico(usuario="pytest", gravar_memorias=False)
    agente.ao_progresso = lambda etapa: avisos.append(ETAPAS[etapa])
    agente.callbacks = [ProgressoCallback(avisos.append)]
    agente.conversar("Qual o saldo de pontos da sprint 13 do Portal?")
    texto = " | ".join(avisos)
    assert avisos[0] == ETAPAS["entender"] and "Calculando a capacidade da sprint 13 do Portal" in texto
    assert texto.index("Calculando") < texto.index("Verificando a resposta")


def test_progresso_langgraph_e_duracao_do_esclarecimento(tmp_path, monkeypatch):
    """No LangGraph o aviso de ferramenta vem de outra thread (a interface reanexa o contexto); aqui
    garantimos que ele é disparado. E o turno de esclarecimento precisa registrar a duração."""
    from fabrica_agentica.memoria import historico, longo_prazo
    from fabrica_agentica.observabilidade.progresso import ProgressoCallback

    monkeypatch.setattr(historico, "CAMINHO_HISTORICO", tmp_path / "h.db")
    monkeypatch.setattr(longo_prazo, "CAMINHO_MEMORIA", tmp_path / "m.db")
    from fabrica_agentica.agentes.integrador import TechLeadAgentico

    avisos: list[str] = []
    agente = TechLeadAgentico(usuario="pytest-lg", motor="langgraph", gravar_memorias=False)
    agente.callbacks = [ProgressoCallback(avisos.append)]
    agente.conversar("Qual o saldo de pontos da sprint 13 do Portal?")
    assert any("Calculando a capacidade" in a for a in avisos)

    import itertools

    from fabrica_agentica.agentes import integrador

    novo = TechLeadAgentico(usuario="pytest-esc", gravar_memorias=False)
    relogio = itertools.count(0, 1.5)  # cada leitura do relógio avança 1,5 s (no modo demo o turno é instantâneo)
    monkeypatch.setattr(integrador.time, "perf_counter", lambda: next(relogio))
    turno = novo.conversar("Quero modo escuro.")
    assert turno.pediu_esclarecimento and turno.duracao_s > 0
