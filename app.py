import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from services.notifications import enviar_notificacao as enviar_notificacao_service

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

    # Compatibilidade com o sistema atual
    is_admin = db.Column(db.Boolean, default=False)
    funcao = db.Column(db.String(50), default='membro')

    # Dados da conta
    ultimo_acesso = db.Column(db.DateTime, nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    grupo_limpeza = db.Column(db.Integer, nullable=True)
    celular = db.Column(db.String(20), nullable=True)

    # Perfil / participação na casa
    tipo_conta = db.Column(db.String(20), nullable=False, default='membro')
    cargo_casa = db.Column(db.String(30), nullable=False, default='membro')
    participa_mensalidade = db.Column(db.Boolean, nullable=False, default=True)
    participa_limpeza = db.Column(db.Boolean, nullable=False, default=True)

    # Permissões específicas
    gerencia_limpezas = db.Column(db.Boolean, nullable=False, default=False)
    gerencia_mensalidades = db.Column(db.Boolean, nullable=False, default=False)
    gerencia_financeiro = db.Column(db.Boolean, nullable=False, default=False)

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

class GrupoLimpeza(db.Model):
    __tablename__ = 'grupo_limpeza'

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, unique=True, nullable=False)
    periodo = db.Column(db.String(50), nullable=True)
    confirmado = db.Column(db.Boolean, default=False, nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    confirmado_por = db.Column(
        db.Integer,
        db.ForeignKey('usuario.id'),
        nullable=True
    )
    data_confirmacao = db.Column(db.DateTime, nullable=True)


class Mensalidade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    mes_ano = db.Column(db.String(7), nullable=False)
    status = db.Column(db.String(20), default='pendente')
    observacao = db.Column(db.String(200), nullable=True)
    data_pagamento = db.Column(db.DateTime, nullable=True)

class Comprovante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    mes_ano = db.Column(db.String(7), nullable=False)
    arquivo = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='pendente')
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)

class TurmaCurso(db.Model):
    __tablename__ = 'turma_curso'

    id = db.Column(db.Integer, primary_key=True)
    curso_nome = db.Column(db.String(120), nullable=False)
    turma_nome = db.Column(db.String(120), nullable=False)
    data_inicio = db.Column(db.Date, nullable=True)
    data_fim = db.Column(db.Date, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Publicacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(50))
    data_evento = db.Column(db.DateTime, nullable=True)
    data_publicacao = db.Column(db.DateTime, default=datetime.utcnow)

    # Público da comunicação: interno, publico ou curso.
    # NULL continua permitido para publicações antigas/legadas.
    publico = db.Column(db.String(20), nullable=True)
    turma_curso_id = db.Column(
        db.Integer,
        db.ForeignKey('turma_curso.id', ondelete='SET NULL'),
        nullable=True
    )

# ============ FUNÇÕES AUXILIARES ============

def pode_gerenciar(tipo=None):
    if 'user_id' not in session:
        return False

    funcao = session.get('funcao', 'membro')

    if funcao == 'super_admin':
        return True

    if funcao == 'admin':
        return True

    if tipo == 'limpeza' and session.get('gerencia_limpezas', False):
        return True

    if tipo == 'financeiro' and session.get('gerencia_financeiro', False):
        return True

    if tipo == 'mensalidades' and session.get('gerencia_mensalidades', False):
        return True

    return False


def pode_gerenciar_usuarios():
    return session.get('funcao') == 'super_admin'


def pode_gerenciar_tesouraria():
    if session.get('funcao') == 'super_admin':
        return True

    return (
        session.get('gerencia_financeiro', False)
        or session.get('gerencia_mensalidades', False)
    )


def pode_gerenciar_equipes_limpeza():
    if session.get('funcao') == 'super_admin':
        return True

    return session.get('gerencia_limpezas', False)

def enviar_notificacao(titulo, mensagem):
    return enviar_notificacao_service(titulo, mensagem)

    try:
        onesignal_app_id = os.environ.get('ONESIGNAL_APP_ID', '')
        onesignal_api_key = os.environ.get('ONESIGNAL_API_KEY', '')
        if not onesignal_app_id or not onesignal_api_key:
            return
        url = "https://onesignal.com/api/v1/notifications"
        headers = {"Authorization": f"Bearer {onesignal_api_key}", "Content-Type": "application/json"}
        data = {"app_id": onesignal_app_id, "headings": {"en": titulo}, "contents": {"en": mensagem}, "included_segments": ["Active Subscriptions"]}
        requests.post(url, json=data, headers=headers)
    except:
        pass

