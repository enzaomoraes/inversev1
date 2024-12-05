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
from unidecode import unidecode
import re

openai.api_key = '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'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'vitticalvo'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class PDF(FPDF):
    def header(self):
        pass

    def footer(self):
        pass

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
    
class ResumeAdaptation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey('resume.id'))
    job_description = db.Column(db.Text)
    company_name = db.Column(db.String(150))
    adapted_experience = db.Column(db.Text)
    #missing_info = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    adapted_filename = db.Column(db.Text)
    
    resume = db.relationship('Resume', backref=db.backref('adaptations', lazy=True))

    
if not os.path.exists('database.db'):
    with app.app_context():
        db.create_all()  # Cria as tabelas novamente
    
        inspector = inspect(db.engine)
        print("Tabelas criadas:", inspector.get_table_names())
    

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
        file = request.files.get('file')  # Alterado de ['file'] para .get('file') para evitar KeyError
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

from PyPDF2 import PdfReader

from PyPDF2 import PdfReader

def extract_all_sections(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()

    # Normalize quebras de linha substituindo-as por espaços
    text = ' '.join(text.splitlines()).strip()

    # Encontra dinamicamente seções-chave e extrai conteúdo
    sections = {
        "Summary": "",
        "Professional Experience": "",
        "Education": "",
        "Languages": "",
        "Skills": ""
    }

    # Extração das seções (exceto Skills) e formatação
    for section in sections.keys():
        if section == "Skills":
            continue  # Pulamos a extração da seção "Skills" por enquanto
        
        start_idx = text.lower().find(section.lower())
        next_section_idx = min(
            [text.lower().find(sec.lower(), start_idx + 1) for sec in sections.keys() if text.lower().find(sec.lower(), start_idx + 1) > -1] + [len(text)]
        )
        if start_idx != -1:
            content = text[start_idx:next_section_idx].strip()
            content = content[len(section):].strip()  # Remove o título da seção

            # Formatação específica para a seção de Educação
            if section == "Education":
                # Adiciona uma quebra de linha apenas uma vez após "Degree" e remove quebras de linha extras
                content = content.replace("Degree ", "Degree\n").replace("\n\n", "\n").strip()

            # Formatação para a seção de Idiomas
            elif section == "Languages":
                for fluency in ["Native", "Fluent", "Advanced", "Intermediate", "Basic"]:
                    content = content.replace(fluency, f"{fluency}\n")

            sections[section] = content.strip()

# Captura da seção "Skills" (última seção)
        skills_start = text.lower().find("skills")
        if skills_start != -1:
    # Encontra o início da seção "Skills", mas sem a palavra "Skills" na captura
            skills_content = text[skills_start:].strip()
    
    # Remove a palavra "Skills" (e o possível espaço após ela)
            skills_content = skills_content.replace("Skills", "").strip()
    
    # Atribui o conteúdo da seção "Skills" sem a palavra "Skills"
            sections["Skills"] = skills_content


    return sections


import re

def extract_personal_info(text):
    # Regex para capturar o nome e informações pessoais
    name_pattern = r"^([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+){0,3})"
    email_pattern = r"([\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,})"
    phone_pattern = r"(\+?\d{2}\s*\(?\d{2}\)?\s*\d{4,5}-?\d{4})"
    linkedin_pattern = r"(https?://[^\s]+)"
    address_pattern = r"(Rua|Rodovia|Avenida|Travessa|Praça|Alameda)\s+.+?-\s*[A-Z]{2}"

    # Limpeza do texto
    text = text.replace("\n", " ").replace("\r", "").strip()

    # Depuração: verifique o texto completo
    print("Texto extraído do PDF:")
    print(text)

    # Usando a regex para capturar informações
    name = re.search(name_pattern, text, re.MULTILINE)
    email = re.search(email_pattern, text)
    phone = re.search(phone_pattern, text)
    linkedin = re.search(linkedin_pattern, text)
    address = re.search(address_pattern, text)

    # Depuração: cheque o que foi encontrado
    if address:
        print("Endereço capturado:", address.group(0))
    else:
        print("Padrão de endereço não encontrado!")

    # Processando o nome para garantir que tenha espaços entre as partes
    full_name = name.group(1).strip() if name else "Nome não encontrado"
    full_name = ' '.join(full_name.split())

    # Processando o endereço para garantir espaços
    full_address = address.group(0).strip() if address else "Endereço não encontrado"

    return {
        "name": full_name,
        "email": email.group(0) if email else "Email não encontrado",
        "phone": phone.group(0) if phone else "Telefone não encontrado",
        "linkedin": linkedin.group(0) if linkedin else "LinkedIn não encontrado",
        "address": full_address
    }


def add_section(pdf, title, content, title_font_size=13, content_font_size=11, is_bold=False):
    # Adicionar título com sublinhado para cabeçalhos de seção
    pdf.set_font("Arial", "B" if is_bold else "", size=title_font_size)
    pdf.cell(0, 8, title, ln=True, border="B")  # Título sublinhado
    pdf.ln(3)  # Espaço reduzido após o título

    # Configurar fonte para conteúdo
    pdf.set_font("Arial", "", size=content_font_size)
    for paragraph in content.split('\n\n'): 
        pdf.multi_cell(0, 5, paragraph)  # Espaçamento de linha reduzido
        pdf.ln(2)  # Espaço reduzido entre os parágrafos

def add_languages_section(pdf, languages_content):
    pdf.set_font("Arial", "B", size=13)
    pdf.cell(0, 8, "LANGUAGES", ln=True, border="B")
    pdf.ln(3)  # Espaço reduzido após o título

    for line in languages_content.split('\n'):
        if ":" in line:
            language, fluency = line.split(":", 1)
            pdf.set_font("Arial", "B", size=11)
            pdf.cell(25, 6, f"{language.strip()}:", align="L")  # Reduzindo a altura da célula
            pdf.set_font("Arial", "", size=11)
            pdf.cell(0, 6, fluency.strip(), ln=True, align="L")  # Fluência na mesma linha
        pdf.ln(2)  # Espaço reduzido entre as linhas

def add_professional_experience_section(pdf, experience_content):
    pdf.set_font("Arial", "B", size=13)
    pdf.cell(0, 8, "PROFESSIONAL EXPERIENCE", ln=True, border="B")
    pdf.ln(3)  # Espaço reduzido após o título

    previous_line_has_period = False  # Flag para verificar se a linha anterior termina com ponto
    first_line_after_date = True  # Flag para garantir que a primeira linha após uma data tenha um ponto de bala

    # Caminho para a imagem do ponto de bala
    bullet_image_path = 'static/bullet.png'  # Substitua com o caminho correto
    bullet_image_width = 4  # Largura da imagem do ponto de bala
    bullet_image_height = 4  # Altura da imagem do ponto de bala
    offset_x = 6  # Ajuste esse valor para mover as linhas sem pontos de bala para a direita

    # Divida o conteúdo em linhas
    for line in experience_content.split('\n'):
        line = line.strip()
        if line:
            # Trata a linha com informações de data e empresa na mesma linha
            if any(char.isdigit() for char in line):  # Detecta se contém alguma data
                # Encontra a posição do parêntese, onde a data começa
                parenthesis_pos = line.find('(')
                if parenthesis_pos != -1:
                    # Quebra a linha no parêntese (onde começa a data)
                    line_part1 = line[:parenthesis_pos].strip()
                    line_part2 = line[parenthesis_pos:].strip()
                    
                    # Adiciona a primeira parte (empresa) da linha
                    pdf.set_font("Arial", "B", size=10)
                    pdf.cell(0, 6, line_part1, ln=True)
                    
                    # Adiciona a segunda parte (data) da linha
                    pdf.set_font("Arial", "", size=10)
                    pdf.cell(0, 6, line_part2, ln=True)
                    
                    previous_line_has_period = False
                    first_line_after_date = True
                else:
                    # Se não houver parêntese, trata a linha inteira
                    pdf.set_font("Arial", "B", size=10)
                    pdf.cell(0, 6, line, ln=True)
                    previous_line_has_period = False
                    first_line_after_date = True
            else:
                pdf.set_font("Arial", "", size=10)

                # Se for a primeira linha após uma data, adicionar um ponto de bala
                if first_line_after_date:
                    x = pdf.get_x()
                    y = pdf.get_y()
                    pdf.image(bullet_image_path, x=x, y=y, w=bullet_image_width, h=bullet_image_height)
                    pdf.set_x(x + bullet_image_width + 2)  # Move o cursor para a direita da imagem do ponto de bala
                    pdf.multi_cell(0, 4, line, align='L')
                    first_line_after_date = False
                else:
                    if previous_line_has_period:
                        x = pdf.get_x()
                        y = pdf.get_y()
                        pdf.image(bullet_image_path, x=x, y=y, w=bullet_image_width, h=bullet_image_height)
                        pdf.set_x(x + bullet_image_width + 2)
                        pdf.multi_cell(0, 4, line, align='L')
                    else:
                        # Linha sem ponto de bala, mover para a direita
                        pdf.set_x(pdf.get_x() + offset_x)
                        pdf.multi_cell(0, 4, line, align='L')
                        pdf.set_x(pdf.get_x() - offset_x)

                previous_line_has_period = line.endswith(".")

        pdf.ln(2)  # Espaço reduzido entre as entradas de experiência



def add_education_section(pdf, education_content):
    # Função personalizada para formatar a seção de Educação com instituição e grau em negrito
    pdf.set_font("Arial", "B", size=13)
    pdf.cell(0, 8, "EDUCATION", ln=True, border="B")
    pdf.ln(3)  # Espaço reduzido após o título

    for line in education_content.split('\n'):
        # Verifica se há uma linha com a palavra "Degree" para separar instituição e grau
        if "Degree" in line:
            parts = line.split("Degree", 1)  # Divide a linha antes e depois da palavra "Degree"
            if len(parts) > 1:
                institution = parts[0].strip()
                degree = parts[1].strip()
                pdf.set_font("Arial", "B", size=11)
                pdf.cell(0, 6, f"{institution} - Degree", ln=True)  # Linha com o nome da instituição em negrito
                pdf.set_font("Arial", "", size=11)
                pdf.multi_cell(0, 6, degree)  # Linha com o grau de estudo
        else:
            pdf.multi_cell(0, 6, line)  # Linha sem "Degree" trata-se apenas de uma linha de educação
        pdf.ln(1)  # Espaço reduzido entre as entradas de educação

def add_skills_section(pdf, skills_content):
    # Título da seção "Skills"
    pdf.set_font("Arial", "B", size=13)
    pdf.cell(0, 8, "SKILLS", ln=True, border="B")
    pdf.ln(3)  # Espaço após o título

    # Corpo da seção "Skills"
    pdf.set_font("Arial", size=11)

    # Verifica se a variável skills_content contém conteúdo
    if skills_content:
        # Dividimos o conteúdo das habilidades em linhas
        lines = skills_content.split("\n")
        
        for line in lines:
            if ":" in line:
                # Se houver ":", dividimos a linha em título e conteúdo
                title, content = line.split(":", 1)
                
                # Adiciona o título em negrito
                pdf.set_font("Arial", "B", size=11)
                pdf.cell(0, 6, f"{title.strip()}:", ln=True)
                
                # Quebra de linha após o título
                pdf.ln(2)
                
                # Adiciona o conteúdo abaixo, em formato normal
                pdf.set_font("Arial", size=11)
                pdf.multi_cell(0, 6, content.strip(), align='L')
                
                # Quebra de linha entre categorias
                pdf.ln(2)
            else:
                # Se não houver ":", adicionamos a linha normalmente
                pdf.multi_cell(0, 6, line.strip(), align='L')
                
        # Espaço após a seção de skills
        pdf.ln(2)
    
@app.route('/adapt_resume/<string:resume_name>', methods=['GET', 'POST'])
@login_required
def adapt_resume_by_name(resume_name):
    # Buscar o currículo pelo nome no banco de dados
    resume = Resume.query.filter_by(name=resume_name, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        company_name = request.form['company_name']
        job_description = request.form['job_description']

        # Atualizar as informações
        resume.job_description = job_description
        resume.company_name = company_name
        db.session.commit()

        # Extrair as seções do currículo original (do arquivo PDF)
        sections = extract_all_sections(os.path.join(app.config['UPLOAD_FOLDER'], resume.filename))
        print("Skills section content:", repr(sections["Skills"]))  # Verificar a seção de Skills extraída

        # Extrair o texto completo do PDF
        pdf_text = ""
        with open(os.path.join(app.config['UPLOAD_FOLDER'], resume.filename), 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                pdf_text += page.extract_text()

        # Extrair informações pessoais
        personal_info = extract_personal_info(pdf_text)

        # Preparar o prompt para a API do ChatGPT
        prompt_script = (
            f"Please tailor my recent experience to the following job description:\n\n"
            f"{job_description}\n\n"
            f"You are allowed to change the order of the experiences to have the most relevant first, "
            f"remove items that don't add to the role, and add experiences that are already there. "
            f"Keep in mind that for my current role the bullets need to start with present continuous, "
            f"and the past ones with past perfect. "
            f"Please don't write any comments or anything else, just the sections of the tailored resume. "
            f"Please do not use asterisks, or hyphens in any way, neither bullet points, just words and periods, and also do not write anything more than what is asked"
            f"\n{sections['Professional Experience']}\n\n"
            #f"Output format: Please return two distinct sections in your response:\n"
            #f"1. The tailored experience for the job (adapted experience).\n"
            #f"2. The missing information for the role (what is missing in my resume for this job).\n\n"
            #f"Please make sure that these two sections are clearly separated."
        )

        # Chamada à API do ChatGPT
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a resume adaptation assistant."},
                      {"role": "user", "content": prompt_script}],
            max_tokens=1500,
            temperature=0.7,
        )

        # Extrair o conteúdo adaptado da resposta da API
        adapted_content = response['choices'][0]['message']['content']
        
        # Remover ou substituir o caractere '\u2022' (ponto de bala)
        adapted_content = adapted_content.replace('\u2022', '')

        # Inicializar as variáveis com valores padrão
        adapted_experience = adapted_content
        #missing_info = "Error: Could not parse the missing information."

        # Usar expressões regulares para separar as duas partes da resposta
        #pattern = r"1\. The tailored experience for the job \(adapted experience\)\.(.*?)(2\. The missing information for the role \(what is missing in my resume for this job\)\.)"
        #match = re.search(pattern, adapted_content, re.DOTALL)

        #if match:
            #adapted_experience = match.group(1).strip()
            #missing_info = match.group(2).strip()

        # Salvar as partes adaptadas na sessão
        session['adapted_experience'] = adapted_experience
        #session['missing_info'] = missing_info

        # Criar o PDF com as seções formatadas
        ResumeAdaptation.adapted_filename = f"adapted_resume_{resume.id}_{current_user.id}.pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], ResumeAdaptation.adapted_filename)

        # Criando o PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Seção de informações pessoais
        pdf.set_font("Arial", "B", size=21)
        pdf.cell(0, 10, unidecode(personal_info['name']), ln=True)
        pdf.set_font("Arial", "B", size=13.5)
        pdf.cell(0, 8, "(career)", ln=True)

        pdf.set_font("Arial", size=10)
        contact_info = unidecode(f"{personal_info['email']} | {personal_info['phone']} |")
        pdf.cell(pdf.get_string_width(contact_info), 8, contact_info, ln=False)

        # Link do LinkedIn
        pdf.set_text_color(0, 0, 255)
        pdf.write(8, unidecode(personal_info['linkedin']), personal_info['linkedin'])
        pdf.set_text_color(0, 0, 0)
        pdf.ln(6)

        pdf.cell(0, 8, unidecode(f"Brazil | {personal_info['address']}"), ln=True)
        pdf.ln(2)

        # Adicionar seções formatadas
        add_section(pdf, "SUMMARY", sections["Summary"], title_font_size=13, content_font_size=10, is_bold=True)
        add_professional_experience_section(pdf, adapted_experience)
        add_education_section(pdf, sections["Education"])
        add_languages_section(pdf, sections["Languages"])
        add_skills_section(pdf, sections["Skills"])

        # Salvar o PDF gerado
        pdf.output(pdf_path)

        # Registrar a adaptação no banco de dados
        adaptation = ResumeAdaptation(
            resume_id=resume.id,
            job_description=job_description,
            company_name=company_name,
            adapted_experience=adapted_experience,
            #missing_info=missing_info,
            adapted_filename = ResumeAdaptation.adapted_filename,
        )
        db.session.add(adaptation)
        db.session.commit()
        
        return redirect(url_for('preview_resume', adaptation_id=adaptation.id))

    flash(f"Resume '{resume_name}' adapted successfully!")
    return redirect(url_for('dashboard'))


@app.route('/download_adapted_resume/<int:resume_id>', methods=['POST'])
@login_required
def download_adapted_resume(resume_id):
    # Obtém o objeto Resume do banco de dados
    resume = Resume.query.get_or_404(resume_id)
    if not ResumeAdaptation.adapted_filename:
        flash("No adapted resume found.")
        return redirect(url_for('dashboard'))

    # Caminho do arquivo PDF gerado na função adapt_resume
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], ResumeAdaptation.adapted_filename)

    # Verifica se o arquivo existe antes de enviar
    if not os.path.exists(pdf_path):
        flash("Adapted resume file not found.")
        return redirect(url_for('dashboard'))

    return send_from_directory(app.config['UPLOAD_FOLDER'], ResumeAdaptation.adapted_filename, as_attachment=True)

