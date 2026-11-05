import json
import sqlite3
from datetime import date

import pytest

from fabrica_agentica.ferramentas import hardcoded, sql
from fabrica_agentica.ferramentas.catalogo import calcular_capacidade_sprint, consultar_pypi, consultar_vulnerabilidades


# ------------------------------------------------------------------ hardcoded
def test_dias_uteis_desconta_feriado():
    uteis = hardcoded.dias_uteis(date(2026, 11, 9), date(2026, 11, 20), {date(2026, 11, 20)})
    assert len(uteis) == 9


def test_capacidade_formula_man06():
    r = hardcoded.calcular_capacidade([hardcoded.Integrante("A", 0.5), hardcoded.Integrante("B", 1.0, dias_ausencia=2)], 10, 3)
    assert r["capacidade_bruta"] == 13.0  # 10*0.5 + 8*1.0
    assert r["capacidade_liquida"] == 10  # floor(13 * 0.8)
    assert r["saldo_disponivel"] == 7


def test_capacidade_sprint13_portal_e_simulacao_sem_bruno():
    r = json.loads(calcular_capacidade_sprint.invoke({"projeto": "Portal"}))
    assert (r["dias_uteis"], r["capacidade_liquida"], r["pontos_comprometidos"], r["saldo_disponivel"]) == (9, 25, 11, 14)
    sem = json.loads(calcular_capacidade_sprint.invoke({"projeto": "Portal", "remover_integrantes": ["Bruno"]}))
    assert (sem["capacidade_liquida"], sem["saldo_disponivel"]) == (20, 9)


@pytest.mark.parametrize("atual,recente,conforme", [("1.9.5", "1.9.5", True), ("1.8.0", "1.9.5", True), ("1.3.0", "1.9.5", False), ("0.9.0", "1.0.0", False)])
def test_comparar_versoes(atual, recente, conforme):
    assert hardcoded.comparar_versoes(atual, recente)["conforme_MAN_04"] is conforme


@pytest.mark.parametrize("cvss,faixa,bloqueia", [(0, "nenhuma", False), (3.9, "baixa", False), (6.9, "media", False), (7.0, "alta", True), (9.1, "critica", True)])
def test_classificar_cvss(cvss, faixa, bloqueia):
    r = hardcoded.classificar_cvss(cvss)
    assert (r["severidade"], r["bloqueia_adocao"]) == (faixa, bloqueia)


# ------------------------------------------------------------------ guardrail SQL
@pytest.mark.parametrize("consulta", ["DELETE FROM historias", "SELECT 1; DROP TABLE bugs", "UPDATE bugs SET status='x'", "PRAGMA table_info(bugs)"])
def test_guardrail_bloqueia(consulta):
    assert sql.executar_consulta(consulta)["ok"] is False


def test_guardrail_aceita_updated_at_e_texto_com_palavra_proibida():
    assert sql.executar_consulta("SELECT titulo, updated_at FROM historias")["ok"]
    assert sql.executar_consulta("SELECT titulo FROM historias WHERE titulo LIKE '%delete%'")["ok"]


def test_guardrail_adiciona_limit():
    assert sql.validar_consulta("SELECT * FROM bugs").endswith("LIMIT 50")


def test_conexao_somente_leitura():
    with pytest.raises(sqlite3.OperationalError):
        with sql.conexao_leitura() as conn:
            conn.execute("DELETE FROM bugs")


# ------------------------------------------------------------------ APIs (respostas gravadas)
def test_apis_offline():
    assert json.loads(consultar_pypi.invoke({"pacote": "authlib"}))["versao_mais_recente"] == "1.9.5"
    osv = json.loads(consultar_vulnerabilidades.invoke({"pacote": "authlib", "versao": "1.3.0"}))
    assert osv["total"] == 34 and osv["maior_cvss"] >= 9.0