# ============ ROTAS PÚBLICAS ============

@app.route('/')
def index():
    giras = Publicacao.query.filter_by(tipo='gira')\
        .filter(Publicacao.data_evento >= datetime.utcnow())\
        .order_by(Publicacao.data_evento.asc()).limit(5).all()
    projetos = Publicacao.query.filter_by(tipo='projeto')\
        .filter(Publicacao.data_evento >= datetime.utcnow())\
        .order_by(Publicacao.data_evento.asc()).limit(3).all()
    return render_template('index.html', giras=giras, projetos=projetos)

@app.route('/agenda')
def agenda():
    giras = Publicacao.query.filter_by(tipo='gira')\
        .filter(Publicacao.data_evento >= datetime.utcnow())\
        .order_by(Publicacao.data_evento.asc()).all()
    return render_template('agenda.html', giras=giras)

@app.route('/projetos')
def projetos():
    projetos = Publicacao.query.filter_by(tipo='projeto')\
        .filter(Publicacao.data_evento >= datetime.utcnow())\
        .order_by(Publicacao.data_evento.asc()).all()
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

            session['tipo_conta'] = user.tipo_conta
            session['cargo_casa'] = user.cargo_casa
            session['participa_mensalidade'] = user.participa_mensalidade
            session['participa_limpeza'] = user.participa_limpeza
            session['gerencia_limpezas'] = user.gerencia_limpezas
            session['gerencia_mensalidades'] = user.gerencia_mensalidades
            session['gerencia_financeiro'] = user.gerencia_financeiro

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
    avisos = (
        Publicacao.query
        .filter_by(tipo='aviso')
        .filter(
            db.or_(
                Publicacao.publico == 'interno',
                Publicacao.publico.is_(None)
            )
        )
        .order_by(Publicacao.data_publicacao.desc())
        .all()
    )
    novos_avisos = 0
    for aviso in avisos:
        if aviso.id not in lidos:
            novos_avisos += 1
    return render_template('area_membros/dashboard.html', avisos=avisos, novos_avisos=novos_avisos)

@app.route('/dashboard/avisos')
def ver_avisos():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Membro comum vai direto aos recados internos.
    # Admin/Super Admin recebe o hub para separar os públicos.
    if session.get('funcao') not in ['super_admin', 'admin']:
        return redirect(url_for('ver_avisos_internos'))

    turmas_ativas = (
        TurmaCurso.query
        .filter_by(ativo=True)
        .order_by(TurmaCurso.data_inicio.desc(), TurmaCurso.id.desc())
        .all()
    )

    qtd_internos = (
        Publicacao.query
        .filter_by(tipo='aviso')
        .filter(
            db.or_(
                Publicacao.publico == 'interno',
                Publicacao.publico.is_(None)
            )
        )
        .count()
    )

    qtd_publicos = (
        Publicacao.query
        .filter_by(tipo='aviso', publico='publico')
        .count()
    )

    qtd_cursos = (
        Publicacao.query
        .filter_by(tipo='aviso', publico='curso')
        .count()
    )

    return render_template(
        'area_membros/avisos.html',
        turmas_ativas=turmas_ativas,
        qtd_internos=qtd_internos,
        qtd_publicos=qtd_publicos,
        qtd_cursos=qtd_cursos
    )


@app.route('/dashboard/avisos/internos')
def ver_avisos_internos():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    avisos = (
        Publicacao.query
        .filter_by(tipo='aviso')
        .filter(
            db.or_(
                Publicacao.publico == 'interno',
                Publicacao.publico.is_(None)
            )
        )
        .order_by(Publicacao.data_publicacao.desc())
        .all()
    )

    lidos = [
        al.publicacao_id
        for al in AvisoLido.query.filter_by(usuario_id=session['user_id']).all()
    ]

    return render_template(
        'area_membros/avisos_internos.html',
        avisos=avisos,
        lidos=lidos
    )


@app.route('/dashboard/avisos/publicos')
def ver_avisos_publicos():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('funcao') not in ['super_admin', 'admin']:
        flash('Acesso restrito.')
        return redirect(url_for('ver_avisos_internos'))

    avisos = (
        Publicacao.query
        .filter_by(tipo='aviso', publico='publico')
        .order_by(Publicacao.data_publicacao.desc())
        .all()
    )

    return render_template(
        'area_membros/avisos_publicos.html',
        avisos=avisos
    )


