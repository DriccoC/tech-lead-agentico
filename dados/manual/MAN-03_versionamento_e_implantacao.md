# MAN-03 — Política de Versionamento e Implantação

Código: MAN-03 · Versão 4.0 · Vigência: 01/09/2026 · Responsável: Engenharia de Plataforma da NovaForja Software (empresa fictícia)

## 1. Modelo de ramificação
Adota-se o desenvolvimento baseado em tronco (trunk-based development). O ramo principal é protegido: nenhuma alteração pode ser incorporada a ele por envio direto. Toda integração ao tronco ocorre exclusivamente por meio de solicitação de incorporação (pull request) com aprovação conforme a Definição de Pronto (MAN-01) e com todas as verificações automatizadas do pipeline concluídas com sucesso.

## 2. Ramificações de curta duração
Ramificações de trabalho devem ter duração máxima de dois dias úteis. Funcionalidades incompletas devem permanecer ocultas por sinalizadores de funcionalidade (feature flags) até a liberação.

## 3. Janela de congelamento de mudanças
Fica instituída a janela de congelamento de mudanças: não são autorizadas implantações no ambiente de produção às sextas-feiras após as 14h, nos fins de semana e nas vésperas de feriados nacionais. Durante a janela de congelamento, somente correções emergenciais de severidade crítica podem ser implantadas, mediante aprovação do gerente de plantão e registro de mudança emergencial.

## 4. Procedimento de implantação
1. Implantação automática no ambiente de homologação a cada incorporação no tronco.
2. Promoção para produção por estratégia canário (5% do tráfego por 30 minutos), com reversão automática se a taxa de erros superar 1%.
3. Toda implantação em produção gera nota de versão vinculada às histórias entregues.

## 5. Versionamento semântico
Bibliotecas e APIs públicas seguem o versionamento semântico (MAJOR.MINOR.PATCH). Mudanças incompatíveis exigem incremento da versão principal e período de convivência mínimo de 90 dias para a versão anterior.
