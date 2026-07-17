-- ============================================================================
-- FASE 0 - CRIAÇÃO DO BANCO DE DADOS E TABELAS (0_criar_banco.sql)
-- Arquitetura Medallion: Camadas Raw (Bruta) e Silver (Tratada)
-- ============================================================================
 CREATE DATABASE transparencia;

-- ----------------------------------------------------------------------------
-- 1. LIMPEZA DOS OBJETOS EXISTENTES (Garantia de Idempotência)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS silver_trecho CASCADE;
DROP TABLE IF EXISTS silver_pagamento CASCADE;
DROP TABLE IF EXISTS silver_passagem CASCADE;
DROP TABLE IF EXISTS silver_viagem CASCADE;

DROP TABLE IF EXISTS raw_trecho CASCADE;
DROP TABLE IF EXISTS raw_pagamento CASCADE;
DROP TABLE IF EXISTS raw_passagem CASCADE;
DROP TABLE IF EXISTS raw_viagem CASCADE;

-- ============================================================================
-- CAMADA RAW (Mapeamento 1:1 fiel aos arquivos CSV originais)
-- Todas as colunas são VARCHAR e sem restrições/constraints de integridade.
-- ============================================================================

-- 1.1. Tabela Bruta: Viagem (Origem: 2025_Viagem.csv)
CREATE TABLE raw_viagem (
    id_viagem                  VARCHAR(500), -- Identificador do processo de viagem
    num_proposta               VARCHAR(500), -- Número da Proposta (PCDP)
    situacao                   VARCHAR(500), -- Situação
    viagem_urgente             VARCHAR(500), -- Viagem Urgente
    justificativa_urgencia     VARCHAR(4000),-- Justificativa Urgência Viagem
    cod_orgao_superior         VARCHAR(500), -- Código do órgão superior
    nome_orgao_superior        VARCHAR(1000),-- Nome do órgão superior
    cod_orgao_solicitante      VARCHAR(500), -- Código órgão solicitante
    nome_orgao_solicitante     VARCHAR(1000),-- Nome órgão solicitante
    cpf_viajante               VARCHAR(500), -- CPF viajante
    nome_viajante              VARCHAR(1000),-- Nome
    cargo                      VARCHAR(1000),-- Cargo
    funcao                     VARCHAR(1000),-- Função
    descricao_funcao           VARCHAR(2000),-- Descrição Função
    data_inicio                VARCHAR(500), -- Período - Data de início
    data_fim                   VARCHAR(500), -- Período - Data de fim
    destinos                   VARCHAR(4000),-- Destinos
    motivo                     VARCHAR(4000),-- Motivo
    valor_diarias              VARCHAR(500), -- Valor diárias
    valor_passagens            VARCHAR(500), -- Valor passagens
    valor_devolucao            VARCHAR(500), -- Valor devolução
    valor_outros_gastos        VARCHAR(500)  -- Valor outros gastos
);

-- 1.2. Tabela Bruta: Pagamento (Origem: 2025_Pagamento.csv)
CREATE TABLE raw_pagamento (
    id_viagem                  VARCHAR(500), -- Identificador do processo de viagem
    num_proposta               VARCHAR(500), -- Número da Proposta (PCDP)
    cod_orgao_superior         VARCHAR(500), -- Código do órgão superior
    nome_orgao_superior        VARCHAR(1000),-- Nome do órgão superior
    cod_orgao_pagador          VARCHAR(500), -- Codigo do órgão pagador
    nome_orgao_pagador         VARCHAR(1000),-- Nome do órgao pagador
    cod_ug_pagadora            VARCHAR(500), -- Código da unidade gestora pagadora
    nome_ug_pagadora           VARCHAR(1000),-- Nome da unidade gestora pagadora
    tipo_pagamento             VARCHAR(500), -- Tipo de pagamento
    valor                      VARCHAR(500)  -- Valor
);

