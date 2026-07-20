# Pipeline de Dados — Viagens a Serviço (Portal da Transparência)

## 1. Problema

Os dados de Viagens a Serviço do Governo Federal são publicados de forma bruta e desorganizada no Portal da Transparência. Este projeto constrói um pipeline de dados de ponta a ponta que extrai, limpa e organiza essas informações, transformando-as em métricas e gráficos confiáveis para apoiar a tomada de decisão sobre os gastos públicos com viagens.

## 2. Tecnologias utilizadas

- **Python** (pandas, gdown, psycopg2, SQLAlchemy)
- **PostgreSQL**
- **Jupyter Notebook** (matplotlib, seaborn)
- Arquitetura **Medallion** (camadas Raw, Silver e Gold)

### Arquitetura do pipeline

```
Google Drive (.zip)
        │
        ▼
1_extrair.py  ──────────► RAW (raw_viagem, raw_pagamento, raw_passagem, raw_trecho)
                           cópia fiel dos CSVs, sem tratamento
        │
        ▼
2_transformar.py ───────► SILVER (silver_viagem, silver_pagamento, silver_passagem, silver_trecho)
                           dados tipados, limpos e com integridade referencial
        │
        ▼
3_analise.ipynb ────────► GOLD (gold_resumo_orgao + view)
                           perguntas de negócio, gráficos e tabela agregada
```

## 3. Estrutura do repositório

| Arquivo | Descrição |
|---|---|
| `0_criar_banco.sql` | Cria o database e as 8 tabelas (Raw e Silver), com PK, FK e constraints |
| `1_extrair.py` | Baixa o .zip do Google Drive e carrega os CSVs na camada Raw |
| `2_transformar.py` | Limpa e tipa os dados, gravando na camada Silver |
| `3_analise.ipynb` | Responde as perguntas de negócio, gera gráficos e cria a camada Gold |
| `banco.py` | Funções utilitárias de conexão e execução no PostgreSQL |
| `config.py` | Parâmetros do projeto e leitura das credenciais do `.env` |
| `.env.example` | Modelo de variáveis de ambiente (credenciais) |
| `requirements.txt` | Dependências Python do projeto |

## 4. Como executar

**Estrutura de arquivos esperada na raiz do projeto:**
```
.
├── .env
├── requirements.txt
├── 0_criar_banco.sql
├── 1_extrair.py
├── 2_transformar.py
├── 3_analise.ipynb
├── banco.py
└── config.py
```

1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Crie um arquivo `.env` na raiz do projeto com as credenciais do PostgreSQL:
   ```
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_USER=seu_usuario
   POSTGRES_PASSWORD=sua_senha
   POSTGRES_DATABASE=transparencia
   ```

3. Execute `0_criar_banco.sql` no pgAdmin em 2 etapas: primeiro só o trecho de criação do banco (conectado a outro banco, ex. `postgres`); depois, já conectado ao banco `transparencia`, o restante do script (criação das tabelas)

4. Execute o pipeline na ordem:
   ```bash
   python 1_extrair.py       # download + camada Raw
   python 2_transformar.py   # camada Silver
   ```

5. Abra `3_analise.ipynb` e execute todas as células (camada Gold + perguntas de negócio + gráficos).

## 5. Perguntas de negócio respondidas

1. Os 5 órgãos com maior custo total
2. Os 3 destinos com maior custo médio por viagem
3. A viagem de maior duração e seu custo total
4. O tipo de pagamento com maior valor médio
5. O meio de transporte mais usado nos trechos
6. A UF de destino que mais aparece nos trechos
7. O órgão que mais pagou no total

## 6. Melhorias futuras

- Automatizar a execução do pipeline (agendamento/orquestração, ex. Airflow)
- Adicionar testes automatizados para as camadas Raw e Silver
- Parametrizar o pipeline para múltiplos anos, não apenas 2025

## 7. Conclusões e insights

- **Concentração de gastos:** o Ministério da Justiça e Segurança Pública lidera com folga o custo total em viagens (R\$ 485 mi), quase 4x o valor do segundo colocado (Defesa, R\$ 155 mi). Do lado dos pagamentos, esse eixo se confirma: o Fundo Nacional de Segurança Pública é o maior pagador (R\$ 278 mi) — mesmo com nomenclaturas diferentes entre solicitante e pagador, os dados apontam para a mesma área como maior gasto público em viagens.
- **Duração não é sinônimo de custo alto:** a viagem mais longa do período (378 dias) teve custo total de R\$ 120.650 — valor moderado frente à duração. O boxplot mostra que a maioria das viagens dura poucos dias, com alguns outliers de longa duração, mas isso não significa necessariamente maior custo total.
- **Número de destinos pesa mais que o destino em si:** viagens com múltiplos destinos (ex.: Pequim + Xangai, R\$ 57.683 de média) custam muito mais que viagens de destino único e trecho exato (ex.: Brasília → Berlim, R\$ 12.088 de média), sugerindo que a quantidade de paradas é um fator de custo mais relevante que o destino escolhido.

Os detalhes completos das análises e gráficos estão em `3_analise.ipynb`.
