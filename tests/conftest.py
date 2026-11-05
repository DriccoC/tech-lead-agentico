"""Os testes rodam SEMPRE em modo demonstração: sem chaves, sem rede e sem custo.

Banco de backlog e memórias usam cópias temporárias, para não alterar os dados do projeto.
"""

import os
import shutil
import sys
from pathlib import Path

os.environ["LLM_PROVIDER"] = "demo"
os.environ["APIS_OFFLINE"] = "1"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["GITHUB_ESCRITA_REAL"] = "0"

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pytest  # noqa: E402


@pytest.fixture()
def banco_temporario(tmp_path, monkeypatch):
    """Cópia do backlog.db + memória isolada, restaurando os caminhos depois."""
    from fabrica_agentica import config
    from fabrica_agentica.ferramentas import acoes, apis, sql

    copia = tmp_path / "backlog.db"
    shutil.copy(config.CAMINHO_BANCO, copia)
    monkeypatch.setattr(config, "CAMINHO_BANCO", copia)
    monkeypatch.setattr(acoes, "CAMINHO_BANCO", copia)
    monkeypatch.setattr(acoes, "CAMINHO_MEMORIA", tmp_path / "memoria.db")
    monkeypatch.setattr(apis, "CAMINHO_LOGS", tmp_path)
    original = sql.conexao_leitura
    monkeypatch.setattr(sql, "conexao_leitura", lambda caminho=copia: original(caminho))
    return copia
