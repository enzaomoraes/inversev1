from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import openai
from PyPDF2 import PdfReader
from fpdf import FPDF
from sqlalchemy import inspect

openai.api_key = "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"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(os.path.abspath(os.path.dirname(__file__)), "instance/database.db")}'
db = SQLAlchemy(app)

if not os.path.exists('instance'):
    os.makedirs('instance')
    
with app.app_context():
    try:
        db.create_all()
        print("Banco de dados criado com sucesso.")
    except Exception as e:
        print(f"Erro ao criar o banco de dados: {e}")

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)

class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    filename = db.Column(db.String(150), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    adapted_content = db.Column(db.Text)  # A coluna deve estar aqui
    
    
    # Definindo uma pasta para salvar os arquivos
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Redireciona para a página de login ao acessar a raiz do site
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Atualizar o método de hash para 'pbkdf2:sha256'
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registro realizado com sucesso! Faça login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Falha no login. Verifique seu nome de usuário e senha.')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        file = request.files['file']
        resume_name = request.form['name']
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Salvar detalhes do currículo no banco
            new_resume = Resume(name=resume_name, filename=filename, user_id=current_user.id)
            db.session.add(new_resume)
            db.session.commit()
            flash('Currículo enviado com sucesso!')
            return redirect(url_for('dashboard'))
        else:
            flash('Formato de arquivo inválido. Envie um PDF.')

    # Obtém todos os currículos carregados pelo usuário logado
    resumes = Resume.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', resumes=resumes)

@app.route('/download_resume/<int:resume_id>')
@login_required
def download_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        flash("Você não tem permissão para acessar este currículo.")
        return redirect(url_for('dashboard'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], resume.filename, as_attachment=True)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/upload_resume', methods=['GET', 'POST'])
@login_required
def upload_resume():
    if request.method == 'POST':
        file = request.files['file']
        resume_name = request.form['name']
        
        if file and allowed_file(file.filename):
            # Garantir que o nome do arquivo é seguro
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Salvar os detalhes no banco de dados
            new_resume = Resume(name=resume_name, filename=filename, user_id=current_user.id)
            db.session.add(new_resume)
            db.session.commit()
            flash('Currículo enviado com sucesso!')
            return redirect(url_for('dashboard'))
        else:
            flash('Formato de arquivo inválido. Envie um PDF.')
    return render_template('upload_resume.html')

@app.route('/edit_resume/<int:resume_id>', methods=['GET', 'POST'])
@login_required
def edit_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        flash("Você não tem permissão para editar este currículo.")
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        new_name = request.form['name']
        resume.name = new_name
        db.session.commit()
        flash("Nome do currículo atualizado com sucesso!")
        return redirect(url_for('dashboard'))
    
    return render_template('edit_resume.html', resume=resume)

@app.route('/delete_resume/<int:resume_id>', methods=['POST'])
@login_required
def delete_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        flash("Você não tem permissão para excluir este currículo.")
        return redirect(url_for('dashboard'))
    
    # Remove o arquivo do sistema
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], resume.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Remove o registro do banco de dados
    db.session.delete(resume)
    db.session.commit()
    flash("Currículo excluído com sucesso!")
    return redirect(url_for('dashboard'))

# Função para extrair o texto do PDF (apenas resumo e experiência profissional)
def extract_resume_sections(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()

    # Supondo que você tenha uma maneira de identificar "Summary" e "Professional Experience"
    summary_start = text.lower().find("summary")
    experience_start = text.lower().find("professional experience")
    
    summary_text = text[summary_start:experience_start].strip() if summary_start != -1 else ""
    experience_text = text[experience_start:].strip() if experience_start != -1 else ""

    return summary_text, experience_text

@app.route('/adapt_resume/<int:resume_id>', methods=['GET', 'POST'])
@login_required
def adapt_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        flash("You do not have permission to adapt this resume.")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        job_description = request.form['job_description']
        summary_text, experience_text = extract_resume_sections(os.path.join(app.config['UPLOAD_FOLDER'], resume.filename))

        # Script para adaptar o currículo
        prompt_script = (
            f"I need you to taylorize my recent experience to a vacancy I want to apply for. You are allowed to change the order of the experiences to have the most relevant first, "
            f"remove items that don't add to the role and add experiences that are already there. Let me know what is missing and what you have removed (if you did). "
            f"Keep in mind that for my current role the bullets need to start with present continuous and the past ones with past perfect.\n\n"
            f"---\n\n"
            f"Summary:\n{summary_text}\n\nProfessional Experience:\n{experience_text}\n\nJob Description:\n{job_description}"
        )

        # Envia a solicitação à API do ChatGPT para adaptar o currículo
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "You are a resume adaptation assistant."},
                      {"role": "user", "content": prompt_script}],
            max_tokens=1500,
            temperature=0.7,
        )

        adapted_resume_text = response.choices[0].message['content']

        # Armazena o currículo adaptado no banco de dados
        resume.adapted_content = adapted_resume_text
        db.session.commit()  # Salva a alteração no banco

        # Armazena o currículo adaptado na sessão
        session['adapted_resume_text'] = adapted_resume_text

        # Exibir o currículo adaptado em uma pré-visualização
        return render_template('preview_resume.html', adapted_resume=adapted_resume_text)

    # Para o método GET, renderize o formulário com o currículo
    return render_template('adapt_resume.html', resume=resume)

@app.route('/download_adapted_resume/<int:resume_id>', methods=['POST'])
@login_required
def download_adapted_resume(resume_id):
    adapted_resume_text = session.get('adapted_resume_text')
    if not adapted_resume_text:
        flash("No adapted resume found.")
        return redirect(url_for('dashboard'))

    # Cria um PDF com o conteúdo adaptado
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, adapted_resume_text)

    # Salva o PDF temporariamente e envia para download
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f"adapted_resume_{resume_id}.pdf")
    pdf.output(pdf_path)

    return send_from_directory(app.config['UPLOAD_FOLDER'], f"adapted_resume_{resume_id}.pdf", as_attachment=True)

@app.route('/view_resumes', methods=['GET'])
@login_required
def view_resumes():
    resumes = Resume.query.filter_by(user_id=current_user.id).all()
    return render_template('view_resumes.html', resumes=resumes)


if __name__ == '__main__':
    app.run(debug=True)
