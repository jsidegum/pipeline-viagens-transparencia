"""
1_extrair.py - FASE 1: Extração e Camada RAW
"""
import zipfile
import gdown
import pandas as pd
import config
import banco


# -----------------------------------------------------------------------------
# Passo 1 - Baixar o arquivo .zip do Google Drive
# -----------------------------------------------------------------------------
def baixar_zip():
    """Baixa o arquivo ZIP do Google Drive para a pasta data/."""
    config.PASTA_DADOS.mkdir(exist_ok=True)
    caminho_zip = config.PASTA_DADOS / f"{config.ANO}.zip"

    if caminho_zip.exists():
        print(f"Arquivo já existe: {caminho_zip}")
        return caminho_zip

    url = (
        f"https://drive.google.com/uc?id="
        f"{config.DRIVE_FILE_ID}"
    )

    print("Baixando arquivo do Google Drive...")

    gdown.download(
        url,
        str(caminho_zip),
        quiet=False
    )

    print("Download concluído.")
    return caminho_zip

# -----------------------------------------------------------------------------
# Passo 2 - Limpar tabela RAW
# -----------------------------------------------------------------------------
def limpar_tabela(conexao, tabela):
    banco.executar(
    conexao,
    f"TRUNCATE TABLE {tabela}"
    )

# -----------------------------------------------------------------------------
# Passo 3 - Carregar CSV do ZIP para RAW
# -----------------------------------------------------------------------------
def carregar_csv_para_raw(conexao, zip_file, nome_csv, tabela):
    """
    Lê um CSV diretamente do ZIP em blocos e grava na tabela RAW.
    """
    print(f"\nProcessando {nome_csv} -> {tabela}")

    limpar_tabela(conexao, tabela)

    with zip_file.open(nome_csv) as arquivo_csv:

        leitor = pd.read_csv(
            arquivo_csv,
            sep=config.CSV_SEPARADOR,
            encoding=config.CSV_ENCODING,
            dtype=str,
            keep_default_na=False,
            chunksize=config.TAMANHO_BLOCO
        )

        total = 0

        for chunk in leitor:

            colunas = list(chunk.columns)

            placeholders = ", ".join(
                ["%s"] * len(colunas)
            )

            sql = f"""INSERT INTO {tabela} VALUES ({placeholders})"""

            linhas = [
                tuple(linha)
                for linha in chunk.values.tolist()
            ]

            banco.inserir_em_lote(
                conexao,
                sql,
                linhas
            )

            total += len(linhas)

            print(
                f"{tabela}: {total:,} registros carregados"
            )

        print(f"Finalizado: {tabela}")

# -----------------------------------------------------------------------------
# Processo principal
# -----------------------------------------------------------------------------
def main():

    conexao = None

    try:

        caminho_zip = baixar_zip()

        conexao = banco.conectar()

        with zipfile.ZipFile(caminho_zip, "r") as zip_file:

            for info in config.ARQUIVOS.values():

                carregar_csv_para_raw(
                    conexao,
                    zip_file,
                    info["csv"],
                    info["tabela_raw"]
                )

        print("\nCarga RAW concluída com sucesso.")

    except Exception as erro:

        print(f"\nERRO: {erro}")

    finally:

        if conexao:
            conexao.close()

if __name__ == "__main__":
    main()