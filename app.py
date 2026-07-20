import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///templo.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============ MODELOS ============

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    funcao = db.Column(db.String(50), default='membro')
    ultimo_acesso = db.Column(db.DateTime, nullable=True)
    ativo = db.Column(db.Boolean, default=True)

class AvisoLido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    publicacao_id = db.Column(db.Integer, db.ForeignKey('publicacao.id'), nullable=False)
    data_leitura = db.Column(db.DateTime, default=datetime.utcnow)

class CheckinLimpeza(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    usuario_nome = db.Column(db.String(100), nullable=False)
    grupo = db.Column(db.String(50), nullable=False)
    periodo = db.Column(db.String(50), nullable=True)
    data_checkin = db.Column(db.DateTime, default=datetime.utcnow)

class Mensalidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    mes_ano = db.Column(db.String(7), nullable=False)
    status = db.Column(db.String(20), default='pendente')
    observacao = db.Column(db.String(200), nullable=True)
    data_pagamento = db.Column(db.DateTime, nullable=True)

class Publicacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(50))
    data_evento = db.Column(db.DateTime, nullable=True)
    data_publicacao = db.Column(db.DateTime, default=datetime.utcnow)

# ============ FUNÇÕES AUXILIARES ============

def pode_gerenciar(tipo=None):
    if 'user_id' not in session:
        return False
    funcao = session.get('funcao', 'membro')
    if funcao in ['super_admin', 'admin']:
        return True
    if funcao == 'tesouraria' and tipo == 'financeiro':
        return True
    if funcao == 'limpezas' and tipo == 'limpeza':
        return True
    return False

def pode_gerenciar_usuarios():
    return session.get('funcao') == 'super_admin'

def pode_gerenciar_tesouraria():
    return session.get('user_nome') in ['Flavia', 'Lilian', 'Roberto', 'Dirigente']

def enviar_notificacao(titulo, mensagem):
    try:
        onesignal_app_id = os.environ.get('ONESIGNAL_APP_ID', '')
        onesignal_api_key = os.environ.get('ONESIGNAL_API_KEY', '')
        if not onesignal_app_id or not onesignal_api_key:
            return
        url = "https://onesignal.com/api/v1/notifications"
        headers = {
            "Authorization": f"Bearer {onesignal_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "app_id": onesignal_app_id,
            "headings": {"en": titulo},
            "contents": {"en": mensagem},
            "included_segments": ["Active Subscriptions"]
        }
        requests.post(url, json=data, headers=headers)
    except:
        pass

# ============ ROTAS PÚBLICAS ============

@app.route('/')
def index():
    giras = Publicacao.query.filter_by(tipo='gira').order_by(Publicacao.data_evento.asc()).limit(5).all()
    projetos = Publicacao.query.filter_by(tipo='projeto').order_by(Publicacao.data_publicacao.desc()).limit(3).all()
    return render_template('index.html', giras=giras, projetos=projetos)

@app.route('/agenda')
def agenda():
    giras = Publicacao.query.filter_by(tipo='gira').order_by(Publicacao.data_evento.asc()).all()
    return render_template('agenda.html', giras=giras)

@app.route('/projetos')
def projetos():
    projetos = Publicacao.query.filter_by(tipo='projeto').order_by(Publicacao.data_publicacao.desc()).all()
    return render_template('projetos.html', projetos=projetos)

