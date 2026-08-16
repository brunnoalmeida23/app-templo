import psycopg2

# Banco antigo (Render)
FONTE = "postgresql://tupbao:db0flqQoptkEvcatCjouKd1UUhJUyaja@dpg-d9ail56cjfls739gdtl0-a.oregon-postgres.render.com/tupbao"

# Banco novo (Supabase)
DESTINO = "postgresql://postgres:%40147448R%23o%40@db.cvaurclhtxkuirvwgkam.supabase.co:5432/postgres"

def migrar():
    conn_fonte = psycopg2.connect(FONTE)
    conn_destino = psycopg2.connect(DESTINO)
    
    cur_fonte = conn_fonte.cursor()
    cur_destino = conn_destino.cursor()
    
    tabelas = ['usuario', 'publicacao', 'aviso_lido', 'checkin_limpeza', 'mensalidade']
    
    for tabela in tabelas:
        try:
            cur_fonte.execute(f"SELECT * FROM {tabela}")
            colunas = [desc[0] for desc in cur_fonte.description]
            dados = cur_fonte.fetchall()
            
            for linha in dados:
                valores = []
                for v in linha:
                    if isinstance(v, str):
                        valores.append(f"'{v.replace(chr(39), chr(39)+chr(39))}'")
                    elif v is None:
                        valores.append('NULL')
                    else:
                        valores.append(str(v))
                
                sql = f"INSERT INTO {tabela} ({','.join(colunas)}) VALUES ({','.join(valores)}) ON CONFLICT DO NOTHING"
                try:
                    cur_destino.execute(sql)
                except:
                    pass
            
            conn_destino.commit()
            print(f"✅ {tabela}: {len(dados)} registros migrados")
        except Exception as e:
            print(f"❌ {tabela}: {e}")
    
    conn_fonte.close()
    conn_destino.close()
    print("✅ Migração concluída!")

migrar()