import os
import psycopg2


FONTE = os.environ.get("DATABASE_URL_FONTE")
DESTINO = os.environ.get("DATABASE_URL_DESTINO")


def migrar():
    if not FONTE or not DESTINO:
        raise RuntimeError(
            "Configure DATABASE_URL_FONTE e DATABASE_URL_DESTINO antes de executar."
        )

    conn_fonte = psycopg2.connect(FONTE)
    conn_destino = psycopg2.connect(DESTINO)

    cur_fonte = conn_fonte.cursor()
    cur_destino = conn_destino.cursor()

    tabelas = [
        "usuario",
        "publicacao",
        "aviso_lido",
        "checkin_limpeza",
        "mensalidade"
    ]

    try:
        for tabela in tabelas:
            cur_fonte.execute(f"SELECT * FROM {tabela}")

            colunas = [desc[0] for desc in cur_fonte.description]
            dados = cur_fonte.fetchall()

            placeholders = ",".join(["%s"] * len(colunas))

            sql = (
                f"INSERT INTO {tabela} "
                f"({','.join(colunas)}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT DO NOTHING"
            )

            for linha in dados:
                cur_destino.execute(sql, linha)

            conn_destino.commit()

            print(
                f"OK: {tabela}: "
                f"{len(dados)} registros processados"
            )

    except Exception:
        conn_destino.rollback()
        raise

    finally:
        cur_fonte.close()
        cur_destino.close()
        conn_fonte.close()
        conn_destino.close()

    print("Migração concluída.")


if __name__ == "__main__":
    migrar()