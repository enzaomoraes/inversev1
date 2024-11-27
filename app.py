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
from pdf2image import convert_from_path

openai.api_key = os.getenv('OPENAI_API_KEY')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'vitticalvo'
app.config['SQLALCHEMY_DATABASE_URI'] = 'database.db'
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
    adapted_filename = db.Column(db.Text)
    
    
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
    
    for section in sections.keys():
        start_idx = text.lower().find(section.lower())
        next_section_idx = min(
            [text.lower().find(sec.lower(), start_idx + 1) for sec in sections.keys() if text.lower().find(sec.lower(), start_idx + 1) > -1] + [len(text)]
        )
        if start_idx != -1:
            content = text[start_idx:next_section_idx].strip()
            content = content[len(section):].strip()  # Remove o título da seção
            
            # Formatação específica para a seção de Educação
            if section == "Education":
                content = content.replace("Degree", "Degree\n")
                lines = content.split('\n')
                formatted_content = []
                for i in range(0, len(lines), 2):
                    if i + 1 < len(lines):
                        # Combina o nome da faculdade e o curso em uma linha formatada
                        formatted_line = f"{lines[i].strip():<40} {lines[i+1].strip()}"
                        formatted_content.append(formatted_line)
                    else:
                        # Adiciona linha sem par se houver
                        formatted_content.append(lines[i].strip())
                content = '\n'.join(formatted_content)

            # Formatação para a seção de Idiomas
            elif section == "Languages":
                for fluency in ["Native", "Fluent", "Advanced", "Intermediate", "Basic"]:
                    content = content.replace(fluency, f"{fluency}\n")
                    
            # Formatação específica para a seção de Education
            if section == "Education":
                # Adiciona uma quebra de linha apenas uma vez após "Degree" e remove quebras de linha extras
                content = content.replace("Degree ", "Degree\n").replace("\n\n", "\n").strip()
            
        elif section == "Skills":
    # Procura pelo início da seção "Skills" de forma insensível a maiúsculas/minúsculas
            skills_start = content.lower().find("skills")
            if skills_start != -1:
        # Captura tudo a partir de "Skills" até o final do texto
                skills_content = content[skills_start:].strip()

        # Separa as categorias por linhas e remove espaços extras
                formatted_skills = []
                for line in skills_content.splitlines():
                    line = line.strip()
                    if line and ":" in line:  # Verifica se a linha contém uma categoria
                        category, skills = line.split(":", 1)
                # Formata: Categoria em negrito e habilidades separadas por vírgulas
                    formatted_skills.append(f"{category.strip()}: {skills.strip()}")

        # Junta as categorias formatadas com quebras de linha
            content = '\n'.join(formatted_skills)


            
        sections[section] = content.strip()

    return sections




def extract_personal_info(text):
    # Regex para capturar o nome e informações pessoais
    name_pattern = r"^([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+){0,3})"
    email_pattern = r"([\w\.-]+@[\w\.-]+)"
    phone_pattern = r"(\+?\d{2}\s*\(?\d{2}\)?\s*\d{4,5}-?\d{4})"
    linkedin_pattern = r"(https?://[^\s]+)"
    address_pattern = r"([A-Za-zÀ-ÿ\s]+,\s*[A-Za-zÀ-ÿ\s]+-\s*[A-Z]{2})"

    # Usando a regex para capturar informações
    name = re.search(name_pattern, text, re.MULTILINE)
    email = re.search(email_pattern, text)
    phone = re.search(phone_pattern, text)
    linkedin = re.search(linkedin_pattern, text)
    address = re.search(address_pattern, text)

    # Processando o nome para garantir que tenha espaços entre as partes
    full_name = name.group(1).strip() if name else "Nome não encontrado"
    full_name = ' '.join(full_name.split())

    # Processando o endereço para remover "Brazil" e garantir espaços
    full_address = address.group(0).replace("Brazil", "").strip() if address else "Endereço não encontrado"
    full_address = ' '.join(full_address.split())

    return {
        "name": full_name,
        "email": email.group(0) if email else "Email não encontrado",
        "phone": phone.group(0) if phone else "Telefone não encontrado",
        "linkedin": linkedin.group(0) if linkedin else "LinkedIn não encontrado",
        "address": full_address
    }


def add_section(pdf, title, content, title_font_size=13, content_font_size=11, is_bold=False):
    # Add the title with underline for section headers
    pdf.set_font("Arial", "B" if is_bold else "", size=title_font_size)
    pdf.cell(0, 8, unidecode(title), ln=True, border="B")  # Underlined title
    pdf.ln(3)  # Reduced space after the title

    # Set font for content
    pdf.set_font("Arial", "", size=content_font_size)
    for paragraph in content.split('\n\n'): 
        pdf.multi_cell(0, 5, unidecode(paragraph))  # Reduced line spacing
        pdf.ln(2)  # Reduced space between paragraphs
        
