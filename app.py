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

def enviar_notificacao(titulo, mensagem):
    """Envia notificação push via OneSignal"""
    try:
        url = "https://onesignal.com/api/v1/notifications"
        headers = {
            "Authorization": "Basic os_v2_app_c5lk3msgarb7nccxhhs4jru6ziyuegufbgruqpv62o4rip5bubxxxcmqto3pyuoovlcu6smuhf76rvj2d7gkm3llqatq2kwe7igrf4a",
            "Content-Type": "application/json"
        }
        data = {
            "app_id": "1756adb2-4604-43f6-8857-39e5c4c69eca",
            "headings": {"en": titulo},
            "contents": {"en": mensagem},
            "included_segments": ["Subscribed Users"]
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        user = Usuario.query.filter_by(email=email).first()
        if user and check_password_hash(user.senha, senha):
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
    
    ultimo_acesso_anterior = session.get('ultimo_acesso_anterior')
    
    if ultimo_acesso_anterior:
        novos_avisos = Publicacao.query.filter_by(tipo='aviso')\
            .filter(Publicacao.data_publicacao > ultimo_acesso_anterior).count()
    else:
        novos_avisos = Publicacao.query.filter_by(tipo='aviso').count()
    
    avisos = Publicacao.query.filter_by(tipo='aviso').order_by(Publicacao.data_publicacao.desc()).all()
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

@app.route('/dashboard/financeiro')
def ver_financeiro():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    financeiro = Publicacao.query.filter_by(tipo='financeiro').order_by(Publicacao.data_publicacao.desc()).all()
    return render_template('area_membros/financeiro.html', financeiro=financeiro)

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
        checkin = CheckinLimpeza(
            usuario_id=session['user_id'],
            usuario_nome=session['user_nome'],
            grupo=grupo_nome,
            periodo=grupo_periodo
        )
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
    
    checkins = CheckinLimpeza.query.order_by(CheckinLimpeza.periodo.desc(), CheckinLimpeza.data_checkin.desc()).all()
    
    periodos = {}
    for c in checkins:
        chave = c.periodo if c.periodo else 'Sem período'
        if chave not in periodos:
            periodos[chave] = []
        periodos[chave].append(c)
    
    return render_template('admin/historico_limpezas.html', periodos=periodos)

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
        nova = Publicacao(
            titulo=titulo,
            conteudo=conteudo,
            tipo=tipo,
            data_evento=data_evento
        )
        db.session.add(nova)
        db.session.commit()
        flash(f'✅ {tipo.capitalize()} cadastrado(a) com sucesso!')
        # Enviar notificação push se for aviso
        if tipo == 'aviso':
            enviar_notificacao("📢 Novo Aviso - TUPBAO", titulo)
        return redirect(url_for('admin'))
    funcao = session.get('funcao', 'membro')
    tipos_disponiveis = []
    if funcao in ['super_admin', 'admin']:
        tipos_disponiveis = ['gira', 'aviso', 'projeto', 'limpeza', 'financeiro', 'noticia']
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
            novo = Usuario(
                nome=nome,
                email=email,
                senha=generate_password_hash(senha),
                funcao=funcao,
                is_admin=(funcao in ['super_admin', 'admin'])
            )
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
        admin = Usuario(
            nome='Dirigente',
            email='admin@templo.com',
            senha=generate_password_hash('mudar123'),
            is_admin=True,
            funcao='super_admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Super Admin criado: admin@templo.com / mudar123")

_banco_inicializado = False

@app.before_request
def inicializar_banco():
    global _banco_inicializado
    if not _banco_inicializado:
        db.create_all()
        criar_admin_inicial()
        _banco_inicializado = True

@app.route('/OneSignalSDKWorker.js')
def serve_worker():
    return app.send_static_file('OneSignalSDKWorker.js')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
