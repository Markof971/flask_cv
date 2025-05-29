import os
import json
import uuid
import shutil
import subprocess
import re
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_file, flash
)
from jinja2 import Environment, FileSystemLoader, select_autoescape
import openai

# Import libraries for CV parsing
import docx
from pdfminer.high_level import extract_text
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

# Download NLTK data if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# ---------------------------------------------------------------------------
#  Configuration
# ---------------------------------------------------------------------------
openai.api_key = os.getenv("OPENAI_API_KEY","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")  # clé éventuelle pour la post‑édition GPT
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "o3")

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET", "change_me"),
    UPLOAD_FOLDER=BASE_DIR / "static" / "uploads",
    OUTPUT_FOLDER=BASE_DIR / "generated",
)

# ---------------------------------------------------------------------------
#  Templates catalogue -------------------------------------------------------
# ---------------------------------------------------------------------------
with open(BASE_DIR / "config.json", encoding="utf-8") as fh:
    CV_TEMPLATES = json.load(fh)

def get_template_meta(template_id: str):
    return next((t for t in CV_TEMPLATES if t["id"] == template_id), None)

# ---------------------------------------------------------------------------
#  Helpers : schema / form / latex ------------------------------------------
# ---------------------------------------------------------------------------

def load_schema(template_meta: dict) -> dict:
    """Charge le schema.json placé à côté de main.tex."""
    schema_path = Path(template_meta["latex_path"]).with_name("schema.json")
    if not schema_path.exists():
        raise FileNotFoundError(f"schema.json manquant pour le modèle {template_meta['id']}")
    with open(schema_path, encoding="utf-8") as fh:
        return json.load(fh)


def parse_form_data(schema: dict, form, files) -> dict:
    """Transforme request.form / files en un dict prêt pour Jinja2."""
    data = {}

    for section in schema["sections"]:
        for field in section["fields"]:
            fid = field["id"]
            ftype = field.get("type", "text")

            # Fichiers -------------------------------------------------------
            if ftype == "file":
                fobj = files.get(fid)
                if fobj and fobj.filename:
                    ext = Path(fobj.filename).suffix
                    dest_name = f"{uuid.uuid4().hex}{ext}"
                    dest_path = app.config["UPLOAD_FOLDER"] / dest_name
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    fobj.save(dest_path)
                    data[fid] = dest_name  # chemin relatif
                else:
                    data[fid] = ""
                continue

            # Tableaux (array) ----------------------------------------------
            if ftype == "array":
                pattern = re.compile(fr"{re.escape(fid)}\[(\d+)]\[(\w+)]")
                rows = {}
                for key, val in form.items():
                    m = pattern.fullmatch(key)
                    if m:
                        idx, sub = m.groups()
                        rows.setdefault(int(idx), {})[sub] = val
                data[fid] = [rows[k] for k in sorted(rows)]
            else:
                data[fid] = form.get(fid, "")

    return data


def render_latex(template_meta: dict, data: dict) -> str:
    """Rend le main.tex Jinja2 avec les données collectées."""
    tpl_path = Path(template_meta["latex_path"])
    env = Environment(
    loader=FileSystemLoader(tpl_path.parent),
    autoescape=select_autoescape([]),

    block_start_string='{%', block_end_string='%}',
    variable_start_string='{{', variable_end_string='}}',

    # empêche le conflit {# … #}
    comment_start_string='((#',   # n'apparaîtra jamais dans votre LaTeX
    comment_end_string='#))'
)

    template = env.get_template(tpl_path.name)
    return template.render(**data)


def copy_template_dir(template_meta: dict) -> Path:
    """Copie récursivement tout le dossier du template vers /generated/<uid>."""
    src_dir = Path(template_meta["latex_path"]).parent
    build_dir = app.config["OUTPUT_FOLDER"] / uuid.uuid4().hex
    shutil.copytree(src_dir, build_dir)
    return build_dir