-- 1.3. Tabela Bruta: Passagem (Origem: 2025_Passagem.csv)
CREATE TABLE raw_passagem (
    id_viagem                  VARCHAR(500), -- Identificador do processo de viagem
    num_proposta               VARCHAR(500), -- Número da Proposta (PCDP)
    meio_transporte            VARCHAR(500), -- Meio de transporte
    pais_origem_ida            VARCHAR(500), -- País - Origem ida
    uf_origem_ida              VARCHAR(500), -- UF - Origem ida
    cidade_origem_ida          VARCHAR(500), -- Cidade - Origem ida
    pais_destino_ida           VARCHAR(500), -- País - Destino ida
    uf_destino_ida             VARCHAR(500), -- UF - Destino ida
    cidade_destino_ida         VARCHAR(500), -- Cidade - Destino ida
    pais_origem_volta          VARCHAR(500), -- País - Origem volta
    uf_origem_volta            VARCHAR(500), -- UF - Origem volta
    cidade_origem_volta        VARCHAR(500), -- Cidade - Origem volta
    pais_destino_volta         VARCHAR(500), -- Pais - Destino volta
    uf_destino_volta           VARCHAR(500), -- UF - Destino volta
    cidade_destino_volta       VARCHAR(500), -- Cidade - Destino volta
    valor_passagem             VARCHAR(500), -- Valor da passagem
    taxa_servico               VARCHAR(500), -- Taxa de serviço
    data_emissao               VARCHAR(500), -- Data da emissão/compra
    hora_emissao               VARCHAR(500)  -- Hora da emissão/compra
);

-- 1.4. Tabela Bruta: Trecho (Origem: 2025_Trecho.csv)
CREATE TABLE raw_trecho (
    id_viagem                  VARCHAR(500), -- Identificador do processo de viagem
    num_proposta               VARCHAR(500), -- Número da Proposta (PCDP)
    sequencia_trecho           VARCHAR(500), -- Sequência Trecho
    origem_data                VARCHAR(500), -- Origem - Data
    origem_pais                VARCHAR(500), -- Origem - País
    origem_uf                  VARCHAR(500), -- Origem - UF
    origem_cidade              VARCHAR(500), -- Origem - Cidade
    destino_data               VARCHAR(500), -- Destino - Data
    destino_pais               VARCHAR(500), -- Destino - País
    destino_uf                 VARCHAR(500), -- Destino - UF
    destino_cidade             VARCHAR(500), -- Destino - Cidade
    meio_transporte            VARCHAR(500), -- Meio de transporte
    numero_diarias             VARCHAR(500), -- Número Diárias
    missao                     VARCHAR(500)  -- Missao?
);


-- ============================================================================
-- CAMADA SILVER (Dados limpos, tipados e estruturados com integridade)
-- Modelagem relacional contendo Chaves Primárias (PK), Estrangeiras (FK)
-- e restrições específicas para garantir consistência e qualidade analítica.
-- ============================================================================

-- 2.1. Tabela Silver: Viagem (Dimensão / Entidade Base)
CREATE TABLE silver_viagem (
    id_viagem                  VARCHAR(20) PRIMARY KEY,
    num_proposta               VARCHAR(20),
    situacao                   VARCHAR(50),
    viagem_urgente             VARCHAR(5),
    cod_orgao_superior         VARCHAR(20),
    nome_orgao_superior        VARCHAR(255) NOT NULL, -- CONSTRAINT 1: NOT NULL exigido no escopo
    nome_viajante              VARCHAR(255),
    cargo                      VARCHAR(255),
    data_inicio                DATE,
    data_fim                   DATE,
    destinos                   VARCHAR(4000),
    motivo                     VARCHAR(4000),
    valor_diarias              DECIMAL(10,2) CHECK (valor_diarias >= 0), -- CONSTRAINT 2: CHECK >= 0 exigido no escopo
    valor_passagens            DECIMAL(10,2),
    valor_devolucao            DECIMAL(10,2),
    valor_outros_gastos        DECIMAL(10,2),
    valor_total                DECIMAL(12,2), -- Calculado na Fase 2
    duracao_dias               INT            -- Calculado na Fase 2
);

