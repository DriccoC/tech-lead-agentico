"""Cria o banco de backlog (SQLite) da empresa fictícia NovaForja Software.

Uso:  python scripts/criar_banco.py
Recria dados/backlog.db do zero, sempre com os mesmos dados (reprodutível).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fabrica_agentica.config import CAMINHO_BANCO  # noqa: E402

ESQUEMA = """
CREATE TABLE projetos (
    projeto_id   INTEGER PRIMARY KEY,
    nome         TEXT NOT NULL UNIQUE,
    descricao    TEXT NOT NULL,
    stack        TEXT NOT NULL,
    repositorio  TEXT NOT NULL
);
CREATE TABLE desenvolvedores (
    dev_id       INTEGER PRIMARY KEY,
    nome         TEXT NOT NULL,
    papel        TEXT NOT NULL,          -- backend, frontend, fullstack, qa, mobile
    senioridade  TEXT NOT NULL           -- junior, pleno, senior
);
CREATE TABLE sprints (
    sprint_id    INTEGER PRIMARY KEY,
    projeto_id   INTEGER NOT NULL REFERENCES projetos(projeto_id),
    numero       INTEGER NOT NULL,
    inicio       TEXT NOT NULL,          -- AAAA-MM-DD
    fim          TEXT NOT NULL,
    status       TEXT NOT NULL           -- concluida, em_andamento, planejada
);
CREATE TABLE alocacoes (
    sprint_id     INTEGER NOT NULL REFERENCES sprints(sprint_id),
    dev_id        INTEGER NOT NULL REFERENCES desenvolvedores(dev_id),
    fator_foco    REAL NOT NULL,         -- fração do dia dedicada à sprint (0 a 1)
    dias_ausencia INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sprint_id, dev_id)
);
CREATE TABLE historias (
    historia_id    INTEGER PRIMARY KEY,
    projeto_id     INTEGER NOT NULL REFERENCES projetos(projeto_id),
    sprint_id      INTEGER REFERENCES sprints(sprint_id),   -- NULL = backlog
    epico          TEXT NOT NULL,
    titulo         TEXT NOT NULL,
    pontos         INTEGER NOT NULL,
    prioridade     TEXT NOT NULL,        -- alta, media, baixa
    status         TEXT NOT NULL,        -- backlog, a_fazer, em_andamento, concluida
    responsavel_id INTEGER REFERENCES desenvolvedores(dev_id),
    criado_em      TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE TABLE bugs (
    bug_id      INTEGER PRIMARY KEY,
    projeto_id  INTEGER NOT NULL REFERENCES projetos(projeto_id),
    titulo      TEXT NOT NULL,
    severidade  TEXT NOT NULL,           -- critica, alta, media, baixa
    status      TEXT NOT NULL,           -- aberto, em_correcao, resolvido
    aberto_em   TEXT NOT NULL
);
"""

PROJETOS = [
    (1, "Portal", "Portal do cliente (web) com autoatendimento e área logada",
     "Python 3.12, FastAPI, PostgreSQL, React", "novaforja/portal"),
    (2, "PagaFacil", "API de pagamentos e conciliação", "Java 21, Quarkus, PostgreSQL, Kafka",
     "novaforja/pagafacil"),
    (3, "AppCampo", "Aplicativo móvel para equipes de campo", "Flutter, Firebase, FastAPI",
     "novaforja/app-campo"),
]

DEVS = [
    (1, "Ana Souza", "backend", "senior"),
    (2, "Bruno Lima", "backend", "pleno"),
    (3, "Carla Mendes", "frontend", "pleno"),
    (4, "Diego Rocha", "qa", "pleno"),
    (5, "Eduarda Nunes", "fullstack", "senior"),
    (6, "Felipe Araujo", "backend", "senior"),
    (7, "Gabriela Torres", "mobile", "pleno"),
    (8, "Henrique Dias", "backend", "junior"),
]

SPRINTS = [
    # Portal
    (11, 1, 11, "2026-10-12", "2026-10-23", "concluida"),
    (12, 1, 12, "2026-10-26", "2026-11-06", "em_andamento"),
    (13, 1, 13, "2026-11-09", "2026-11-20", "planejada"),
    # PagaFacil
    (21, 2, 21, "2026-10-19", "2026-10-30", "concluida"),
    (22, 2, 22, "2026-11-02", "2026-11-13", "em_andamento"),
    # AppCampo
    (31, 3, 5, "2026-11-02", "2026-11-13", "em_andamento"),
]

ALOCACOES = [
    # Portal, sprint 11 e 12 (mesmo time)
    *[(s, d, f, 0) for s in (11, 12) for d, f in ((1, 0.7), (2, 0.8), (3, 0.8), (4, 0.6), (5, 0.75))],
    # Portal, sprint 13: Bruno com 2 dias de ausência (férias)
    (13, 1, 0.7, 0), (13, 2, 0.8, 2), (13, 3, 0.8, 0), (13, 4, 0.6, 0), (13, 5, 0.75, 0),
    # PagaFacil
    *[(s, d, f, 0) for s in (21, 22) for d, f in ((6, 0.8), (8, 0.9), (4, 0.3))],
    # AppCampo
    (31, 7, 0.9, 0), (31, 5, 0.25, 0),
]

H = "2026-10-01"
HISTORIAS = [
    # Portal - sprint 11 (concluída) -> velocidade 21
    (101, 1, 11, "Área logada", "Exibir faturas dos últimos 12 meses", 5, "alta", "concluida", 1, H, "2026-10-22"),
    (102, 1, 11, "Área logada", "Download de segunda via em PDF", 3, "media", "concluida", 3, H, "2026-10-21"),
    (103, 1, 11, "Cadastro", "Atualização de endereço com validação de CEP", 5, "media", "concluida", 2, H, "2026-10-23"),
    (104, 1, 11, "Cadastro", "Troca de e-mail com confirmação", 3, "media", "concluida", 5, H, "2026-10-20"),
    (105, 1, 11, "Observabilidade", "Painel de erros do front-end", 5, "baixa", "concluida", 3, H, "2026-10-23"),
    # Portal - sprint 12 (em andamento)
    (111, 1, 12, "Área logada", "Notificações de vencimento por e-mail", 5, "alta", "concluida", 1, H, "2026-11-03"),
    (112, 1, 12, "Área logada", "Preferências de notificação", 3, "media", "em_andamento", 5, H, "2026-11-04"),
    (113, 1, 12, "Autenticação", "Bloqueio após 5 tentativas de login", 5, "alta", "em_andamento", 2, H, "2026-11-04"),
    (114, 1, 12, "Acessibilidade", "Navegação por teclado no menu", 3, "media", "a_fazer", 3, H, "2026-10-26"),
    (115, 1, 12, "Observabilidade", "Rastreamento distribuído no backend", 5, "baixa", "a_fazer", 1, H, "2026-10-26"),
    # Portal - sprint 13 (planejada): 11 pontos já comprometidos
    (121, 1, 13, "Área logada", "Histórico de atendimentos", 5, "alta", "a_fazer", 5, H, "2026-11-02"),
    (122, 1, 13, "Acessibilidade", "Contraste alto e fonte ajustável", 3, "media", "a_fazer", 3, H, "2026-11-02"),
    (123, 1, 13, "Cadastro", "Exclusão de conta (LGPD)", 3, "alta", "a_fazer", 2, H, "2026-11-02"),
    # Portal - backlog sem sprint
    (131, 1, None, "Autenticação", "Integração com SSO corporativo dos clientes B2B", 13, "media", "backlog", None, H, H),
    (132, 1, None, "Autenticação", "Autenticação em dois fatores (MFA) por aplicativo", 8, "alta", "backlog", None, H, H),
    (133, 1, None, "Pagamentos", "Pagamento de fatura por Pix", 8, "alta", "backlog", None, H, H),
    # PagaFacil
    (201, 2, 21, "Conciliação", "Conciliação automática de boletos", 8, "alta", "concluida", 6, H, "2026-10-29"),
    (202, 2, 21, "Conciliação", "Relatório diário de divergências", 5, "media", "concluida", 8, H, "2026-10-30"),
    (203, 2, 22, "Pix", "Webhook de confirmação Pix", 8, "alta", "em_andamento", 6, H, "2026-11-04"),
    (204, 2, 22, "Pix", "Idempotência de cobranças", 5, "alta", "a_fazer", 8, H, "2026-11-02"),
    # AppCampo
    (301, 3, 31, "Ordens de serviço", "Modo offline com sincronização", 8, "alta", "em_andamento", 7, H, "2026-11-04"),
    (302, 3, 31, "Ordens de serviço", "Assinatura digital do cliente", 5, "media", "a_fazer", 7, H, "2026-11-02"),
]

BUGS = [
    (1, 1, "Sessão expira antes do tempo configurado", "alta", "aberto", "2026-11-03"),
    (2, 1, "Botão de segunda via some no Safari", "media", "em_correcao", "2026-10-29"),
    (3, 1, "Erro 500 ao salvar endereço sem complemento", "alta", "resolvido", "2026-10-20"),
    (4, 2, "Duplicidade em conciliação de boletos de fim de mês", "critica", "em_correcao", "2026-11-01"),
    (5, 3, "Sincronização falha com fotos acima de 10 MB", "media", "aberto", "2026-11-04"),
]


def criar(caminho: Path = CAMINHO_BANCO) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        caminho.unlink()
    with sqlite3.connect(caminho) as conn:
        conn.executescript(ESQUEMA)
        conn.executemany("INSERT INTO projetos VALUES (?,?,?,?,?)", PROJETOS)
        conn.executemany("INSERT INTO desenvolvedores VALUES (?,?,?,?)", DEVS)
        conn.executemany("INSERT INTO sprints VALUES (?,?,?,?,?,?)", SPRINTS)
        conn.executemany("INSERT INTO alocacoes VALUES (?,?,?,?)", ALOCACOES)
        conn.executemany("INSERT INTO historias VALUES (?,?,?,?,?,?,?,?,?,?,?)", HISTORIAS)
        conn.executemany("INSERT INTO bugs VALUES (?,?,?,?,?,?)", BUGS)
    return caminho


if __name__ == "__main__":
    print(f"Banco criado em {criar()}")