def compile_pdf(tex_source: str, build_dir: Path, tex_name: str = "main.tex") -> Path:
    """Écrit le LaTeX dans build_dir, lance pdflatex, renvoie le path PDF."""
    tex_file = build_dir / tex_name
    tex_file.write_text(tex_source, encoding="utf-8")
    subprocess.run([
        "pdflatex", "-interaction=nonstopmode", tex_file.name
    ], cwd=build_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return build_dir / f"{tex_file.stem}.pdf"

# ---------------------------------------------------------------------------
#  CV Import Functions ------------------------------------------------------
# ---------------------------------------------------------------------------

def extract_text_from_docx(file_path):
    """Extract text from a DOCX file."""
    doc = docx.Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

def extract_text_from_pdf(file_path):
    """Extract text from a PDF file."""
    return extract_text(file_path)

def extract_cv_data(file_path, file_ext):
    """Extract CV data from a file based on its extension."""
    if file_ext.lower() == '.docx':
        text = extract_text_from_docx(file_path)
    elif file_ext.lower() == '.pdf':
        text = extract_text_from_pdf(file_path)
    else:
        raise ValueError(f"Unsupported file extension: {file_ext}")
    
    # Use GPT to extract structured data from the CV text
    return gpt_extract_cv_data(text)

def gpt_extract_cv_data(cv_text):
    """Use GPT to extract structured data from CV text."""
    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY required for CV data extraction")
    
    system_prompt = """
    You are a CV/resume parser. Extract structured information from the provided CV text.
    Identify the following information:
    - Personal details (name, email, phone, address)
    - Professional summary/profile
    - Work experience (job titles, companies, dates, descriptions)
    - Education (degrees, institutions, dates)
    - Skills
    - Languages
    - Certifications
    - Personal information (citizenship, family status)
    - Hobbies/interests
    
    Format your response as a JSON object with these fields. If information is not found, use empty strings or arrays.
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": cv_text}
    ]
    
    try:
        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3
        )
        
        result = response.choices[0].message.content.strip()
        # Clean up the response to ensure it's valid JSON
        result = re.sub(r"```json|```", "", result).strip()
        
        try:
            parsed_data = json.loads(result)
            return map_gpt_data_to_schema(parsed_data)
        except json.JSONDecodeError as e:
            print(f"Error parsing GPT response: {e}")
            print(f"Response was: {result}")
            return {}
            
    except Exception as e:
        print(f"Error calling GPT API: {e}")
        return {}

def map_gpt_data_to_schema(gpt_data):
    """Map GPT extracted data to our schema format."""
    mapped_data = {}
    
    # Map basic fields
    if 'name' in gpt_data:
        name_parts = gpt_data['name'].split(maxsplit=1)
        if len(name_parts) > 0:
            mapped_data['first_name'] = name_parts[0]
        if len(name_parts) > 1:
            mapped_data['last_name'] = name_parts[1]
    
    # Map contact info
    mapped_data['email'] = gpt_data.get('email', '')
    mapped_data['phone'] = gpt_data.get('phone', '')
    mapped_data['address'] = gpt_data.get('address', '')
    
    # Map profile summary
    mapped_data['profile_summary'] = gpt_data.get('summary', '')
    
    # Map personal info
    mapped_data['citizenship'] = gpt_data.get('citizenship', '')
    mapped_data['family'] = gpt_data.get('family_status', '')
    mapped_data['languages'] = gpt_data.get('languages', '')
    
    # Map skills
    if 'skills' in gpt_data:
        if isinstance(gpt_data['skills'], list):
            mapped_data['skills'] = '\n'.join(gpt_data['skills'])
        else:
            mapped_data['skills'] = gpt_data['skills']
    
    # Map work experience
    if 'experience' in gpt_data and isinstance(gpt_data['experience'], list):
        mapped_data['jobs'] = []
        for exp in gpt_data['experience']:
            job = {
                'title': exp.get('title', ''),
                'company': exp.get('company', ''),
                'location': exp.get('location', ''),
                'start_date': exp.get('start_date', ''),
                'end_date': exp.get('end_date', ''),
                'bullets': '\n'.join(exp.get('description', [])) if isinstance(exp.get('description', []), list) else exp.get('description', '')
            }
            mapped_data['jobs'].append(job)
    
    # Map education
    if 'education' in gpt_data and isinstance(gpt_data['education'], list):
        mapped_data['degrees'] = []
        for edu in gpt_data['education']:
            degree = {
                'degree': edu.get('degree', ''),
                'institution': edu.get('institution', ''),
                'dates': f"{edu.get('start_date', '')}–{edu.get('end_date', '')}"
            }
            mapped_data['degrees'].append(degree)
    
    # Map certifications
    if 'certifications' in gpt_data and isinstance(gpt_data['certifications'], list):
        mapped_data['certifications'] = []
        for cert in gpt_data['certifications']:
            certification = {
                'title': cert.get('title', ''),
                'issuer': cert.get('issuer', ''),
                'date': cert.get('date', '')
            }
            mapped_data['certifications'].append(certification)
    
    # Map hobbies
    mapped_data['hobbies'] = gpt_data.get('hobbies', '')
    
    return mapped_data

# ---------------------------------------------------------------------------
#  Routes -------------------------------------------------------------------
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", templates=CV_TEMPLATES)


@app.route("/select/<template_id>")
def select_template(template_id):
    if not get_template_meta(template_id):
        flash("Modèle invalide", "danger")
        return redirect(url_for("index"))
    session.clear()
    session["template_id"] = template_id
    return redirect(url_for("form"))


@app.route("/form", methods=["GET", "POST"])
def form():
    if "template_id" not in session:
        return redirect(url_for("index"))

    template_meta = get_template_meta(session["template_id"])

    # Charge le schéma une seule fois
    if "form_schema" not in session:
        session["form_schema"] = load_schema(template_meta)
    schema = session["form_schema"]

    # Soumission
    if request.method == "POST":
        data = parse_form_data(schema, request.form, request.files)
        session["cv_data"] = data
        return redirect(url_for("preview"))

    # Affichage du formulaire avec les données pré-remplies si disponibles
    return render_template("form_schema.html", schema=schema, data=session.get("cv_data"))


@app.route("/import", methods=["GET", "POST"])
def import_cv():
    if "template_id" not in session:
        return redirect(url_for("index"))
    
    if request.method == "POST":
        if 'cv_file' not in request.files:
            flash("Aucun fichier sélectionné", "danger")
            return redirect(url_for("import_cv"))
        
        cv_file = request.files['cv_file']
        if cv_file.filename == '':
            flash("Aucun fichier sélectionné", "danger")
            return redirect(url_for("import_cv"))
        
        # Save the uploaded file
        file_ext = os.path.splitext(cv_file.filename)[1]
        if file_ext.lower() not in ['.docx', '.pdf']:
            flash("Format de fichier non supporté. Veuillez télécharger un fichier DOCX ou PDF.", "danger")
            return redirect(url_for("import_cv"))
        
        temp_file_path = os.path.join(app.config["UPLOAD_FOLDER"], f"temp_{uuid.uuid4().hex}{file_ext}")
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        cv_file.save(temp_file_path)
        
        try:
            # Extract data from the CV
            extracted_data = extract_cv_data(temp_file_path, file_ext)
            
            # Store the extracted data in session
            session["cv_data"] = extracted_data
            
            # Clean up the temporary file
            os.remove(temp_file_path)
            
            flash("Données extraites avec succès! Veuillez vérifier et compléter si nécessaire.", "success")
            return redirect(url_for("form"))
            
        except Exception as e:
            flash(f"Erreur lors de l'extraction des données: {str(e)}", "danger")
            return redirect(url_for("import_cv"))
    
    return render_template("import.html")


@app.route("/preview")
def preview():
    if "cv_data" not in session:
        return redirect(url_for("form"))

    template_meta = get_template_meta(session["template_id"])

    # 1. Rendu Jinja2 → LaTeX
    filled_tex = render_latex(template_meta, session["cv_data"])
    session["last_tex"] = filled_tex  # pour une éventuelle post‑édition GPT

    # 2. Build directory & compilation
    build_dir = copy_template_dir(template_meta)
    pdf_path = compile_pdf(filled_tex, build_dir)

    # 3. Stocke le PDF relatif pour l'affichage / téléchargement
    rel_pdf = pdf_path.relative_to(app.config["OUTPUT_FOLDER"])
    session["pdf_filename"] = str(rel_pdf)

    return render_template("preview.html", pdf_filename=rel_pdf)


@app.route("/file/<path:filename>")
def file(filename):
    return send_file(app.config["OUTPUT_FOLDER"] / filename)


@app.route("/download")
def download():
    if "pdf_filename" not in session:
        return redirect(url_for("form"))
    return send_file(app.config["OUTPUT_FOLDER"] / session["pdf_filename"], as_attachment=True)

# ---------------------------------------------------------------------------
#  (Facultatif) édition libre via GPT ---------------------------------------
# ---------------------------------------------------------------------------

def gpt_edit_latex(current_tex: str, prompt: str) -> str:
    """Renvoie une nouvelle version LaTeX modifiée selon 'prompt'."""
    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY requis pour l'édition GPT")

    system = (
        "Tu es un expert LaTeX. On te donne un CV et une instruction. "
        "Retourne uniquement le code LaTeX final, sans explication."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"CV actuel :\n---\n{current_tex}\n---\nInstruction : {prompt}"}
    ]
    resp = openai.ChatCompletion.create(model=OPENAI_MODEL, messages=messages)
    updated = re.sub(r"^```.*?\n|\n?```$", "", resp.choices[0].message.content.strip(), flags=re.S)
    return updated


@app.route("/edit", methods=["POST"])
def edit():
    if "last_tex" not in session:
        flash("Aucun CV à modifier", "warning")
        return redirect(url_for("preview"))

    instruction = request.form.get("instruction", "").strip()
    if not instruction:
        flash("Veuillez saisir une instruction", "warning")
        return redirect(url_for("preview"))

    try:
        new_tex = gpt_edit_latex(session["last_tex"], instruction)
        template_meta = get_template_meta(session["template_id"])
        build_dir = copy_template_dir(template_meta)
        pdf_path = compile_pdf(new_tex, build_dir)

        session["last_tex"] = new_tex
        session["pdf_filename"] = str(pdf_path.relative_to(app.config["OUTPUT_FOLDER"]))
        flash("Modifications appliquées", "success")
    except Exception as exc:
        flash(f"Erreur GPT/LaTeX : {exc}", "danger")

    return redirect(url_for("preview"))

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)