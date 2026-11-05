"""Evidências da verificação: as saídas das ferramentas do turno, em frases.

O modelo NLI compara frases em linguagem natural; um JSON como {"saldo_disponivel": 14}
não "implica" a frase "restam 14 pontos". Por isso cada saída de ferramenta é
verbalizada em frases simples em português (a "premissa" do NLI). Os números também são
coletados para o fact-checking determinístico.
"""

from __future__ import annotations

import json
import re
from typing import Any


def _json(conteudo: Any) -> Any:
    if isinstance(conteudo, (dict, list)):
        return conteudo
    try:
        return json.loads(conteudo)
    except (TypeError, ValueError):
        return conteudo


def verbalizar(ferramenta: str, saida: Any) -> list[str]:
    d = _json(saida)
    frases: list[str] = []
    if isinstance(d, dict) and d.get("erro"):
        return [f"A ferramenta {ferramenta} retornou erro: {d['erro']}"]
    if ferramenta == "calcular_capacidade_sprint" and isinstance(d, dict) and "saldo_disponivel" in d:
        removidos = d.get("integrantes_removidos_na_simulacao") or []
        cenario = f" na simulação sem {', '.join(removidos)}" if removidos else ""
        frases += [
            f"A sprint {d['sprint']} do {d['projeto']} tem {d['dias_uteis']} dias úteis{cenario}.",
            f"A capacidade bruta da sprint {d['sprint']} é de {d['capacidade_bruta']} pontos{cenario}.",
            f"A capacidade líquida da sprint {d['sprint']} é de {d['capacidade_liquida']} pontos{cenario}.",
            f"Há {d['pontos_comprometidos']} pontos já comprometidos na sprint {d['sprint']}.",
            f"O saldo disponível da sprint {d['sprint']} é de {d['saldo_disponivel']} pontos{cenario}.",
        ]
        frases += [f"O feriado {f['name']} em {f['date']} cai em dia útil da sprint." for f in d.get("feriados_em_dia_util", [])]
    elif ferramenta == "consultar_pypi" and isinstance(d, dict):
        if d.get("encontrado"):
            frases.append(f"A versão estável mais recente de {d['pacote']} no PyPI é a {d['versao_mais_recente']}.")
            frases += [f"A versão {v['versao']} de {d['pacote']} foi publicada em {v['data']}." for v in d.get("ultimas_versoes", [])]
        else:
            frases.append(f"O pacote {d.get('pacote')} não foi encontrado no PyPI.")
    elif ferramenta == "consultar_vulnerabilidades" and isinstance(d, dict):
        if d.get("total"):
            frases.append(f"A versão {d['versao']} de {d['pacote']} tem {d['total']} vulnerabilidades conhecidas, com CVSS máximo de {d.get('maior_cvss')}.")
            frases.append(f"A versão {d['versao']} de {d['pacote']} não é segura.")
            for v in d.get("vulnerabilidades", []):
                apelidos = f" ({', '.join(v.get('aliases', []))})" if v.get("aliases") else ""
                corrigida = f", corrigida em {', '.join(v['corrigida_em'])}" if v.get("corrigida_em") else ""
                frases.append(f"Vulnerabilidade {v['id']}{apelidos} em {d['pacote']} {d['versao']}: CVSS {v.get('cvss')}{corrigida}. {v.get('resumo', '')}")
        else:
            frases.append(f"A versão {d.get('versao')} de {d.get('pacote')} não tem vulnerabilidades conhecidas.")
    elif ferramenta == "classificar_cvss" and isinstance(d, dict):
        bloqueia = "bloqueia" if d.get("bloqueia_adocao") else "não bloqueia"
        frases.append(f"O CVSS {d.get('cvss')} tem severidade {d.get('severidade')} e {bloqueia} a adoção do componente.")
    elif ferramenta == "comparar_versoes" and isinstance(d, dict):
        conforme = "está conforme" if d.get("conforme_MAN_04") else "não está conforme"
        frases.append(f"A versão {d['versao_atual']} está {d['situacao']} em relação à {d['versao_mais_recente']} e {conforme} o MAN-04.")
    elif ferramenta == "buscar_manual_engenharia" and isinstance(d, dict):
        for r in d.get("resultados", [])[:4]:
            if r.get("similaridade") != "baixa":
                frases += [f"{r['doc_id']} ({r['chunk_id']}): {s.strip()}" for s in re.split(r"(?<=[.;:])\s+", r["trecho"]) if len(s.strip()) > 25]
    elif ferramenta == "buscar_issues_github" and isinstance(d, dict):
        frases += [f"A issue #{i['numero']} '{i['titulo']}' está {i['estado']}." for i in d.get("issues", [])]
        if not d.get("issues"):
            frases.append("Não foram encontradas issues relacionadas no GitHub.")
    elif ferramenta == "consultar_backlog_sql" and isinstance(d, dict) and d.get("ok"):
        frases += ["Registro do backlog: " + "; ".join(f"{k} = {v}" for k, v in linha.items()) + "." for linha in d.get("linhas", [])[:25]]
    elif ferramenta == "decompor_demanda" and isinstance(d, dict) and d.get("plano"):
        p = d["plano"]
        frases.append(f"O plano proposto '{p['epico']}' tem {len(p['historias'])} histórias e soma {d['total_pontos']} pontos.")
        frases.append(f"As histórias do plano proposto ainda não estão registradas e não fazem parte dos pontos já comprometidos.")
        frases += [f"A história '{h['titulo'][:90]}' tem {h['pontos']} pontos." for h in p["historias"]]
    elif ferramenta == "propor_registro_backlog" and isinstance(d, dict):
        frases.append(f"Foi criada a pendência {d.get('pendencia_id')} aguardando aprovação humana; nada foi gravado ainda.")
    elif ferramenta == "consultar_feriados" and isinstance(d, list):
        frases += [f"{f['date']} é feriado nacional: {f['name']}." for f in d]
    elif isinstance(d, str):
        frases.append(d[:600])
    return frases


def regras_procedurais() -> list[str]:
    """Regras do system prompt (memória procedural), que também valem como evidência."""
    from fabrica_agentica.prompts import CONTEXTO

    return [f"Regra procedural do agente: {l.strip()[3:]}" for l in CONTEXTO.splitlines() if l.strip()[:2].rstrip(".").isdigit()]


def coletar(passos: list[tuple]) -> list[str]:
    """Frases de evidência a partir de intermediate_steps [(AgentAction, observação)]."""
    frases: list[str] = []
    for acao, observacao in passos:
        nome = getattr(acao, "tool", None) or (acao.get("ferramenta") if isinstance(acao, dict) else str(acao))
        frases += verbalizar(nome, observacao)
    return list(dict.fromkeys(frases))


NUMERO = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)(?![\w])")


def numeros(texto: str) -> set[float]:
    achados = set()
    for n in NUMERO.findall(texto):
        try:
            achados.add(float(n.replace(",", ".")))
        except ValueError:
            pass
    return achados
