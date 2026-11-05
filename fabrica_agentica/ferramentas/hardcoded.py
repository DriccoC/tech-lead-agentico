"""Funções hardcoded (determinísticas): mesma entrada, mesma saída, sem custo de tokens.

Usadas quando a precisão é inegociável: as regras vêm do Manual de Engenharia
(MAN-04 e MAN-06), e o LLM nunca deve calcular esses valores "de cabeça".
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, timedelta

RESERVA_DEFEITOS = 0.20  # MAN-06 §3
PONTOS_POR_DIA_IDEAL = 1.0  # MAN-06 §3
SEQUENCIA_FIBONACCI = (1, 2, 3, 5, 8, 13)  # MAN-06 §2
LIMITE_PONTOS_HISTORIA = 8  # MAN-06 §2


@dataclass
class Integrante:
    nome: str
    fator_foco: float
    dias_ausencia: int = 0


def dias_uteis(inicio: date, fim: date, feriados: set[date]) -> list[date]:
    """Dias de segunda a sexta entre início e fim (inclusive), sem feriados."""
    dias, atual = [], inicio
    while atual <= fim:
        if atual.weekday() < 5 and atual not in feriados:
            dias.append(atual)
        atual += timedelta(days=1)
    return dias


def calcular_capacidade(integrantes: list[Integrante], n_dias_uteis: int, pontos_comprometidos: int) -> dict:
    """Capacidade da sprint conforme MAN-06 §3.

    bruta   = Σ (dias úteis − ausências) × fator de foco × 1 ponto/dia ideal
    líquida = floor(bruta × 0,80)   (20% reservados para defeitos e imprevistos)
    saldo   = líquida − pontos já comprometidos
    """
    detalhe = []
    bruta = 0.0
    for p in integrantes:
        dias = max(n_dias_uteis - p.dias_ausencia, 0)
        contribuicao = dias * p.fator_foco * PONTOS_POR_DIA_IDEAL
        bruta += contribuicao
        detalhe.append({"integrante": p.nome, "dias_disponiveis": dias, "fator_foco": p.fator_foco, "pontos": round(contribuicao, 2)})
    liquida = math.floor(bruta * (1 - RESERVA_DEFEITOS) + 1e-9)
    return {
        "dias_uteis": n_dias_uteis,
        "capacidade_bruta": round(bruta, 2),
        "reserva_defeitos": round(bruta * RESERVA_DEFEITOS, 2),
        "capacidade_liquida": liquida,
        "pontos_comprometidos": pontos_comprometidos,
        "saldo_disponivel": liquida - pontos_comprometidos,
        "detalhe": detalhe,
    }


def _partes_versao(versao: str) -> tuple[int, int, int]:
    numeros = [int(n) for n in re.findall(r"\d+", versao)[:3]]
    while len(numeros) < 3:
        numeros.append(0)
    return tuple(numeros)  # type: ignore[return-value]


def comparar_versoes(versao_atual: str, versao_mais_recente: str) -> dict:
    """Compara duas versões semânticas e aplica a regra de defasagem do MAN-04 §2.3.

    Conforme: ser a mais recente estável ou estar no máximo uma versão MINOR atrás
    (mesma MAJOR).
    """
    a, r = _partes_versao(versao_atual), _partes_versao(versao_mais_recente)
    if a >= r:
        situacao, conforme = "atualizada", True
    elif a[0] < r[0]:
        situacao, conforme = "defasada em versão MAJOR", False
    elif r[1] - a[1] <= 1:
        situacao, conforme = "até uma versão MINOR atrás", True
    else:
        situacao, conforme = f"defasada em {r[1] - a[1]} versões MINOR", False
    return {"versao_atual": versao_atual, "versao_mais_recente": versao_mais_recente, "situacao": situacao, "conforme_MAN_04": conforme}


def classificar_cvss(pontuacao: float | None) -> dict:
    """Faixa de severidade CVSS v3 (MAN-04 §3) e se bloqueia a adoção (MAN-04 §2.1)."""
    if pontuacao is None:
        return {"cvss": None, "severidade": "desconhecida", "bloqueia_adocao": False}
    p = float(pontuacao)
    if p == 0:
        faixa = "nenhuma"
    elif p < 4.0:
        faixa = "baixa"
    elif p < 7.0:
        faixa = "media"
    elif p < 9.0:
        faixa = "alta"
    else:
        faixa = "critica"
    return {"cvss": p, "severidade": faixa, "bloqueia_adocao": p >= 7.0}


def validar_estimativa(pontos: int) -> dict:
    """Valida uma estimativa contra o MAN-06 §2 (Fibonacci e limite de 8 pontos)."""
    return {
        "pontos": pontos,
        "na_sequencia_fibonacci": pontos in SEQUENCIA_FIBONACCI,
        "precisa_decompor": pontos > LIMITE_PONTOS_HISTORIA,
    }
