"""
2_transformar.py - FASE 2: Transformação e Camada SILVER (PostgreSQL)

Le as 4 tabelas RAW (texto puro, fiel ao CSV), limpa, tipa (DECIMAL, DATE, INT)
e grava nas 4 tabelas SILVER, respeitando a integridade referencial
(silver_viagem primeiro, depois as tabelas filhas) e calculando as colunas
derivadas valor_total e duracao_dias.

Processo idempotente (TRUNCATE antes de carregar) e resiliente (try/except),
seguindo o mesmo padrao de 1_extrair.py.

Leitura das tabelas RAW feita via engine SQLAlchemy (silencia o UserWarning do
pandas e é a forma oficialmente suportada por pd.read_sql). A escrita na
Silver continua usando banco.py/psycopg2, que já é o utilitário do projeto.
"""
import urllib.parse

import pandas as pd
from sqlalchemy import create_engine

import banco
import config

# Tamanho do bloco de insercao (mesma logica do 1_extrair.py)
TAMANHO_BLOCO = 50_000

# Textos que representam "sem informacao" nas bases do Portal da Transparencia
VALORES_NULOS = {"", "SEM INFORMAÇÃO", "SEM INFORMACAO", "NAN", "NA", "-", "NULL", "N/A"}


def criar_engine_leitura():
    cfg = config.POSTGRES_CONFIG
    senha_segura = urllib.parse.quote_plus(cfg["password"])
    url = (
        f"postgresql+psycopg2://{cfg['user']}:{senha_segura}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
    )
    return create_engine(url)


# =============================================================================
# Funcoes de conversao (texto bruto -> tipo Silver), usadas via Series.apply()
# =============================================================================
def limpar_valor(valor):
    """Converte texto no padrao BR ('1.272,97' ou '1272,97') para float.
    Retorna None quando o valor esta vazio ou e um marcador de "sem informacao".
    """
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto == "" or texto.upper() in VALORES_NULOS:
        return None
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def limpar_data(valor):
    """Converte 'DD/MM/AAAA' para date. Retorna None se vazio/invalido."""
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto == "" or texto.upper() in VALORES_NULOS:
        return None
    data = pd.to_datetime(texto, format="%d/%m/%Y", errors="coerce")
    return data.date() if pd.notna(data) else None


def limpar_texto(valor, tamanho_max=None):
    """Remove espacos nas pontas, normaliza vazio/"sem informacao" para None
    e corta a string no tamanho maximo da coluna Silver (evita erro de insert).
    """
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto == "" or texto.upper() in VALORES_NULOS:
        return None
    if tamanho_max:
        texto = texto[:tamanho_max]
    return texto


def valor_ou_zero(serie):
    """Para colunas financeiras onde a ausencia de informacao equivale a 0
    (valor_diarias, valor_passagens, valor_devolucao, valor_outros_gastos,
    valor_passagem, taxa_servico, numero_diarias, valor de pagamento).
    Recebe e devolve uma Series (uso vetorizado: serie.apply()).
    """
    return serie.apply(limpar_valor).fillna(0.0)


def dataframe_para_tuplas(df):
    """Converte um DataFrame já limpo para uma lista de tuplas prontas para o
    INSERT, trocando NaN/NaT (que o psycopg2 não entende) por None."""
    df_objeto = df.astype(object)
    df_objeto = df_objeto.where(pd.notnull(df_objeto), None)
    return [tuple(linha) for linha in df_objeto.to_numpy()]


# =============================================================================
# Utilitario de carga/limpeza das tabelas SILVER
# =============================================================================
def truncar_silver(conexao):
    """Limpa as 4 tabelas Silver de uma vez (garante idempotencia)."""
    banco.executar(
        conexao,
        """
        TRUNCATE TABLE silver_trecho, silver_pagamento, silver_passagem,
                       silver_viagem
        RESTART IDENTITY CASCADE
        """,
    )


def inserir_em_blocos(conexao, sql_insert, linhas, nome_tabela):
    """Insere 'linhas' em blocos de TAMANHO_BLOCO, imprimindo o progresso."""
    total = 0
    for inicio in range(0, len(linhas), TAMANHO_BLOCO):
        bloco = linhas[inicio: inicio + TAMANHO_BLOCO]
        banco.inserir_em_lote(conexao, sql_insert, bloco)
        total += len(bloco)
        print(f"{nome_tabela}: {total:,} registros carregados")
    return total


