"""Clientes das APIs externas reais usadas pelo agente.

| API            | Uso                                             | Chave?                       |
|----------------|-------------------------------------------------|------------------------------|
| BrasilAPI      | feriados nacionais (afetam a capacidade)        | não                          |
| PyPI JSON      | versão estável mais recente de um pacote        | não                          |
| OSV.dev        | vulnerabilidades conhecidas de pacote + versão  | não                          |
| GitHub REST    | buscar issues (leitura) e abrir issues (escrita)| leitura: não; escrita: token |

Modo offline (APIS_OFFLINE=1 ou modo demo): as respostas vêm de fixtures gravadas em
demo/fixtures/, e as issues abertas ficam num arquivo local. É a alternativa "dummy"
exigida pelo enunciado para avaliação sem credenciais.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

import httpx

from fabrica_agentica.config import CAMINHO_FIXTURES, CAMINHO_LOGS, GITHUB_REPO, apis_offline

TEMPO_LIMITE = httpx.Timeout(10.0)
CABECALHOS = {"User-Agent": "fabrica-agentica-tech-lead/1.0 (projeto academico)"}


class ErroAPIExterna(RuntimeError):
    """Falha de rede ou resposta inesperada de uma API externa."""


def _fixture(nome: str) -> Any:
    caminho = CAMINHO_FIXTURES / f"{nome}.json"
    if not caminho.exists():
        raise ErroAPIExterna(f"Sem resposta gravada para '{nome}' no modo offline.")
    return json.loads(caminho.read_text(encoding="utf-8"))


def _get(url: str, **kwargs: Any) -> Any:
    try:
        resposta = httpx.get(url, timeout=TEMPO_LIMITE, headers={**CABECALHOS, **kwargs.pop("headers", {})}, **kwargs)
    except httpx.HTTPError as erro:
        raise ErroAPIExterna(f"Falha de rede ao acessar {url}: {erro}") from erro
    if resposta.status_code == 404:
        return None
    if resposta.status_code >= 400:
        raise ErroAPIExterna(f"HTTP {resposta.status_code} em {url}: {resposta.text[:200]}")
    return resposta.json()


# ------------------------------------------------------------------------------ feriados
def feriados_nacionais(ano: int) -> list[dict]:
    """Lista de feriados nacionais do ano: [{"date": "AAAA-MM-DD", "name": ...}]."""
    if apis_offline():
        return _fixture(f"feriados_{ano}")
    dados = _get(f"https://brasilapi.com.br/api/feriados/v1/{ano}")
    return [{"date": f["date"], "name": f["name"]} for f in dados or []]


# ------------------------------------------------------------------------------ PyPI
def consultar_pypi(pacote: str) -> dict:
    """Versão estável mais recente e datas das últimas versões de um pacote PyPI."""
    nome = pacote.strip().lower()
    if apis_offline():
        return _fixture(f"pypi_{nome}")
    dados = _get(f"https://pypi.org/pypi/{nome}/json")
    if dados is None:
        return {"pacote": nome, "encontrado": False}
    lancamentos = []
    for versao, arquivos in dados.get("releases", {}).items():
        if arquivos and not any(c.isalpha() for c in versao):  # ignora alfas, betas e rcs
            lancamentos.append((arquivos[0].get("upload_time", "")[:10], versao))
    lancamentos.sort(reverse=True)
    return {
        "pacote": nome,
        "encontrado": True,
        "versao_mais_recente": dados["info"]["version"],
        "resumo": dados["info"].get("summary", ""),
        "ultimas_versoes": [{"versao": v, "data": d} for d, v in lancamentos[:5]],
    }


# ------------------------------------------------------------------------------ OSV
def _pontuacao_cvss(vetor: str) -> float | None:
    try:
        from cvss import CVSS3, CVSS4

        if vetor.startswith("CVSS:4"):
            return float(CVSS4(vetor).base_score)
        if vetor.startswith("CVSS:3"):
            return float(CVSS3(vetor).scores()[0])
    except Exception:  # vetor malformado ou versão não suportada
        return None
    return None


def consultar_vulnerabilidades(pacote: str, versao: str) -> dict:
    """Vulnerabilidades conhecidas (base OSV) que afetam a versão informada."""
    nome, versao = pacote.strip().lower(), versao.strip()
    if apis_offline():
        return _fixture(f"osv_{nome}_{versao}")
    try:
        resposta = httpx.post(
            "https://api.osv.dev/v1/query",
            json={"package": {"name": nome, "ecosystem": "PyPI"}, "version": versao},
            timeout=TEMPO_LIMITE,
            headers=CABECALHOS,
        )
        resposta.raise_for_status()
    except httpx.HTTPError as erro:
        raise ErroAPIExterna(f"Falha ao consultar OSV: {erro}") from erro

    vulns = []
    for v in resposta.json().get("vulns", []):
        pontuacoes = [_pontuacao_cvss(s.get("score", "")) for s in v.get("severity", [])]
        pontuacoes = [p for p in pontuacoes if p is not None]
        corrigida_em = sorted(
            {e["fixed"] for a in v.get("affected", []) for r in a.get("ranges", []) for e in r.get("events", []) if "fixed" in e}
        )
        vulns.append(
            {
                "id": v["id"],
                "aliases": v.get("aliases", [])[:3],
                "resumo": v.get("summary", "")[:160],
                "cvss": max(pontuacoes) if pontuacoes else None,
                "severidade_rotulo": (v.get("database_specific") or {}).get("severity"),
                "corrigida_em": corrigida_em[:3],
            }
        )
    vulns.sort(key=lambda x: x["cvss"] or 0, reverse=True)
    return {"pacote": nome, "versao": versao, "total": len(vulns), "vulnerabilidades": vulns}


# ------------------------------------------------------------------------------ GitHub
def _token_github() -> str:
    return os.getenv("GITHUB_TOKEN", "").strip()


def buscar_issues_github(termo: str, repositorio: str = "", limite: int = 5) -> dict:
    """Busca issues (abertas ou fechadas) cujo título ou corpo contenha o termo."""
    repo = repositorio or GITHUB_REPO
    if apis_offline() or not repo:
        issues = _fixture("github_issues") + _issues_simuladas()
        termos = termo.lower().split()
        achadas = [i for i in issues if any(t in (i["titulo"] + " " + i.get("corpo", "")).lower() for t in termos)]
        return {"repositorio": repo or "(simulado)", "modo": "simulado", "issues": achadas[:limite]}

    cabecalhos = {"Accept": "application/vnd.github+json"}
    if _token_github():
        cabecalhos["Authorization"] = f"Bearer {_token_github()}"
    dados = _get(
        "https://api.github.com/search/issues",
        params={"q": f"repo:{repo} is:issue {termo}", "per_page": limite},
        headers=cabecalhos,
    )
    issues = [
        {"numero": i["number"], "titulo": i["title"], "estado": i["state"], "url": i["html_url"], "corpo": (i.get("body") or "")[:200]}
        for i in (dados or {}).get("items", [])
    ]
    return {"repositorio": repo, "modo": "ao vivo", "issues": issues}


def _arquivo_issues_simuladas():
    return CAMINHO_LOGS / "issues_simuladas.json"


def _issues_simuladas() -> list[dict]:
    arquivo = _arquivo_issues_simuladas()
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else []


def abrir_issue_github(titulo: str, corpo: str, rotulos: list[str] | None = None, repositorio: str = "") -> dict:
    """Abre uma issue. ATENÇÃO: só deve ser chamada após aprovação humana (ver acoes.py).

    Sem token, em modo offline ou com GITHUB_ESCRITA_REAL diferente de 1, a issue é registrada
    localmente (modo simulado). A escrita real exige ligar essa chave de propósito.
    """
    repo = repositorio or GITHUB_REPO
    escrita_real = os.getenv("GITHUB_ESCRITA_REAL", "0").strip() == "1"
    if apis_offline() or not repo or not _token_github() or not escrita_real:
        existentes = _issues_simuladas()
        numero = 1000 + len(existentes) + 1
        issue = {
            "numero": numero,
            "titulo": titulo,
            "estado": "open",
            "url": f"(simulada) issue #{numero}",
            "corpo": corpo[:200],
            "rotulos": rotulos or [],
            "criada_em": datetime.now().isoformat(timespec="seconds"),
        }
        CAMINHO_LOGS.mkdir(exist_ok=True)
        _arquivo_issues_simuladas().write_text(json.dumps(existentes + [issue], ensure_ascii=False, indent=1), encoding="utf-8")
        return {**issue, "modo": "simulado"}

    try:
        resposta = httpx.post(
            f"https://api.github.com/repos/{repo}/issues",
            json={"title": titulo, "body": corpo, "labels": rotulos or []},
            headers={**CABECALHOS, "Accept": "application/vnd.github+json", "Authorization": f"Bearer {_token_github()}"},
            timeout=TEMPO_LIMITE,
        )
        resposta.raise_for_status()
    except httpx.HTTPError as erro:
        raise ErroAPIExterna(f"Falha ao abrir issue no GitHub: {erro}") from erro
    dados = resposta.json()
    time.sleep(1)  # respeita o limite de criação de conteúdo da API do GitHub
    return {"numero": dados["number"], "titulo": dados["title"], "url": dados["html_url"], "modo": "ao vivo"}
