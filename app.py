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

class Publicacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(50))  # 'gira', 'projeto', 'noticia', 'aviso', 'limpeza', 'financeiro'
    data_evento = db.Column(db.DateTime, nullable=True)
    data_publicacao = db.Column(db.DateTime, default=datetime.utcnow)

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
            flash('Login realizado com sucesso!')
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
    avisos = Publicacao.query.filter_by(tipo='aviso').order_by(Publicacao.data_publicacao.desc()).all()
    return render_template('area_membros/dashboard.html', avisos=avisos)

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

# ============ ADMIN ============

@app.route('/admin')
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Acesso restrito ao dirigente.')
        return redirect(url_for('dashboard'))
    
    publicacoes = Publicacao.query.order_by(Publicacao.data_publicacao.desc()).all()
    return render_template('admin/painel.html', publicacoes=publicacoes)

@app.route('/admin/cadastrar', methods=['GET', 'POST'])
def cadastrar_publicacao():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Acesso restrito ao dirigente.')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        titulo = request.form['titulo']
        conteudo = request.form['conteudo']
        tipo = request.form['tipo']
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
        return redirect(url_for('admin'))
    
    return render_template('admin/cadastrar.html')

@app.route('/admin/editar/<int:id>', methods=['GET', 'POST'])
def editar_publicacao(id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Acesso restrito ao dirigente.')
        return redirect(url_for('dashboard'))
    
    pub = Publicacao.query.get_or_404(id)
    
    if request.method == 'POST':
        pub.titulo = request.form['titulo']
        pub.conteudo = request.form['conteudo']
        pub.tipo = request.form['tipo']
        
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
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Acesso restrito ao dirigente.')
        return redirect(url_for('dashboard'))
    
    pub = Publicacao.query.get_or_404(id)
    db.session.delete(pub)
    db.session.commit()
    flash('🗑️ Publicação excluída.')
    return redirect(url_for('admin'))

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

# ============ INICIALIZAÇÃO ============

def criar_admin_inicial():
    if not Usuario.query.filter_by(email='admin@templo.com').first():
        admin = Usuario(
            nome='Dirigente',
            email='admin@templo.com',
            senha=generate_password_hash('mudar123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Usuário admin criado: admin@templo.com / mudar123")

# Inicializar banco na primeira requisição
_banco_inicializado = False

@app.before_request
def inicializar_banco():
    global _banco_inicializado
    if not _banco_inicializado:
        db.create_all()
        criar_admin_inicial()
        _banco_inicializado = True

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)