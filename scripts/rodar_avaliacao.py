"""Roda a avaliação do agente integrador em dois experimentos e salva os resultados.

Experimentos (mesmo dataset, mesmo agente; muda só a transformação de consulta do RAG):
  A) com transformação multi-query + HyDE (configuração adotada)
  B) sem transformação (busca direta com a consulta do agente)

Uso:  python scripts/rodar_avaliacao.py                    (A e B no LangSmith, se houver LANGSMITH_API_KEY)
      python scripts/rodar_avaliacao.py --so pos-correcao  (só o experimento C)
      python scripts/rodar_avaliacao.py --local            (sem LangSmith)
Saída: relatorio/avaliacao/resultados_<experimento>.csv e resumo.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from fabrica_agentica.config import RAIZ  # noqa: E402
from fabrica_agentica.observabilidade import avaliacao  # noqa: E402

SAIDA = RAIZ / "relatorio" / "avaliacao"
EXPERIMENTOS = {
    "com-transformacao": "multi-query+hyde",   # A
    "sem-transformacao": "nenhuma",            # B
    "pos-correcao": "nenhuma",                 # C: após corrigir o preenchimento de lacunas (rodar com --so pos-correcao)
}


def linhas_langsmith(resultados) -> list[dict]:
    linhas = []
    for r in resultados:
        run, exemplo = r["run"], r["example"]
        notas = {e.key: e.score for e in r["evaluation_results"]["results"]}
        comentarios = {f"coment_{e.key}": e.comment for e in r["evaluation_results"]["results"] if e.comment}
        latencia = (run.end_time - run.start_time).total_seconds() if run.end_time and run.start_time else None
        linhas.append({
            "categoria": (exemplo.metadata or {}).get("categoria"), "input": exemplo.inputs["input"], **notas,
            "ferramentas": (run.outputs or {}).get("ferramentas"), "latencia_s": latencia,
            "tokens_total": getattr(run, "total_tokens", None), "custo_usd": getattr(run, "total_cost", None), **comentarios,
        })
    return linhas


def main(local: bool, somente: list[str]) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    arquivo_resumo = SAIDA / "resumo.json"
    resumo = json.loads(arquivo_resumo.read_text(encoding="utf-8")) if arquivo_resumo.exists() else {}
    for nome, transformacao in EXPERIMENTOS.items():
        if somente and nome not in somente:
            continue
        inicio = time.time()
        if local or not os.getenv("LANGSMITH_API_KEY"):
            linhas, url = avaliacao.avaliar_local(transformacao), None
        else:
            resultados = avaliacao.avaliar_langsmith(f"tech-lead-{nome}", transformacao)
            linhas, url = linhas_langsmith(resultados), getattr(resultados, "url", None) or str(getattr(resultados, "experiment_name", ""))
        df = pd.DataFrame(linhas)
        df.to_csv(SAIDA / f"resultados_{nome}.csv", index=False)
        metricas = [c for c in ("cobertura_trajetoria", "trajetoria_exata", "corretude", "verificacao_final", "verificacao_rascunho", "corrigida") if c in df]
        resumo[nome] = {
            "transformacao": transformacao, "experimento": url, "minutos": round((time.time() - inicio) / 60, 1),
            "medias": {m: round(float(pd.to_numeric(df[m], errors="coerce").mean()), 3) for m in metricas},
            "por_categoria": {m: df.groupby("categoria")[m].apply(lambda s: round(float(pd.to_numeric(s, errors="coerce").mean()), 3)).to_dict() for m in metricas},
            "latencia_media_s": round(float(pd.to_numeric(df.get("latencia_s"), errors="coerce").mean()), 1) if "latencia_s" in df else None,
        }
        print(nome, json.dumps(resumo[nome]["medias"], ensure_ascii=False))
        arquivo_resumo.write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    args = sys.argv[1:]
    somente = args[args.index("--so") + 1].split(",") if "--so" in args else ["com-transformacao", "sem-transformacao"]
    main(local="--local" in args, somente=somente)