def add_languages_section(pdf, languages_content):
    pdf.set_font("Arial", "B", size=13)
    pdf.cell(0, 8, "LANGUAGES", ln=True, border="B")
    pdf.ln(3)  # Reduced space after the title

    for line in languages_content.split('\n'):
        if ":" in line:
            language, fluency = line.split(":", 1)
            pdf.set_font("Arial", "B", size=11)
            pdf.cell(25, 6, f"{language.strip()}:", align="L")  # Reduced cell height
            pdf.set_font("Arial", "", size=11)
            pdf.cell(0, 6, fluency.strip(), ln=True, align="L")  # Fluency on the same line
        pdf.ln(2)  # Reduced space between lines
        
def add_professional_experience_section(pdf, experience_content):
    pdf.set_font("Arial", "B", size=13)
    pdf.cell(0, 8, "PROFESSIONAL EXPERIENCE", ln=True, border="B")
    pdf.ln(3)  # Reduced space after the title

    previous_line_has_period = False  # Flag to check if the previous line ends with a period
    first_line_after_date = True  # Flag to ensure the first line after a date has a bullet point

    # Path to the bullet point image
    bullet_image_path = 'C:/inverserecruiter/uploads/bullet.png'  # Replace with the actual path to your .png image
    bullet_image_width = 4  # Width of the bullet point image
    bullet_image_height = 4  # Height of the bullet point image
    offset_x = 6  # Adjust this value to shift the lines without bullet points to the right

    # Divide the content into lines
    for line in experience_content.split('\n'):
        line = line.strip()
        if line:
            if "-" in line and any(char.isdigit() for char in line):  # Detect date lines
                pdf.set_font("Arial", "B", size=10)
                pdf.cell(0, 6, line, ln=True)  # Reduced line height for date lines
                previous_line_has_period = False
                first_line_after_date = True
            elif "Brazil" in line or "On-site" in line or "Remote" in line:
                pdf.set_font("Arial", "B", size=10)
                pdf.cell(0, 6, line, ln=True)  # Reduced line height for job and location
                previous_line_has_period = False
                first_line_after_date = True
            else:
                pdf.set_font("Arial", "", size=10)

                # If it's the first line after a date, add a bullet point image
                if first_line_after_date:
                    x = pdf.get_x()
                    y = pdf.get_y()
                    pdf.image(bullet_image_path, x=x, y=y, w=bullet_image_width, h=bullet_image_height)
                    pdf.set_x(x + bullet_image_width + 2)  # Move the cursor to the right of the bullet image
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
                        # Line without bullet point, move to the right
                        pdf.set_x(pdf.get_x() + offset_x)
                        pdf.multi_cell(0, 4, line, align='L')
                        pdf.set_x(pdf.get_x() - offset_x)

                previous_line_has_period = line.endswith(".")

        pdf.ln(2)  # Reduced space between experience entries



def add_education_section(pdf, education_content):
    # Custom function to format the Education section with institution and degree in bold
    pdf.set_font("Arial", "B", size=13)
    pdf.cell(0, 8, "EDUCATION", ln=True, border="B")
    pdf.ln(3)  # Reduced space after the title

    for line in education_content.split('\n'):
        if "Degree" in line:
            institution, degree = line.split("Degree", 1)
            pdf.set_font("Arial", "B", size=11)
            pdf.cell(0, 6, f"{institution.strip()} Degree", ln=True)  # Reduced line height
            pdf.set_font("Arial", "", size=11)
            pdf.multi_cell(0, 6, degree.strip())  # Reduced line height for degree content
        else:
            pdf.multi_cell(0, 6, line)  # Reduced line height for other lines
        pdf.ln(1)  # Reduced space between education entries
     
        
def add_skills_section(pdf, skills_content):
    # Custom function to format the Skills section with skills in bold
    pdf.set_font("Arial", "B", size=13)
    pdf.cell(0, 8, "SKILLS", ln=True, border="B")
    pdf.ln(3)  # Reduced space after the title

    for skill in skills_content.split('\n'):
        pdf.set_font("Arial", "B", size=11)
        pdf.multi_cell(0, 6, unidecode(skill.strip()))  # Reduced line height
    pdf.ln(2)  # Reduced space between skill entries

    
            


