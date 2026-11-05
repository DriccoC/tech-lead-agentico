# MAN-04 — Política de Segurança da Cadeia de Suprimentos de Software

Código: MAN-04 · Versão 1.6 · Vigência: 01/07/2026 · Responsável: Time de Segurança da Informação da NovaForja Software (empresa fictícia)

## 1. Escopo
Aplica-se a todos os componentes de terceiros (bibliotecas, pacotes, imagens de contêiner) incorporados aos produtos da empresa.

## 2. Critérios de admissão de componentes
1. É vedada a adoção de componente com vulnerabilidade conhecida de pontuação CVSS igual ou superior a 7,0 (severidade alta ou crítica) na versão pretendida, salvo exceção formal aprovada pelo time de segurança com prazo de correção.
2. Vulnerabilidades de severidade média (CVSS de 4,0 a 6,9) devem ser registradas no backlog com prazo de correção de até 30 dias.
3. A versão adotada deve ser a mais recente estável disponível no repositório oficial do ecossistema, ou estar no máximo uma versão secundária (MINOR) atrás dela.
4. Componentes sem manutenção há mais de 18 meses exigem avaliação de risco.

## 3. Classificação de severidade (CVSS v3)
- Nenhuma: 0,0
- Baixa: 0,1 a 3,9
- Média: 4,0 a 6,9
- Alta: 7,0 a 8,9
- Crítica: 9,0 a 10,0

## 4. Monitoramento contínuo
As dependências devem ser verificadas contra bases públicas de vulnerabilidades (como OSV e GitHub Advisory) a cada execução do pipeline. Versões devem ser fixadas (pinning) nos arquivos de dependências, e a atualização preventiva ocorre mensalmente.