@app.route('/dashboard/avisos/cursos')
def ver_avisos_cursos():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('funcao') not in ['super_admin', 'admin']:
        flash('Acesso restrito.')
        return redirect(url_for('ver_avisos_internos'))

    turmas = (
        TurmaCurso.query
        .filter_by(ativo=True)
        .order_by(TurmaCurso.data_inicio.desc(), TurmaCurso.id.desc())
        .all()
    )

    return render_template(
        'area_membros/avisos_cursos.html',
        turmas=turmas
    )


@app.route('/dashboard/avisos/marcar-lido/<int:id>')
def marcar_lido(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    aviso = Publicacao.query.get_or_404(id)

    # Só recados internos/legados podem ser marcados como lidos por membros.
    if aviso.tipo != 'aviso' or aviso.publico not in [None, 'interno']:
        flash('Aviso inválido.')
        return redirect(url_for('ver_avisos_internos'))

    if not AvisoLido.query.filter_by(
        usuario_id=session['user_id'],
        publicacao_id=id
    ).first():
        novo = AvisoLido(
            usuario_id=session['user_id'],
            publicacao_id=id
        )
        db.session.add(novo)
        db.session.commit()

    return redirect(url_for('ver_avisos_internos'))

@app.route('/dashboard/limpezas')
def ver_limpezas():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    grupos = (
        GrupoLimpeza.query
        .filter_by(ativo=True)
        .order_by(GrupoLimpeza.numero.asc())
        .all()
    )

    membros = (
        Usuario.query
        .filter_by(ativo=True, participa_limpeza=True)
        .filter(Usuario.grupo_limpeza.isnot(None))
        .order_by(Usuario.nome.asc())
        .all()
    )

    membros_por_grupo = {grupo.numero: [] for grupo in grupos}

    for membro in membros:
        if membro.grupo_limpeza in membros_por_grupo:
            membros_por_grupo[membro.grupo_limpeza].append(membro)

    return render_template(
        'area_membros/limpezas.html',
        grupos=grupos,
        membros_por_grupo=membros_por_grupo
    )

@app.route('/minha-mensalidade')
def minha_mensalidade():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    ano_atual = datetime.utcnow().year
    meses_lista = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
    historico = []
    for mes in meses_lista:
        mes_ano = f"{mes}/{ano_atual}"
        mensalidade = Mensalidade.query.filter_by(usuario_id=session['user_id'], mes_ano=mes_ano).first()
        comprovante = Comprovante.query.filter_by(usuario_id=session['user_id'], mes_ano=mes_ano).first()
        historico.append({
            'mes': mes,
            'mes_ano': mes_ano,
            'status': mensalidade.status if mensalidade else 'pendente',
            'observacao': mensalidade.observacao if mensalidade else '',
            'comprovante': comprovante.status if comprovante else None
        })
    return render_template('area_membros/minha_mensalidade.html', historico=historico, ano_atual=ano_atual)

@app.route('/upload-comprovante', methods=['POST'])
def upload_comprovante():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if 'arquivo' not in request.files:
        flash('Nenhum arquivo enviado.')
        return redirect(url_for('minha_mensalidade'))
    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado.')
        return redirect(url_for('minha_mensalidade'))
    mes_atual = datetime.utcnow().strftime('%m/%Y')
    nome_arquivo = f"{session['user_id']}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{arquivo.filename}"
    caminho = os.path.join('static', 'uploads', nome_arquivo)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    arquivo.save(caminho)
    novo = Comprovante(usuario_id=session['user_id'], mes_ano=mes_atual, arquivo=nome_arquivo)
    db.session.add(novo)
    db.session.commit()
    enviar_notificacao("📄 Novo Comprovante - TUPBAO", f"{session['user_nome']} enviou comprovante de mensalidade.")
    flash('✅ Comprovante enviado! Aguarde a confirmação da tesouraria.')
    return redirect(url_for('minha_mensalidade'))

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
    mes_selecionado = request.args.get('mes', datetime.utcnow().strftime('%m/%Y'))
    publicacoes = Publicacao.query.filter_by(tipo='conta').order_by(Publicacao.data_publicacao.desc()).all()
    resultado = [p for p in publicacoes if p.data_publicacao.strftime('%m/%Y') == mes_selecionado]
    meses_disponiveis = sorted(set(p.data_publicacao.strftime('%m/%Y') for p in publicacoes), reverse=True)
    if not meses_disponiveis:
        meses_disponiveis = [datetime.utcnow().strftime('%m/%Y')]
    return render_template('area_membros/financeiro_contas.html', publicacoes=resultado, mes_selecionado=mes_selecionado, meses_disponiveis=meses_disponiveis)

@app.route('/dashboard/financeiro/recebimentos')
def ver_recebimentos():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    mes_selecionado = request.args.get('mes', datetime.utcnow().strftime('%m/%Y'))
    publicacoes = Publicacao.query.filter_by(tipo='recebimento').order_by(Publicacao.data_publicacao.desc()).all()
    resultado = [p for p in publicacoes if p.data_publicacao.strftime('%m/%Y') == mes_selecionado]
    meses_disponiveis = sorted(set(p.data_publicacao.strftime('%m/%Y') for p in publicacoes), reverse=True)
    if not meses_disponiveis:
        meses_disponiveis = [datetime.utcnow().strftime('%m/%Y')]
    return render_template('area_membros/financeiro_recebimentos.html', publicacoes=resultado, mes_selecionado=mes_selecionado, meses_disponiveis=meses_disponiveis)

# ============ TESOURARIA - MENSALIDADES ============

@app.route('/dashboard/mensalidades', methods=['GET', 'POST'])
def mensalidades():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not pode_gerenciar_tesouraria():
        flash('Acesso restrito à tesouraria.')
        return redirect(url_for('dashboard'))
    mes_atual = datetime.utcnow().strftime('%m/%Y')
    membros = (
        Usuario.query
        .filter_by(ativo=True, participa_mensalidade=True)
        .order_by(Usuario.nome.asc())
        .all()
    )
    if request.method == 'POST':
        for membro in membros:
            novo_status = request.form.get(f'status_{membro.id}', 'pendente')
            obs = request.form.get(f'obs_{membro.id}', '')
            mensalidade = Mensalidade.query.filter_by(usuario_id=membro.id, mes_ano=mes_atual).first()
            if novo_status == 'pendente':
                if mensalidade: db.session.delete(mensalidade)
            else:
                if not mensalidade:
                    mensalidade = Mensalidade(usuario_id=membro.id, mes_ano=mes_atual)
                    db.session.add(mensalidade)
                mensalidade.status = novo_status
                mensalidade.observacao = obs if novo_status == 'acordo' else None
                if novo_status == 'pago': mensalidade.data_pagamento = datetime.utcnow()
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
    if not pode_gerenciar_tesouraria(): flash('Acesso restrito à tesouraria.'); return redirect(url_for('dashboard'))
    mes_atual = datetime.utcnow().strftime('%m/%Y')
    dia = datetime.utcnow().day
    if dia < 10: flash('Só pode enviar cobrança a partir do dia 10.'); return redirect(url_for('mensalidades'))
    membros = (
        Usuario.query
        .filter_by(ativo=True, participa_mensalidade=True)
        .order_by(Usuario.nome.asc())
        .all()
    )
    pendentes = []
    for m in membros:
        msg = Mensalidade.query.filter_by(usuario_id=m.id, mes_ano=mes_atual).first()
        if not msg or msg.status == 'pendente': pendentes.append(m.nome)
    if pendentes:
        enviar_notificacao("💰 Mensalidade em Aberto - TUPBAO", "Favor entrar em contato com a tesouraria.")
        flash(f'✅ Cobrança enviada! {len(pendentes)} membros pendentes.')
    else: flash('✅ Todos estão em dia ou com acordo!')
    return redirect(url_for('mensalidades'))

# ============ CHECK-IN LIMPEZA ============

@app.route('/checkin/limpeza', methods=['GET', 'POST'])
def checkin_limpeza():
    if 'user_id' not in session: session['next_page'] = '/checkin/limpeza'; return redirect(url_for('login'))
    grupos = [
        {'nome': 'Grupo 1', 'periodo': '29/06 a 04/07'}, {'nome': 'Grupo 2', 'periodo': '22/06 a 27/06'},
        {'nome': 'Grupo 3', 'periodo': '06/07 a 11/07'}, {'nome': 'Grupo 4', 'periodo': '13/07 a 18/07'},
        {'nome': 'Grupo 5', 'periodo': '20/07 a 25/07'}, {'nome': 'Grupo 6', 'periodo': '27/07 a 01/08'},
    ]
    if request.method == 'POST':
        grupo_nome = request.form['grupo']; grupo_periodo = request.form['periodo']
        checkin = CheckinLimpeza(usuario_id=session['user_id'], usuario_nome=session['user_nome'], grupo=grupo_nome, periodo=grupo_periodo)
        db.session.add(checkin); db.session.commit()
        flash(f'✅ Limpeza do {grupo_nome} confirmada! Axé!')
        return redirect(url_for('dashboard'))
    return render_template('checkin_limpeza.html', grupos=grupos)

@app.route('/admin/limpezas/excluir/<int:id>')
def excluir_checkin(id):
    if 'user_id' not in session or not pode_gerenciar(): flash('Acesso restrito.'); return redirect(url_for('dashboard'))
    checkin = CheckinLimpeza.query.get_or_404(id); db.session.delete(checkin); db.session.commit()
    flash('🗑️ Check-in excluído.'); return redirect(url_for('historico_limpezas'))

@app.route('/admin/limpezas/historico')
def historico_limpezas():
    if 'user_id' not in session or not pode_gerenciar(): flash('Acesso restrito.'); return redirect(url_for('dashboard'))
    checkins = CheckinLimpeza.query.order_by(CheckinLimpeza.data_checkin.desc()).all()
    meses = {}
    for c in checkins:
        chave = c.data_checkin.strftime('%m/%Y') if c.data_checkin else 'Sem data'
        if chave not in meses: meses[chave] = []
        meses[chave].append(c)
    return render_template('admin/historico_limpezas.html', meses=meses)



@app.route('/admin/limpezas/equipes', methods=['GET', 'POST'])
def gerenciar_equipes_limpeza():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not pode_gerenciar_equipes_limpeza():
        flash('Acesso restrito à gestão das equipes de limpeza.')
        return redirect(url_for('dashboard'))

    equipes_ativas = (
        GrupoLimpeza.query
        .filter_by(ativo=True)
        .order_by(GrupoLimpeza.numero.asc())
        .all()
    )

    equipes_inativas = (
        GrupoLimpeza.query
        .filter_by(ativo=False)
        .order_by(GrupoLimpeza.numero.asc())
        .all()
    )

    membros = (
        Usuario.query
        .filter_by(ativo=True, participa_limpeza=True)
        .order_by(Usuario.nome.asc())
        .all()
    )

    membros_por_grupo = {equipe.numero: [] for equipe in equipes_ativas}
    sem_equipe = []

    for membro in membros:
        if membro.grupo_limpeza in membros_por_grupo:
            membros_por_grupo[membro.grupo_limpeza].append(membro)
        else:
            sem_equipe.append(membro)

    return render_template(
        'admin/gerenciar_equipes.html',
        equipes=equipes_ativas,
        equipes_inativas=equipes_inativas,
        membros_por_grupo=membros_por_grupo,
        sem_equipe=sem_equipe
    )


@app.route('/admin/limpezas/equipes/nova', methods=['POST'])
def criar_equipe_limpeza():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not pode_gerenciar_equipes_limpeza():
        flash('Acesso restrito à gestão das equipes de limpeza.')
        return redirect(url_for('dashboard'))

    maior_numero = db.session.query(db.func.max(GrupoLimpeza.numero)).scalar() or 0
    novo_numero = maior_numero + 1
    periodo = request.form.get('periodo', '').strip()

    nova = GrupoLimpeza(
        numero=novo_numero,
        periodo=periodo,
        confirmado=False,
        ativo=True
    )

    db.session.add(nova)
    db.session.commit()

    flash(f'✅ Equipe {novo_numero} criada com sucesso!')
    return redirect(url_for('gerenciar_equipes_limpeza'))


@app.route('/admin/limpezas/equipes/<int:numero>/periodo', methods=['POST'])
def editar_periodo_equipe(numero):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not pode_gerenciar_equipes_limpeza():
        flash('Acesso restrito à gestão das equipes de limpeza.')
        return redirect(url_for('dashboard'))

    equipe = GrupoLimpeza.query.filter_by(numero=numero).first_or_404()
    novo_periodo = request.form.get('periodo', '').strip()

    if novo_periodo != (equipe.periodo or ''):
        equipe.periodo = novo_periodo
        equipe.confirmado = False
        equipe.confirmado_por = None
        equipe.data_confirmacao = None
        db.session.commit()
        flash(f'✅ Período da Equipe {numero} atualizado!')
    else:
        flash('Nenhuma alteração foi realizada.')

    return redirect(url_for('gerenciar_equipes_limpeza'))


@app.route('/admin/limpezas/equipes/<int:numero>/adicionar', methods=['POST'])
def adicionar_membro_equipe(numero):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not pode_gerenciar_equipes_limpeza():
        flash('Acesso restrito à gestão das equipes de limpeza.')
        return redirect(url_for('dashboard'))

    equipe = GrupoLimpeza.query.filter_by(numero=numero, ativo=True).first_or_404()
    usuario_id = request.form.get('usuario_id', type=int)

    if not usuario_id:
        flash('Selecione um membro.')
        return redirect(url_for('gerenciar_equipes_limpeza'))

    membro = Usuario.query.filter_by(
        id=usuario_id,
        ativo=True,
        participa_limpeza=True
    ).first_or_404()
    membro.grupo_limpeza = equipe.numero
    db.session.commit()

    flash(f'✅ {membro.nome} adicionado(a) à Equipe {equipe.numero}.')
    return redirect(url_for('gerenciar_equipes_limpeza'))


@app.route('/admin/limpezas/equipes/<int:numero>/remover/<int:usuario_id>', methods=['POST'])
def remover_membro_equipe(numero, usuario_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not pode_gerenciar_equipes_limpeza():
        flash('Acesso restrito à gestão das equipes de limpeza.')
        return redirect(url_for('dashboard'))

    membro = Usuario.query.get_or_404(usuario_id)

    if membro.grupo_limpeza == numero:
        membro.grupo_limpeza = None
        db.session.commit()
        flash(f'✅ {membro.nome} removido(a) da Equipe {numero}.')
    else:
        flash('Este membro não pertence a essa equipe.')

    return redirect(url_for('gerenciar_equipes_limpeza'))


@app.route('/admin/limpezas/equipes/<int:numero>/desativar', methods=['POST'])
def desativar_equipe_limpeza(numero):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not pode_gerenciar_equipes_limpeza():
        flash('Acesso restrito à gestão das equipes de limpeza.')
        return redirect(url_for('dashboard'))

    equipe = GrupoLimpeza.query.filter_by(numero=numero).first_or_404()

    membros = Usuario.query.filter_by(grupo_limpeza=numero).all()
    for membro in membros:
        membro.grupo_limpeza = None

    equipe.ativo = False
    db.session.commit()

    flash(f'✅ Equipe {numero} desativada. Os membros foram movidos para "Sem equipe".')
    return redirect(url_for('gerenciar_equipes_limpeza'))


@app.route('/admin/limpezas/equipes/<int:numero>/reativar', methods=['POST'])
def reativar_equipe_limpeza(numero):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not pode_gerenciar_equipes_limpeza():
        flash('Acesso restrito à gestão das equipes de limpeza.')
        return redirect(url_for('dashboard'))

    equipe = GrupoLimpeza.query.filter_by(numero=numero).first_or_404()
    equipe.ativo = True
    equipe.confirmado = False
    equipe.confirmado_por = None
    equipe.data_confirmacao = None
    db.session.commit()

    flash(f'✅ Equipe {numero} reativada.')
    return redirect(url_for('gerenciar_equipes_limpeza'))


@app.route('/admin/limpezas/grupos', methods=['GET', 'POST'])
def gerenciar_grupos_limpeza():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not pode_gerenciar_equipes_limpeza():
        flash('Acesso restrito ao gerenciamento de limpezas.')
        return redirect(url_for('dashboard'))

    grupos = (
        GrupoLimpeza.query
        .filter_by(ativo=True)
        .order_by(GrupoLimpeza.numero.asc())
        .all()
    )

    if request.method == 'POST':
        alterou = False

        for grupo in grupos:
            novo_periodo = request.form.get(
                f'periodo_{grupo.numero}', ''
            ).strip()

            if novo_periodo != (grupo.periodo or ''):
                grupo.periodo = novo_periodo
                grupo.confirmado = False
                grupo.confirmado_por = None
                grupo.data_confirmacao = None
                alterou = True

        if alterou:
            db.session.commit()
            flash('✅ Períodos das equipes atualizados com sucesso!')
        else:
            flash('Nenhuma alteração foi realizada.')

        return redirect(url_for('gerenciar_grupos_limpeza'))

    return render_template(
        'admin/grupos_limpeza.html',
        grupos=grupos
    )


# ============ ADMIN ============

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return redirect(url_for('dashboard'))

@app.route('/admin/cadastrar', methods=['GET', 'POST'])
def cadastrar_publicacao():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Nova Publicação é destinada somente às publicações gerais do templo.
    # Avisos, limpeza e financeiro possuem fluxos próprios.
    if session.get('funcao') not in ['super_admin', 'admin']:
        flash('Acesso restrito.')
        return redirect(url_for('dashboard'))

    tipos_disponiveis = ['gira', 'projeto', 'evento']

    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        conteudo = request.form.get('conteudo', '').strip()
        tipo = request.form.get('tipo', '').strip()

        # Não confiar apenas nas opções exibidas pelo HTML.
        if tipo not in tipos_disponiveis:
            flash('Tipo de publicação inválido.')
            return redirect(url_for('cadastrar_publicacao'))

        if not titulo or not conteudo:
            flash('Título e conteúdo são obrigatórios.')
            return redirect(url_for('cadastrar_publicacao'))

        data_evento = None
        data_evento_str = request.form.get('data_evento', '').strip()

        if data_evento_str:
            try:
                data_evento = datetime.strptime(
                    data_evento_str,
                    '%Y-%m-%dT%H:%M'
                )
            except ValueError:
                flash('Data do evento inválida.')
                return redirect(url_for('cadastrar_publicacao'))

        nova = Publicacao(
            titulo=titulo,
            conteudo=conteudo,
            tipo=tipo,
            data_evento=data_evento
        )

        db.session.add(nova)
        db.session.commit()

        nomes_tipos = {
            'gira': 'Gira',
            'projeto': 'Projeto Social',
            'evento': 'Evento'
        }

        flash(
            f'✅ {nomes_tipos.get(tipo, "Publicação")} '
            'cadastrado(a) com sucesso!'
        )

        return redirect(url_for('dashboard'))

    return render_template(
        'admin/cadastrar.html',
        tipos_disponiveis=tipos_disponiveis
    )

@app.route('/admin/editar/<int:id>', methods=['GET', 'POST'])
def editar_publicacao(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    pub = Publicacao.query.get_or_404(id)
    if not pode_gerenciar(pub.tipo): flash('Acesso restrito.'); return redirect(url_for('dashboard'))
    if request.method == 'POST':
        pub.titulo = request.form['titulo']; pub.conteudo = request.form['conteudo']; novo_tipo = request.form['tipo']
        if not pode_gerenciar(novo_tipo): flash('Você não tem permissão para este tipo.'); return redirect(url_for('admin'))
        pub.tipo = novo_tipo
        data_evento_str = request.form.get('data_evento', '')
        if data_evento_str:
            try: pub.data_evento = datetime.strptime(data_evento_str, '%Y-%m-%dT%H:%M')
            except: pub.data_evento = None
        else: pub.data_evento = None
        db.session.commit()
        flash('✅ Publicação atualizada com sucesso!')
        if pub.tipo == 'limpeza': enviar_notificacao("🧹 Limpeza Atualizada - TUPBAO", pub.titulo)
        return redirect(url_for('admin'))
    return render_template('admin/editar.html', pub=pub)

@app.route('/admin/excluir/<int:id>')
def excluir_publicacao(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    pub = Publicacao.query.get_or_404(id)
    if not pode_gerenciar(pub.tipo): flash('Acesso restrito.'); return redirect(url_for('dashboard'))
    db.session.delete(pub); db.session.commit()
    flash('🗑️ Publicação excluída.'); return redirect(url_for('admin'))

# ============ GERENCIAR USUÁRIOS ============

@app.route('/admin/usuarios')
def gerenciar_usuarios():
    if not pode_gerenciar_usuarios(): flash('Acesso restrito ao Dirigente.'); return redirect(url_for('dashboard'))
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
        celular = ''.join(filter(str.isdigit, request.form.get('celular', '')))

        grupo_limpeza_raw = request.form.get('grupo_limpeza', '').strip()
        grupo_limpeza = int(grupo_limpeza_raw) if grupo_limpeza_raw.isdigit() else None

        if Usuario.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.')
        else:
            novo = Usuario(
                nome=nome,
                email=email,
                senha=generate_password_hash(senha),
                funcao=funcao,
                is_admin=(funcao in ['super_admin', 'admin']),
                grupo_limpeza=grupo_limpeza,
                celular=celular if celular else None
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

        grupo_limpeza_raw = request.form.get('grupo_limpeza', '').strip()
        user.grupo_limpeza = int(grupo_limpeza_raw) if grupo_limpeza_raw.isdigit() else None

        celular = ''.join(filter(str.isdigit, request.form.get('celular', '')))
        user.celular = celular if celular else None

        if request.form.get('nova_senha'):
            user.senha = generate_password_hash(request.form['nova_senha'])

        db.session.commit()
        flash('✅ Usuário atualizado!')
        return redirect(url_for('gerenciar_usuarios'))

    return render_template('admin/editar_usuario.html', usuario=user)

@app.route('/admin/usuarios/excluir/<int:id>')
def excluir_usuario(id):
    if not pode_gerenciar_usuarios(): flash('Acesso restrito ao Dirigente.'); return redirect(url_for('dashboard'))
    user = Usuario.query.get_or_404(id)
    if user.email == 'admin@templo.com': flash('Não é possível excluir o admin principal.')
    else: db.session.delete(user); db.session.commit(); flash('🗑️ Usuário excluído.')
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/admin/usuarios/bloquear/<int:id>')
def bloquear_usuario(id):
    if not pode_gerenciar_usuarios(): flash('Acesso restrito ao Dirigente.'); return redirect(url_for('dashboard'))
    user = Usuario.query.get_or_404(id)
    if user.email == 'admin@templo.com': flash('Não é possível bloquear o admin principal.')
    else: user.ativo = False; db.session.commit(); flash(f'🔒 {user.nome} bloqueado.')
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/admin/usuarios/desbloquear/<int:id>')
def desbloquear_usuario(id):
    if not pode_gerenciar_usuarios(): flash('Acesso restrito ao Dirigente.'); return redirect(url_for('dashboard'))
    user = Usuario.query.get_or_404(id); user.ativo = True; db.session.commit()
    flash(f'🔓 {user.nome} desbloqueado.'); return redirect(url_for('gerenciar_usuarios'))

@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = Usuario.query.get(session['user_id'])
    if request.method == 'POST':
        senha_atual = request.form['senha_atual']; nova_senha = request.form['nova_senha']; confirmar_senha = request.form['confirmar_senha']
        if not check_password_hash(user.senha, senha_atual): flash('Senha atual incorreta.')
        elif nova_senha != confirmar_senha: flash('Nova senha e confirmação não conferem.')
        elif len(nova_senha) < 6: flash('A nova senha deve ter pelo menos 6 caracteres.')
        else: user.senha = generate_password_hash(nova_senha); db.session.commit(); flash('✅ Senha alterada com sucesso!'); return redirect(url_for('dashboard'))
    return render_template('perfil.html')

# ============ ROTA TEMPORÁRIA ============

@app.route('/resetar-banco')
def resetar_banco():
    try: db.drop_all(); db.create_all(); criar_admin_inicial(); return '✅ Banco resetado! Faça login com admin@templo.com / mudar123'
    except Exception as e: return f'Erro: {e}'

# ============ INICIALIZAÇÃO ============

def criar_admin_inicial():
    if not Usuario.query.filter_by(email='admin@templo.com').first():
        admin = Usuario(
            nome='Administrador',
            email='admin@templo.com',
            senha=generate_password_hash('mudar123'),
            is_admin=True,
            funcao='super_admin',
            tipo_conta='sistema',
            cargo_casa='sistema',
            participa_mensalidade=False,
            participa_limpeza=False,
            gerencia_limpezas=False,
            gerencia_mensalidades=False,
            gerencia_financeiro=False
        )
        db.session.add(admin); db.session.commit()
        print("✅ Super Admin criado: admin@templo.com / mudar123")

_banco_inicializado = False

@app.before_request
def inicializar_banco():
    global _banco_inicializado
    if not _banco_inicializado and request.path != '/resetar-banco':
        db.create_all(); criar_admin_inicial(); _banco_inicializado = True

@app.route('/OneSignalSDKWorker.js')
def serve_worker():
    return app.send_static_file('OneSignalSDKWorker.js')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)