@app.route('/download_adapted_resume_dashboard/<int:resume_id>', methods=['GET'])
@login_required
def download_adapted_resume_dashboard(resume_id):
    # Obtém o objeto Resume do banco de dados
    resume = Resume.query.get_or_404(resume_id)
    if not ResumeAdaptation.adapted_filename:
        flash("No adapted resume available for download.")
        return redirect(url_for('dashboard'))

    # Caminho do arquivo PDF gerado na função adapt_resume
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], ResumeAdaptation.adapted_filename)

    # Verifica se o arquivo existe antes de enviar
    if not os.path.exists(pdf_path):
        flash("Adapted resume file not found.")
        return redirect(url_for('dashboard'))

    return send_from_directory(app.config['UPLOAD_FOLDER'], ResumeAdaptation.adapted_filename, as_attachment=True)

@app.route('/view_resumes', methods=['GET'])
@login_required
def view_resumes():
    resumes = Resume.query.filter_by(user_id=current_user.id).all()
    return render_template('view_resumes.html', resumes=resumes)

@app.route('/show_missing_info/<int:resume_id>/<int:adaptation_id>', methods=['GET'])
@login_required
def show_missing_info(resume_id, adaptation_id):
    resume = Resume.query.get_or_404(resume_id)
    adaptation = ResumeAdaptation.query.get_or_404(adaptation_id)
    
    # Passa as informações para o template
    return render_template('show_missing_info.html', 
                           resume_name=resume.name,
                           company_name=adaptation.company_name,
                           job_description=adaptation.job_description,
                           adapted_experience=adaptation.adapted_experience,
                           missing_info=adaptation.missing_info)
    