# =============================================================================
# Passo 1 - silver_viagem (precisa ser a primeira: as demais dependem dela via FK)
# =============================================================================
def transformar_viagem(conexao, engine):
    print("\nProcessando raw_viagem -> silver_viagem")

    raw = pd.read_sql("SELECT * FROM raw_viagem", engine)
    total_raw = len(raw)

    df = pd.DataFrame()
    df["id_viagem"] = raw["id_viagem"].apply(lambda v: limpar_texto(v, 20))
    df["num_proposta"] = raw["num_proposta"].apply(lambda v: limpar_texto(v, 20))
    df["situacao"] = raw["situacao"].apply(lambda v: limpar_texto(v, 50))
    df["viagem_urgente"] = raw["viagem_urgente"].apply(lambda v: limpar_texto(v, 5))
    df["cod_orgao_superior"] = raw["cod_orgao_superior"].apply(lambda v: limpar_texto(v, 20))
    df["nome_orgao_superior"] = raw["nome_orgao_superior"].apply(lambda v: limpar_texto(v, 255))
    df["nome_viajante"] = raw["nome_viajante"].apply(lambda v: limpar_texto(v, 255))
    df["cargo"] = raw["cargo"].apply(lambda v: limpar_texto(v, 255))
    df["data_inicio"] = raw["data_inicio"].apply(limpar_data)
    df["data_fim"] = raw["data_fim"].apply(limpar_data)
    df["destinos"] = raw["destinos"].apply(lambda v: limpar_texto(v, 4000))
    df["motivo"] = raw["motivo"].apply(lambda v: limpar_texto(v, 4000))
    df["valor_diarias"] = valor_ou_zero(raw["valor_diarias"])
    df["valor_passagens"] = valor_ou_zero(raw["valor_passagens"])
    df["valor_devolucao"] = valor_ou_zero(raw["valor_devolucao"])
    df["valor_outros_gastos"] = valor_ou_zero(raw["valor_outros_gastos"])

    # valor_total: diarias + passagens + outros_gastos - devolucao.
    df["valor_total"] = (
        df["valor_diarias"]
        + df["valor_passagens"]
        + df["valor_outros_gastos"]
        - df["valor_devolucao"]
    )

    # duracao_dias = diferenca em dias corridos entre data_fim e data_inicio.
    # Fica None (NULL) quando alguma das datas esta ausente ou quando a
    # diferenca e negativa (inconsistencia de dado), em vez de mascarar com 0.
    inicio = pd.to_datetime(df["data_inicio"])
    fim = pd.to_datetime(df["data_fim"])
    duracao = (fim - inicio).dt.days
    df["duracao_dias"] = duracao.where(duracao >= 0)
    df["duracao_dias"] = df["duracao_dias"].astype("Int64")  # inteiro anulavel

    total_sem_id = df["id_viagem"].isna().sum()
    total_sem_orgao = df["nome_orgao_superior"].isna().sum()

    # Descarta linhas sem id_viagem (PK) ou sem nome_orgao_superior (NOT NULL)
    df = df.dropna(subset=["id_viagem", "nome_orgao_superior"])

    total_antes_dedup = len(df)
    df = df.drop_duplicates(subset=["id_viagem"], keep="first")
    total_duplicadas = total_antes_dedup - len(df)

    colunas_ordem = [
        "id_viagem", "num_proposta", "situacao", "viagem_urgente",
        "cod_orgao_superior", "nome_orgao_superior", "nome_viajante", "cargo",
        "data_inicio", "data_fim", "destinos", "motivo", "valor_diarias",
        "valor_passagens", "valor_devolucao", "valor_outros_gastos",
        "valor_total", "duracao_dias",
    ]
    linhas = dataframe_para_tuplas(df[colunas_ordem])

    sql = """
        INSERT INTO silver_viagem (
            id_viagem, num_proposta, situacao, viagem_urgente,
            cod_orgao_superior, nome_orgao_superior, nome_viajante, cargo,
            data_inicio, data_fim, destinos, motivo, valor_diarias,
            valor_passagens, valor_devolucao, valor_outros_gastos,
            valor_total, duracao_dias
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    inserir_em_blocos(conexao, sql, linhas, "silver_viagem")

    print(
        f"raw_viagem: {total_raw:,} linhas lidas | "
        f"{len(linhas):,} carregadas | "
        f"{total_sem_id:,} sem id_viagem | "
        f"{total_sem_orgao:,} sem nome_orgao_superior | "
        f"{total_duplicadas:,} id_viagem duplicado"
    )

    return set(df["id_viagem"])


# =============================================================================
# Passo 2 - silver_pagamento
# =============================================================================
def transformar_pagamento(conexao, engine, ids_validos):
    print("\nProcessando raw_pagamento -> silver_pagamento")

    raw = pd.read_sql("SELECT * FROM raw_pagamento", engine)
    total_raw = len(raw)

    df = pd.DataFrame()
    df["id_viagem"] = raw["id_viagem"].apply(lambda v: limpar_texto(v, 20))
    df["num_proposta"] = raw["num_proposta"].apply(lambda v: limpar_texto(v, 20))
    df["nome_orgao_pagador"] = raw["nome_orgao_pagador"].apply(lambda v: limpar_texto(v, 255))
    df["nome_ug_pagadora"] = raw["nome_ug_pagadora"].apply(lambda v: limpar_texto(v, 255))
    df["tipo_pagamento"] = raw["tipo_pagamento"].apply(lambda v: limpar_texto(v, 50))
    df["valor"] = valor_ou_zero(raw["valor"])

    # FK: so mantem pagamentos cuja viagem existe na silver_viagem
    filtro_fk = df["id_viagem"].isin(ids_validos)
    descartadas_fk = (~filtro_fk).sum()
    df = df[filtro_fk]

    # NOT NULL na Silver
    descartadas_tipo = df["tipo_pagamento"].isna().sum()
    df = df.dropna(subset=["tipo_pagamento"])

    colunas_ordem = [
        "id_viagem", "num_proposta", "nome_orgao_pagador", "nome_ug_pagadora",
        "tipo_pagamento", "valor",
    ]
    linhas = dataframe_para_tuplas(df[colunas_ordem])

    sql = """
        INSERT INTO silver_pagamento (
            id_viagem, num_proposta, nome_orgao_pagador, nome_ug_pagadora,
            tipo_pagamento, valor
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """
    inserir_em_blocos(conexao, sql, linhas, "silver_pagamento")

    print(
        f"raw_pagamento: {total_raw:,} linhas lidas | "
        f"{len(linhas):,} carregadas | "
        f"{descartadas_fk:,} sem viagem correspondente | "
        f"{descartadas_tipo:,} sem tipo_pagamento"
    )


# =============================================================================
# Passo 3 - silver_passagem
# =============================================================================
def transformar_passagem(conexao, engine, ids_validos):
    print("\nProcessando raw_passagem -> silver_passagem")

    raw = pd.read_sql("SELECT * FROM raw_passagem", engine)
    total_raw = len(raw)

    df = pd.DataFrame()
    df["id_viagem"] = raw["id_viagem"].apply(lambda v: limpar_texto(v, 20))
    df["meio_transporte"] = raw["meio_transporte"].apply(lambda v: limpar_texto(v, 50))
    df["pais_origem_ida"] = raw["pais_origem_ida"].apply(lambda v: limpar_texto(v, 60))
    df["uf_origem_ida"] = raw["uf_origem_ida"].apply(lambda v: limpar_texto(v, 40))
    df["cidade_origem_ida"] = raw["cidade_origem_ida"].apply(lambda v: limpar_texto(v, 80))
    df["pais_destino_ida"] = raw["pais_destino_ida"].apply(lambda v: limpar_texto(v, 60))
    df["uf_destino_ida"] = raw["uf_destino_ida"].apply(lambda v: limpar_texto(v, 40))
    df["cidade_destino_ida"] = raw["cidade_destino_ida"].apply(lambda v: limpar_texto(v, 80))
    df["valor_passagem"] = valor_ou_zero(raw["valor_passagem"])
    df["taxa_servico"] = valor_ou_zero(raw["taxa_servico"])
    df["data_emissao"] = raw["data_emissao"].apply(limpar_data)

    # FK: so mantem passagens cuja viagem existe na silver_viagem
    filtro_fk = df["id_viagem"].isin(ids_validos)
    descartadas_fk = (~filtro_fk).sum()
    df = df[filtro_fk]

    colunas_ordem = [
        "id_viagem", "meio_transporte", "pais_origem_ida", "uf_origem_ida",
        "cidade_origem_ida", "pais_destino_ida", "uf_destino_ida",
        "cidade_destino_ida", "valor_passagem", "taxa_servico", "data_emissao",
    ]
    linhas = dataframe_para_tuplas(df[colunas_ordem])

    sql = """
        INSERT INTO silver_passagem (
            id_viagem, meio_transporte, pais_origem_ida, uf_origem_ida,
            cidade_origem_ida, pais_destino_ida, uf_destino_ida,
            cidade_destino_ida, valor_passagem, taxa_servico, data_emissao
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    inserir_em_blocos(conexao, sql, linhas, "silver_passagem")

    print(
        f"raw_passagem: {total_raw:,} linhas lidas | "
        f"{len(linhas):,} carregadas | "
        f"{descartadas_fk:,} sem viagem correspondente"
    )


# =============================================================================
# Passo 4 - silver_trecho
# =============================================================================
def transformar_trecho(conexao, engine, ids_validos):
    print("\nProcessando raw_trecho -> silver_trecho")

    raw = pd.read_sql("SELECT * FROM raw_trecho", engine)
    total_raw = len(raw)

    df = pd.DataFrame()
    df["id_viagem"] = raw["id_viagem"].apply(lambda v: limpar_texto(v, 20))
    # sequencia_trecho: passa pelo conversor decimal (aceita '3' ou '3,0') e
    # vira inteiro anulavel (Int64), pois pode faltar em algum registro.
    df["sequencia_trecho"] = raw["sequencia_trecho"].apply(limpar_valor).astype("Int64")
    df["origem_data"] = raw["origem_data"].apply(limpar_data)
    df["origem_uf"] = raw["origem_uf"].apply(lambda v: limpar_texto(v, 40))
    df["origem_cidade"] = raw["origem_cidade"].apply(lambda v: limpar_texto(v, 80))
    df["destino_data"] = raw["destino_data"].apply(limpar_data)
    df["destino_uf"] = raw["destino_uf"].apply(lambda v: limpar_texto(v, 40))
    df["destino_cidade"] = raw["destino_cidade"].apply(lambda v: limpar_texto(v, 80))
    df["meio_transporte"] = raw["meio_transporte"].apply(lambda v: limpar_texto(v, 50))
    df["numero_diarias"] = valor_ou_zero(raw["numero_diarias"])

    # FK: so mantem trechos cuja viagem existe na silver_viagem
    filtro_fk = df["id_viagem"].isin(ids_validos)
    descartadas_fk = (~filtro_fk).sum()
    df = df[filtro_fk]

    # UNIQUE (id_viagem, sequencia_trecho) na Silver
    total_antes_dedup = len(df)
    df = df.drop_duplicates(subset=["id_viagem", "sequencia_trecho"], keep="first")
    descartadas_duplicadas = total_antes_dedup - len(df)

    colunas_ordem = [
        "id_viagem", "sequencia_trecho", "origem_data", "origem_uf",
        "origem_cidade", "destino_data", "destino_uf", "destino_cidade",
        "meio_transporte", "numero_diarias",
    ]
    linhas = dataframe_para_tuplas(df[colunas_ordem])

    sql = """
        INSERT INTO silver_trecho (
            id_viagem, sequencia_trecho, origem_data, origem_uf, origem_cidade,
            destino_data, destino_uf, destino_cidade, meio_transporte,
            numero_diarias
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    inserir_em_blocos(conexao, sql, linhas, "silver_trecho")

    print(
        f"raw_trecho: {total_raw:,} linhas lidas | "
        f"{len(linhas):,} carregadas | "
        f"{descartadas_fk:,} sem viagem correspondente | "
        f"{descartadas_duplicadas:,} sequencia_trecho duplicada"
    )


# =============================================================================
# Processo principal
# =============================================================================
def main():
    conexao = None
    engine = None
    try:
        conexao = banco.conectar()
        engine = criar_engine_leitura()

        truncar_silver(conexao)

        ids_validos = transformar_viagem(conexao, engine)
        transformar_pagamento(conexao, engine, ids_validos)
        transformar_passagem(conexao, engine, ids_validos)
        transformar_trecho(conexao, engine, ids_validos)

        print("\nCarga SILVER concluída com sucesso.")

    except Exception as erro:
        print(f"\nERRO: {erro}")

    finally:
        if engine:
            engine.dispose()
        if conexao:
            conexao.close()


if __name__ == "__main__":
    main()