-- 2.2. Tabela Silver: Passagem (Fato / Detalhe)
CREATE TABLE silver_passagem (
    id_passagem                SERIAL PRIMARY KEY,
    id_viagem                  VARCHAR(20) NOT NULL,
    meio_transporte            VARCHAR(50),
    pais_origem_ida            VARCHAR(60),
    uf_origem_ida              VARCHAR(40),
    cidade_origem_ida          VARCHAR(80),
    pais_destino_ida           VARCHAR(60),
    uf_destino_ida             VARCHAR(40),
    cidade_destino_ida         VARCHAR(80),
    valor_passagem             DECIMAL(10,2),
    taxa_servico               DECIMAL(10,2),
    data_emissao               DATE,
    
    -- Chave Estrangeira mantendo a integridade referencial com a tabela de Viagens
    CONSTRAINT fk_passagem_viagem FOREIGN KEY (id_viagem) REFERENCES silver_viagem(id_viagem) ON DELETE CASCADE,
    
    -- CONSTRAINTS exigidas pelo escopo do projeto:
    CONSTRAINT chk_valor_passagem CHECK (valor_passagem >= 0), -- CONSTRAINT 1
    CONSTRAINT chk_taxa_servico CHECK (taxa_servico >= 0)      -- CONSTRAINT 2
);

-- 2.3. Tabela Silver: Pagamento (Fato / Detalhe)
CREATE TABLE silver_pagamento (
    id_pagamento               SERIAL PRIMARY KEY,
    id_viagem                  VARCHAR(20) NOT NULL,
    num_proposta               VARCHAR(20),
    nome_orgao_pagador         VARCHAR(255),
    nome_ug_pagadora           VARCHAR(255),
    tipo_pagamento             VARCHAR(50) NOT NULL, -- CONSTRAINT 2: NOT NULL exigido no escopo
    valor                      DECIMAL(10,2),
    
    -- Chave Estrangeira mantendo a integridade referencial com a tabela de Viagens
    CONSTRAINT fk_pagamento_viagem FOREIGN KEY (id_viagem) REFERENCES silver_viagem(id_viagem) ON DELETE CASCADE,
    
    -- CONSTRAINTS exigidas pelo escopo do projeto:
    CONSTRAINT chk_valor_pagamento CHECK (valor >= 0)     -- CONSTRAINT 1: CHECK >= 0 exigido no escopo
);

-- 2.4. Tabela Silver: Trecho (Fato / Detalhe)
CREATE TABLE silver_trecho (
    id_trecho                  SERIAL PRIMARY KEY,
    id_viagem                  VARCHAR(20) NOT NULL,
    sequencia_trecho           INT,
    origem_data                DATE,
    origem_uf                  VARCHAR(40),
    origem_cidade              VARCHAR(80),
    destino_data               DATE,
    destino_uf                 VARCHAR(40),
    destino_cidade             VARCHAR(80),
    meio_transporte            VARCHAR(50),
    numero_diarias             DECIMAL(10,2),
    
    -- Chave Estrangeira mantendo a integridade referencial com a tabela de Viagens
    CONSTRAINT fk_trecho_viagem FOREIGN KEY (id_viagem) REFERENCES silver_viagem(id_viagem) ON DELETE CASCADE,
    
    -- CONSTRAINTS exigidas pelo escopo do projeto:
    CONSTRAINT chk_numero_diarias CHECK (numero_diarias >= 0),            -- CONSTRAINT 1
    CONSTRAINT unq_viagem_sequencia UNIQUE (id_viagem, sequencia_trecho)  -- CONSTRAINT 2
);