@app.route('/guia')
def guia():
    return render_template('guia.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        user = Usuario.query.filter_by(email=email).first()
        if user and check_password_hash(user.senha, senha):
            if not user.ativo:
                flash('Usuário bloqueado.')
                return render_template('login.html')
            session['user_id'] = user.id
            session['user_nome'] = user.nome
            session['is_admin'] = user.is_admin
            session['funcao'] = user.funcao
            session['ultimo_acesso_anterior'] = user.ultimo_acesso
            user.ultimo_acesso = datetime.utcnow()
            db.session.commit()
            flash('Login realizado com sucesso!')
            next_page = session.pop('next_page', None)
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        flash('E-mail ou senha inválidos.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ============ ÁREA DOS MEMBROS ============

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    lidos = [al.publicacao_id for al in AvisoLido.query.filter_by(usuario_id=session['user_id']).all()]
    avisos = Publicacao.query.filter_by(tipo='aviso').order_by(Publicacao.data_publicacao.desc()).all()
    novos_avisos = 0
    for aviso in avisos:
        if aviso.id not in lidos:
            novos_avisos += 1
    return render_template('area_membros/dashboard.html', avisos=avisos, novos_avisos=novos_avisos)

@app.route('/dashboard/avisos')
def ver_avisos():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    avisos = Publicacao.query.filter_by(tipo='aviso').order_by(Publicacao.data_publicacao.desc()).all()
    lidos = [al.publicacao_id for al in AvisoLido.query.filter_by(usuario_id=session['user_id']).all()]
    return render_template('area_membros/avisos.html', avisos=avisos, lidos=lidos)

@app.route('/dashboard/avisos/marcar-lido/<int:id>')
def marcar_lido(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not AvisoLido.query.filter_by(usuario_id=session['user_id'], publicacao_id=id).first():
        novo = AvisoLido(usuario_id=session['user_id'], publicacao_id=id)
        db.session.add(novo)
        db.session.commit()
    return redirect(url_for('ver_avisos'))

@app.route('/dashboard/limpezas')
def ver_limpezas():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    limpezas = Publicacao.query.filter_by(tipo='limpeza').order_by(Publicacao.data_publicacao.desc()).all()
    return render_template('area_membros/limpezas.html', limpezas=limpezas)

# ============ FINANCEIRO ============

@app.route('/dashboard/financeiro')
def financeiro_dash():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('area_membros/financeiro.html')

@app.route('/dashboard/financeiro/publicacoes')
def ver_financeiro_publicacoes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    financeiro = Publicacao.query.filter_by(tipo='financeiro').order_by(Publicacao.data_publicacao.desc()).all()
    return render_template('area_membros/financeiro_publicacoes.html', financeiro=financeiro)

@app.route('/dashboard/financeiro/contas')
def ver_contas():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    publicacoes = Publicacao.query.filter_by(tipo='conta').order_by(Publicacao.data_publicacao.desc()).all()
    return render_template('area_membros/financeiro_contas.html', publicacoes=publicacoes)

@app.route('/dashboard/financeiro/recebimentos')
def ver_recebimentos():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    publicacoes = Publicacao.query.filter_by(tipo='recebimento').order_by(Publicacao.data_publicacao.desc()).all()
    return render_template('area_membros/financeiro_recebimentos.html', publicacoes=publicacoes)

# ============ TESOURARIA - MENSALIDADES ============

@app.route('/dashboard/mensalidades', methods=['GET', 'POST'])
def mensalidades():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not pode_gerenciar_tesouraria():
        flash('Acesso restrito à tesouraria.')
        return redirect(url_for('dashboard'))
    
    mes_atual = datetime.utcnow().strftime('%m/%Y')
    isentos = ['Roberto', 'Thais', 'Rafael', 'Vera', 'Flavia', 'Marlon', 'Dirigente', 'Super-Admin']
    membros = Usuario.query.filter_by(ativo=True).filter(Usuario.nome.notin_(isentos)).order_by(Usuario.nome).all()
    
    if request.method == 'POST':
        for membro in membros:
            novo_status = request.form.get(f'status_{membro.id}', 'pendente')
            obs = request.form.get(f'obs_{membro.id}', '')
            mensalidade = Mensalidade.query.filter_by(usuario_id=membro.id, mes_ano=mes_atual).first()
            if novo_status == 'pendente':
                if mensalidade:
                    db.session.delete(mensalidade)
            else:
                if not mensalidade:
                    mensalidade = Mensalidade(usuario_id=membro.id, mes_ano=mes_atual)
                    db.session.add(mensalidade)
                mensalidade.status = novo_status
                mensalidade.observacao = obs if novo_status == 'acordo' else None
                if novo_status == 'pago':
                    mensalidade.data_pagamento = datetime.utcnow()
        db.session.commit()
        flash('✅ Mensalidades atualizadas!')
        return redirect(url_for('mensalidades'))
    
    status_list = {}
    obs_list = {}
    for m in membros:
        msg = Mensalidade.query.filter_by(usuario_id=m.id, mes_ano=mes_atual).first()
        status_list[m.id] = msg.status if msg else 'pendente'
        obs_list[m.id] = msg.observacao if msg else ''
    
    return render_template('area_membros/mensalidades.html', membros=membros, status_list=status_list, obs_list=obs_list, mes_atual=mes_atual)

@app.route('/admin/enviar-cobranca')
def enviar_cobranca():
    if not pode_gerenciar_tesouraria():
        flash('Acesso restrito à tesouraria.')
        return redirect(url_for('dashboard'))
    
    mes_atual = datetime.utcnow().strftime('%m/%Y')
    dia = datetime.utcnow().day
    if dia < 10:
        flash('Só pode enviar cobrança a partir do dia 10.')
        return redirect(url_for('mensalidades'))
    
    isentos = ['Roberto', 'Thais', 'Rafael', 'Vera', 'Flavia', 'Marlon', 'Dirigente', 'Super-Admin']
    membros = Usuario.query.filter_by(ativo=True).filter(Usuario.nome.notin_(isentos)).all()
    pendentes = []
    for m in membros:
        msg = Mensalidade.query.filter_by(usuario_id=m.id, mes_ano=mes_atual).first()
        if not msg or msg.status == 'pendente':
            pendentes.append(m.nome)
    
    if pendentes:
        enviar_notificacao("💰 Mensalidade em Aberto - TUPBAO", "Favor entrar em contato com a tesouraria.")
        flash(f'✅ Cobrança enviada! {len(pendentes)} membros pendentes.')
    else:
        flash('✅ Todos estão em dia ou com acordo!')
    return redirect(url_for('mensalidades'))

# ============ CHECK-IN LIMPEZA ============

@app.route('/checkin/limpeza', methods=['GET', 'POST'])
def checkin_limpeza():
    if 'user_id' not in session:
        session['next_page'] = '/checkin/limpeza'
        return redirect(url_for('login'))
    grupos = [
        {'nome': 'Grupo 1', 'periodo': '29/06 a 04/07'},
        {'nome': 'Grupo 2', 'periodo': '22/06 a 27/06'},
        {'nome': 'Grupo 3', 'periodo': '06/07 a 11/07'},
        {'nome': 'Grupo 4', 'periodo': '13/07 a 18/07'},
        {'nome': 'Grupo 5', 'periodo': '20/07 a 25/07'},
        {'nome': 'Grupo 6', 'periodo': '27/07 a 01/08'},
    ]
    if request.method == 'POST':
        grupo_nome = request.form['grupo']
        grupo_periodo = request.form['periodo']
        checkin = CheckinLimpeza(usuario_id=session['user_id'], usuario_nome=session['user_nome'], grupo=grupo_nome, periodo=grupo_periodo)
        db.session.add(checkin)
        db.session.commit()
        flash(f'✅ Limpeza do {grupo_nome} confirmada! Axé!')
        return redirect(url_for('dashboard'))
    return render_template('checkin_limpeza.html', grupos=grupos)

@app.route('/admin/limpezas/excluir/<int:id>')
def excluir_checkin(id):
    if 'user_id' not in session or not pode_gerenciar():
        flash('Acesso restrito.')
        return redirect(url_for('dashboard'))
    checkin = CheckinLimpeza.query.get_or_404(id)
    db.session.delete(checkin)
    db.session.commit()
    flash('🗑️ Check-in excluído.')
    return redirect(url_for('historico_limpezas'))

@app.route('/admin/limpezas/historico')
def historico_limpezas():
    if 'user_id' not in session or not pode_gerenciar():
        flash('Acesso restrito.')
        return redirect(url_for('dashboard'))
    checkins = CheckinLimpeza.query.order_by(CheckinLimpeza.data_checkin.desc()).all()
    meses = {}
    for c in checkins:
        chave = c.data_checkin.strftime('%m/%Y') if c.data_checkin else 'Sem data'
        if chave not in meses:
            meses[chave] = []
        meses[chave].append(c)
    return render_template('admin/historico_limpezas.html', meses=meses)

# ============ ADMIN ============

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not pode_gerenciar():
        flash('Acesso restrito.')
        return redirect(url_for('dashboard'))
    if session.get('funcao') == 'tesouraria':
        publicacoes = Publicacao.query.filter_by(tipo='financeiro').order_by(Publicacao.data_publicacao.desc()).all()
    elif session.get('funcao') == 'limpezas':
        publicacoes = Publicacao.query.filter_by(tipo='limpeza').order_by(Publicacao.data_publicacao.desc()).all()
    else:
        publicacoes = Publicacao.query.order_by(Publicacao.data_publicacao.desc()).all()
    return render_template('admin/painel.html', publicacoes=publicacoes)

@app.route('/admin/cadastrar', methods=['GET', 'POST'])
def cadastrar_publicacao():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not pode_gerenciar():
        flash('Acesso restrito.')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        titulo = request.form['titulo']
        conteudo = request.form['conteudo']
        tipo = request.form['tipo']
        if not pode_gerenciar(tipo):
            flash('Você não tem permissão para este tipo de publicação.')
            return redirect(url_for('admin'))
        data_evento_str = request.form.get('data_evento', '')
        data_evento = None
        if data_evento_str:
            try:
                data_evento = datetime.strptime(data_evento_str, '%Y-%m-%dT%H:%M')
            except:
                pass
        nova = Publicacao(titulo=titulo, conteudo=conteudo, tipo=tipo, data_evento=data_evento)
        db.session.add(nova)
        db.session.commit()
        flash(f'✅ {tipo.capitalize()} cadastrado(a) com sucesso!')
        if tipo == 'aviso':
            enviar_notificacao("📢 Novo Aviso - TUPBAO", titulo)
        if tipo == 'limpeza':
            enviar_notificacao("🧹 Nova Limpeza - TUPBAO", titulo)
        return redirect(url_for('admin'))
    funcao = session.get('funcao', 'membro')
    tipos_disponiveis = []
    if funcao in ['super_admin', 'admin']:
        tipos_disponiveis = ['gira', 'aviso', 'projeto', 'limpeza', 'financeiro', 'noticia', 'conta', 'recebimento']
    elif funcao == 'tesouraria':
        tipos_disponiveis = ['financeiro']
    elif funcao == 'limpezas':
        tipos_disponiveis = ['limpeza']
    return render_template('admin/cadastrar.html', tipos_disponiveis=tipos_disponiveis)

@app.route('/admin/editar/<int:id>', methods=['GET', 'POST'])
def editar_publicacao(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    pub = Publicacao.query.get_or_404(id)
    if not pode_gerenciar(pub.tipo):
        flash('Acesso restrito.')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        pub.titulo = request.form['titulo']
        pub.conteudo = request.form['conteudo']
        novo_tipo = request.form['tipo']
        if not pode_gerenciar(novo_tipo):
            flash('Você não tem permissão para este tipo.')
            return redirect(url_for('admin'))
        pub.tipo = novo_tipo
        data_evento_str = request.form.get('data_evento', '')
        if data_evento_str:
            try:
                pub.data_evento = datetime.strptime(data_evento_str, '%Y-%m-%dT%H:%M')
            except:
                pub.data_evento = None
        else:
            pub.data_evento = None
        db.session.commit()
        flash('✅ Publicação atualizada com sucesso!')
        if pub.tipo == 'limpeza':
            enviar_notificacao("🧹 Limpeza Atualizada - TUPBAO", pub.titulo)
        return redirect(url_for('admin'))
    return render_template('admin/editar.html', pub=pub)

@app.route('/admin/excluir/<int:id>')
def excluir_publicacao(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    pub = Publicacao.query.get_or_404(id)
    if not pode_gerenciar(pub.tipo):
        flash('Acesso restrito.')
        return redirect(url_for('dashboard'))
    db.session.delete(pub)
    db.session.commit()
    flash('🗑️ Publicação excluída.')
    return redirect(url_for('admin'))

# ============ GERENCIAR USUÁRIOS ============

@app.route('/admin/usuarios')
def gerenciar_usuarios():
    if not pode_gerenciar_usuarios():
        flash('Acesso restrito ao Dirigente.')
        return redirect(url_for('dashboard'))
    usuarios = Usuario.query.all()
    return render_template('admin/usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/cadastrar', methods=['GET', 'POST'])
def cadastrar_usuario():
    if not pode_gerenciar_usuarios():
        flash('Acesso restrito ao Dirigente.')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        funcao = request.form['funcao']
        if Usuario.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.')
        else:
            novo = Usuario(nome=nome, email=email, senha=generate_password_hash(senha), funcao=funcao, is_admin=(funcao in ['super_admin', 'admin']))
            db.session.add(novo)
            db.session.commit()
            flash(f'✅ Usuário {nome} cadastrado como {funcao}!')
            return redirect(url_for('gerenciar_usuarios'))
    return render_template('admin/cadastrar_usuario.html')

@app.route('/admin/usuarios/editar/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    if not pode_gerenciar_usuarios():
        flash('Acesso restrito ao Dirigente.')
        return redirect(url_for('dashboard'))
    user = Usuario.query.get_or_404(id)
    if request.method == 'POST':
        user.nome = request.form['nome']
        user.funcao = request.form['funcao']
        user.is_admin = (request.form['funcao'] in ['super_admin', 'admin'])
        if request.form.get('nova_senha'):
            user.senha = generate_password_hash(request.form['nova_senha'])
        db.session.commit()
        flash('✅ Usuário atualizado!')
        return redirect(url_for('gerenciar_usuarios'))
    return render_template('admin/editar_usuario.html', usuario=user)

@app.route('/admin/usuarios/excluir/<int:id>')
def excluir_usuario(id):
    if not pode_gerenciar_usuarios():
        flash('Acesso restrito ao Dirigente.')
        return redirect(url_for('dashboard'))
    user = Usuario.query.get_or_404(id)
    if user.email == 'admin@templo.com':
        flash('Não é possível excluir o admin principal.')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('🗑️ Usuário excluído.')
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/admin/usuarios/bloquear/<int:id>')
def bloquear_usuario(id):
    if not pode_gerenciar_usuarios():
        flash('Acesso restrito ao Dirigente.')
        return redirect(url_for('dashboard'))
    user = Usuario.query.get_or_404(id)
    if user.email == 'admin@templo.com':
        flash('Não é possível bloquear o admin principal.')
    else:
        user.ativo = False
        db.session.commit()
        flash(f'🔒 {user.nome} bloqueado.')
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/admin/usuarios/desbloquear/<int:id>')
def desbloquear_usuario(id):
    if not pode_gerenciar_usuarios():
        flash('Acesso restrito ao Dirigente.')
        return redirect(url_for('dashboard'))
    user = Usuario.query.get_or_404(id)
    user.ativo = True
    db.session.commit()
    flash(f'🔓 {user.nome} desbloqueado.')
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = Usuario.query.get(session['user_id'])
    if request.method == 'POST':
        senha_atual = request.form['senha_atual']
        nova_senha = request.form['nova_senha']
        confirmar_senha = request.form['confirmar_senha']
        if not check_password_hash(user.senha, senha_atual):
            flash('Senha atual incorreta.')
        elif nova_senha != confirmar_senha:
            flash('Nova senha e confirmação não conferem.')
        elif len(nova_senha) < 6:
            flash('A nova senha deve ter pelo menos 6 caracteres.')
        else:
            user.senha = generate_password_hash(nova_senha)
            db.session.commit()
            flash('✅ Senha alterada com sucesso!')
            return redirect(url_for('dashboard'))
    return render_template('perfil.html')

# ============ ROTA TEMPORÁRIA ============

@app.route('/resetar-banco')
def resetar_banco():
    try:
        db.drop_all()
        db.create_all()
        criar_admin_inicial()
        return '✅ Banco resetado! Faça login com admin@templo.com / mudar123'
    except Exception as e:
        return f'Erro: {e}'

# ============ INICIALIZAÇÃO ============

def criar_admin_inicial():
    if not Usuario.query.filter_by(email='admin@templo.com').first():
        admin = Usuario(nome='Dirigente', email='admin@templo.com', senha=generate_password_hash('mudar123'), is_admin=True, funcao='super_admin')
        db.session.add(admin)
        db.session.commit()
        print("✅ Super Admin criado: admin@templo.com / mudar123")

_banco_inicializado = False

@app.before_request
def inicializar_banco():
    global _banco_inicializado
    if not _banco_inicializado and request.path != '/resetar-banco':
        db.create_all()
        criar_admin_inicial()
        _banco_inicializado = True

@app.route('/OneSignalSDKWorker.js')
def serve_worker():
    return app.send_static_file('OneSignalSDKWorker.js')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