@app.route('/adapt_resume/<int:resume_id>', methods=['GET', 'POST'])
@login_required
def adapt_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        flash("Você não tem permissão para adaptar este currículo.")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        job_description = request.form['job_description']

        # Extrai as seções do currículo original
        sections = extract_all_sections(os.path.join(app.config['UPLOAD_FOLDER'], resume.filename))
        
        pdf_text = ""
        with open(os.path.join(app.config['UPLOAD_FOLDER'], resume.filename), 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                pdf_text += page.extract_text()  # Coleta todo o texto

        personal_info = extract_personal_info(pdf_text)

        # Prompt para o ChatGPT
        prompt_script = (
            f"Please tailor my recent experience to the following job description:\n\n"
            f"{job_description}\n\n"
            f"You are allowed to change the order of the experiences to have the most relevant first, "
            f"remove items that don't add to the role, and add experiences that are already there. "
            f"Let me know what is missing and what you have removed (if you did). "
            f"Keep in mind that for my current role the bullets need to start with present continuous, "
            f"and the past ones with past perfect. "
            f"Please don't write any comments or anything else, just the sections of the tailored resume. "
            f"Use the other sections provided below and integrate them into the adapted resume.\n\n"
            f"Professional Experience\n{sections['Professional Experience']}\n\n"
        )

        # Chamada para a API do ChatGPT
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a resume adaptation assistant."},
                {"role": "user", "content": prompt_script}
            ],
            max_tokens=1500,
            temperature=0.7,
        )

        # Extrai o conteúdo adaptado da resposta da API
        adapted_content = response['choices'][0]['message']['content']

        # Salvar o conteúdo adaptado na sessão
        session['adapted_resume_text'] = adapted_content

        # Criação do PDF com formatação por seção conforme solicitado
        adapted_filename = f"adapted_resume_{resume.id}_{current_user.id}.pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], adapted_filename)

        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

# Add Personal Info Section with specific styling
        pdf.set_font("Arial", "B", size=21)
        pdf.cell(0, 10, unidecode(personal_info['name']), ln=True)
        pdf.set_font("Arial", "B", size=13.5)
        pdf.cell(0, 8, "(career)", ln=True)

# Add email, phone, and LinkedIn on the same line
        pdf.set_font("Arial", size=10)
        contact_info = unidecode(f"{personal_info['email']} | {personal_info['phone']} |")
        pdf.cell(pdf.get_string_width(contact_info), 8, contact_info, ln=False)

# Add clickable LinkedIn link in the same line
        pdf.set_text_color(0, 0, 255)  # Set link color to blue
        pdf.write(8, unidecode(personal_info['linkedin']), personal_info['linkedin'])
        pdf.set_text_color(0, 0, 0)  # Reset text color to black
        pdf.ln(6)  # Move to the next line

# Add address on the next line
        pdf.cell(0, 8, unidecode(f"Brazil {personal_info['address']}"), ln=True)
        pdf.ln(2)  # Space after header




        # Add formatted sections
        add_section(pdf, "SUMMARY", sections["Summary"], title_font_size=13, content_font_size=10, is_bold=True)
        add_professional_experience_section(pdf, adapted_content)  # Use o conteúdo adaptado
        add_education_section(pdf, sections["Education"])  # Education com formatação específica
        add_languages_section(pdf, sections["Languages"])  # Languages com formatação específica
        add_skills_section(pdf, sections["Skills"])  # Skills com formatação específica

        # Save the final PDF
        pdf.output(pdf_path)

        # Armazena no banco de dados
        resume.adapted_content = adapted_content
        resume.adapted_filename = adapted_filename
        db.session.commit()

        return render_template('preview_resume.html', adapted_resume=adapted_content, resume=resume)

    return render_template('adapt_resume.html', resume=resume)


@app.route('/download_adapted_resume/<int:resume_id>', methods=['POST'])
@login_required
def download_adapted_resume(resume_id):
    # Obtém o objeto Resume do banco de dados
    resume = Resume.query.get_or_404(resume_id)
    if not resume.adapted_filename:
        flash("No adapted resume found.")
        return redirect(url_for('dashboard'))

    # Caminho do arquivo PDF gerado na função adapt_resume
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], resume.adapted_filename)

    # Verifica se o arquivo existe antes de enviar
    if not os.path.exists(pdf_path):
        flash("Adapted resume file not found.")
        return redirect(url_for('dashboard'))

    return send_from_directory(app.config['UPLOAD_FOLDER'], resume.adapted_filename, as_attachment=True)

@app.route('/download_adapted_resume_dashboard/<int:resume_id>', methods=['GET'])
@login_required
def download_adapted_resume_dashboard(resume_id):
    # Obtém o objeto Resume do banco de dados
    resume = Resume.query.get_or_404(resume_id)
    if not resume.adapted_filename:
        flash("No adapted resume available for download.")
        return redirect(url_for('dashboard'))

    # Caminho do arquivo PDF gerado na função adapt_resume
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], resume.adapted_filename)

    # Verifica se o arquivo existe antes de enviar
    if not os.path.exists(pdf_path):
        flash("Adapted resume file not found.")
        return redirect(url_for('dashboard'))

    return send_from_directory(app.config['UPLOAD_FOLDER'], resume.adapted_filename, as_attachment=True)

@app.route('/view_resumes', methods=['GET'])
@login_required
def view_resumes():
    resumes = Resume.query.filter_by(user_id=current_user.id).all()
    return render_template('view_resumes.html', resumes=resumes)


if __name__ == '__main__':
    app.run(debug=True)