@app.route('/preview_resume/<int:adaptation_id>')
@login_required
def preview_resume(adaptation_id):
    adaptation = ResumeAdaptation.query.get_or_404(adaptation_id)

    # Verifica se a adaptação pertence ao usuário
    if adaptation.resume.user_id != current_user.id:
        flash("Você não tem permissão para visualizar esta adaptação.")
        return redirect(url_for('dashboard'))

    # Extrair o conteúdo adaptado da adaptação (que já foi salvo no banco de dados)
    adapted_experience = adaptation.adapted_experience  # A variável já está armazenada em ResumeAdaptation

    return render_template('preview_resume.html', adapted_experience=adapted_experience, adaptation=adaptation)

@app.route('/download_model_resume')
def download_model_resume():
    # Caminho para o arquivo do currículo modelo
    model_resume_path = os.path.join(app.root_path, 'static', 'modelresume.pdf')
    
    # Verifica se o arquivo existe e, em caso afirmativo, serve o arquivo
    if os.path.exists(model_resume_path):
        return send_from_directory(os.path.dirname(model_resume_path), os.path.basename(model_resume_path), as_attachment=True)
    else:
        # Se o arquivo não for encontrado, exibe uma mensagem de erro
        return "Model resume not found", 404


if __name__ == '__main__':
    app.run(debug=True)
