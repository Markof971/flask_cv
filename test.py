# import os
# import json
# import uuid
# import subprocess
# import openai
# from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
# import re

# # --------- Configuration ----------
# openai.api_key = os.getenv("OPENAI_API_KEY", "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")
# OPENAI_MODEL = os.getenv("OPENAI_MODEL", "o3")

# app = Flask(__name__)
# app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET", 'change_me')
# app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
# app.config['OUTPUT_FOLDER'] = 'generated'

# # Catalogue des templates
# with open('config.json') as f:
#     CV_TEMPLATES = json.load(f)

# # ---------- Utils ----------
# def get_template_meta(template_id):
#     return next((t for t in CV_TEMPLATES if t['id'] == template_id), None)


# import re, json, openai, textwrap

# import textwrap
# import shutil


# def _normalize_schema(raw_dict: dict) -> dict:
#     """
#     Transforme le JSON de GPT (sections comme clés) en :
#     {"sections":[{"title":..., "fields":[{"id":...,"label":...,"type":...}, ...]}, ...]}
#     """
#     # Si GPT a déjà renvoyé la bonne forme, on ne touche pas
#     if "sections" in raw_dict:
#         return raw_dict

#     sections = []
#     for title, content in raw_dict.items():
#         fields = []

#         # content est un dict : clé = id, valeur = {"type": "..."} ou {"type":"array", ...}
#         for fid, meta in content.items():
#             ftype = meta.get("type", "text")
#             field = {"id": fid,
#                      "label": fid.replace('_', ' ').title(),
#                      "type": ftype}

#             # On garde la définition d'item si c'est un tableau
#             if ftype == "array":
#                 field["item"] = meta.get("item", {})

#             fields.append(field)

#         sections.append({"title": title, "fields": fields})

#     return {"sections": sections}
















# # ---------- GPT : extraction structurée ----------
# def gpt_extract_schema(latex_source: str) -> dict:
#     """
#     Analyse le LaTeX et renvoie un JSON :
#     {
#       "sections": [
#         {"title": "...", "fields":[
#             {"id":"...", "label":"...", "type":"text", "required":false},
#             ...
#         ]}
#       ]
#     }
#     """
#     if not openai.api_key:
#         raise RuntimeError("OPENAI_API_KEY manquant")

#     system_prompt = textwrap.dedent("""
#         Tu lis un template LaTeX de CV.
#         Repère toutes les variables (\\VAR{...} ou \\VAR ...).
#         Regroupe-les logiquement par section (\\section, \\subsection ou commentaire % FORM_SECTION:).
#         Types possibles : text, textarea, email, phone, file, date, url.
#         Réponds UNIQUEMENT par un objet JSON SANS ```.
#     """)

#     messages = [
#         {"role": "system", "content": system_prompt},
#         {"role": "user",   "content": latex_source}
#     ]

#     try:
#         resp = openai.ChatCompletion.create(
#             model=OPENAI_MODEL,
#             messages=messages
#         )
#         raw  = resp.choices[0].message.content.strip()
#         print(raw)
#         raw  = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I|re.S).strip()

#         try:
#             raw_dict = json.loads(raw)
#         except Exception as e:
#             print("json.loads a échoué →", e)
#             raw_dict = {}

#         return _normalize_schema(raw_dict)       

#     except Exception as e:
#         print("GPT schema fallback →", e)
#         # plan B : tout en une seule section
#         placeholders = re.findall(r"\\VAR(?:\s*{(\w+)}|\s+(\w+))", latex_source)
#         flat = [p[0] or p[1] for p in placeholders]
#         return {
#             "sections": [{
#                 "title": "Informations",
#                 "fields": [{"id":p, "label":p.replace('_',' ').title(), "type":"text"} for p in flat]
#             }]
#         }
    



# def gpt_fill_latex(latex_source, data_dict):
#     """Remplit le LaTeX via GPT pour gérer les cas complexes (listes, expériences, etc.)."""
#     if not openai.api_key:
#         raise RuntimeError("OPENAI_API_KEY n'est pas défini")
#     prompt = """Voici un template LaTeX de CV. Remplace toutes les variables par les valeurs fournies en JSON.
#     Ne change rien d'autre que ces valeurs. Réponds uniquement avec le LaTeX final.
#     JSON d'entrée :\n""" + json.dumps(data_dict, ensure_ascii=False, indent=2)
#     messages=[{"role":"system","content":"Tu es un assistant LaTeX"},
#               {"role":"user","content": prompt + "\n\nTEMPLATE:\n" + latex_source}]
#     resp=openai.ChatCompletion.create(model=OPENAI_MODEL, messages=messages, temperature=0)
#     return resp.choices[0].message.content

# def compile_pdf(tex_content):
#     build_dir = os.path.join(app.config['OUTPUT_FOLDER'], uuid.uuid4().hex)
#     os.makedirs(build_dir, exist_ok=True)
#     tex_file = os.path.join(build_dir, 'cv.tex')
#     with open(tex_file, 'w', encoding='utf-8') as f:
#         f.write(tex_content)
#     subprocess.run(['pdflatex', '-interaction=nonstopmode', 'cv.tex'],
#                    cwd=build_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     return os.path.join(build_dir, 'cv.pdf')



# import shutil

# def copy_template_dir(template_meta):
#     """Copie tout le dossier du template dans un dossier de build unique."""
#     tmpl_dir = os.path.dirname(template_meta["latex_path"])
#     build_dir = os.path.join(app.config["OUTPUT_FOLDER"], uuid.uuid4().hex)
#     shutil.copytree(tmpl_dir, build_dir)          # <-- copie récursive
#     return build_dir




# # ---------- Routes ----------
# @app.route('/')
# def index():
#     return render_template('index.html', templates=CV_TEMPLATES)

# @app.route('/select/<template_id>')
# def select_template(template_id):
#     meta = get_template_meta(template_id)
#     if not meta:
#         flash('Modèle invalide', 'danger')
#         return redirect(url_for('index'))
#     session.clear()
#     session['template_id'] = template_id
#     return redirect(url_for('form'))




# @app.route('/form', methods=['GET', 'POST'])
# def form():
#     # 1) On vérifie qu’un modèle est bien choisi
#     if 'template_id' not in session:
#         return redirect(url_for('index'))

#     template_meta = get_template_meta(session['template_id'])

#     # 2) On extrait le schéma (sections + champs) UNE SEULE FOIS
#     if 'form_schema' not in session:
#         with open(template_meta['latex_path'], encoding='utf-8') as f:
#             latex_src = f.read()
#         print(latex_src)
#         session['form_schema'] = gpt_extract_schema(latex_src)

#         print(session['form_schema'])

#     schema = session['form_schema']          # dict contenant "sections" → [ {title, fields} ]

#     # 3) Soumission du formulaire -----------------------------------------------------------
#     if request.method == 'POST':
#         data = {}   # dictionnaire de toutes les valeurs envoyées

#         # On parcourt chaque section puis chaque champ
#         for section in schema['sections']:
#             for field in section['fields']:
#                 fid   = field['id']                 # ex: "name"
#                 ftype = field.get('type', 'text')   # ex: "file" | "textarea" | ...

#                 if ftype == 'file':
#                     # Gestion des uploads
#                     fobj = request.files.get(fid)
#                     if fobj and fobj.filename:
#                         ext   = os.path.splitext(fobj.filename)[1]
#                         fname = f"{uuid.uuid4().hex}{ext}"
#                         dest  = os.path.join(app.config['UPLOAD_FOLDER'], fname)
#                         os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
#                         fobj.save(dest)
#                         data[fid] = fname           # on stocke le nom relatif, pas le chemin absolu
#                     else:
#                         data[fid] = ''
#                 else:
#                     data[fid] = request.form.get(fid, '')

#         # On place toutes les infos en session puis on passe à l’aperçu
#         session['cv_data'] = data
#         return redirect(url_for('preview'))

#     # 4) Affichage (GET) --------------------------------------------------------------------
#     return render_template('form_schema.html', schema=schema)


# @app.route('/preview')
# def preview():
#     if 'cv_data' not in session:
#         return redirect(url_for('form'))
#     # ...
#     template_meta = get_template_meta(session['template_id'])

#     # 1. On crée un clone complet du template
#     build_dir = copy_template_dir(template_meta)

#     # 2. On charge *l'original* main.tex puis GPT le remplit
#     with open(template_meta['latex_path'], encoding='utf-8') as f:
#         latex_src = f.read()
#     filled_tex = gpt_fill_latex(latex_src, session['cv_data'])

#     # 3. On écrase main.tex dans le clone
#     with open(os.path.join(build_dir, 'main.tex'), 'w', encoding='utf-8') as f:
#         f.write(filled_tex)

#     # 4. On lance pdflatex dans ce même clone
#     subprocess.run(
#         ['pdflatex', '-interaction=nonstopmode', 'main.tex'],
#         cwd=build_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
#     )
#     pdf_path = os.path.join(build_dir, 'main.pdf')

#     rel_pdf = os.path.relpath(pdf_path, start=app.config['OUTPUT_FOLDER'])
#     session['pdf_filename'] = rel_pdf
#     return render_template('preview.html', pdf_filename=rel_pdf)

# @app.route('/file/<path:filename>')
# def file(filename):
#     return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename))

# @app.route('/download')
# def download():
#     if 'pdf_filename' not in session:
#         return redirect(url_for('form'))
#     return send_file(os.path.join(app.config['OUTPUT_FOLDER'], session['pdf_filename']), as_attachment=True)

# if __name__ == '__main__':
#     app.run(debug=True)


################################################################################ Version 2 qui marche mais un petit souci

















































#################################################################



######################################################################"""
# #################################################################"




#####################################################"
# import os
# import json
# import uuid
# import shutil
# import subprocess
# import re
# from pathlib import Path

# from flask import (
#     Flask, render_template, request, redirect, url_for,
#     session, send_file, flash
# )
# from jinja2 import Environment, FileSystemLoader, select_autoescape
# import openai

# # ---------------------------------------------------------------------------
# #  Configuration -------------------------------------------------------------
# # ---------------------------------------------------------------------------
# openai.api_key = os.getenv("OPENAI_API_KEY", "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")  # facultatif mais requis pour GPT
# OPENAI_MODEL  = os.getenv("OPENAI_MODEL", "o3")
# LATEX_DEFAULT = os.getenv("LATEX_BIN", "pdflatex")       # moteur par défaut

# BASE_DIR = Path(__file__).resolve().parent

# app = Flask(__name__)
# app.config.update(
#     SECRET_KEY   = os.getenv("FLASK_SECRET", "change_me"),
#     UPLOAD_FOLDER= BASE_DIR / "static" / "uploads",
#     OUTPUT_FOLDER= BASE_DIR / "generated",
# )

# # ---------------------------------------------------------------------------
# #  Catalogue des templates ---------------------------------------------------
# # ---------------------------------------------------------------------------
# with open(BASE_DIR / "config.json", encoding="utf-8") as fh:
#     CV_TEMPLATES = json.load(fh)

# def get_template_meta(tid: str):
#     return next((t for t in CV_TEMPLATES if t["id"] == tid), None)

# # ---------------------------------------------------------------------------
# #  Helpers : schema / formulaire --------------------------------------------
# # ---------------------------------------------------------------------------

# def load_schema(meta: dict) -> dict:
#     """Lit le schema.json (UTF‑8) qui décrit les champs du formulaire."""
#     p = Path(meta["latex_path"]).with_name("schema.json")
#     if not p.exists():
#         raise FileNotFoundError(f"schema.json absent pour {meta['id']}")
#     return json.loads(p.read_text(encoding="utf-8"))


# def parse_form_data(schema: dict, form, files):
#     data = {}
#     for section in schema["sections"]:
#         for field in section["fields"]:
#             fid, ftype = field["id"], field.get("type", "text")
#             if ftype == "file":
#                 fobj = files.get(fid)
#                 if fobj and fobj.filename:
#                     ext   = Path(fobj.filename).suffix
#                     fname = f"{uuid.uuid4().hex}{ext}"
#                     dest  = app.config["UPLOAD_FOLDER"] / fname
#                     dest.parent.mkdir(parents=True, exist_ok=True)
#                     fobj.save(dest)
#                     data[fid] = fname
#                 else:
#                     data[fid] = ""
#             elif ftype == "array":
#                 rows = {}
#                 rgx  = re.compile(fr"{re.escape(fid)}\[(\d+)]\[(\w+)]")
#                 for k, v in form.items():
#                     m = rgx.fullmatch(k)
#                     if m:
#                         i, sub = m.groups(); rows.setdefault(int(i), {})[sub] = v
#                 data[fid] = [rows[i] for i in sorted(rows)]
#             else:
#                 data[fid] = form.get(fid, "")
#     return data

# # ---------------------------------------------------------------------------
# #  Rendu Jinja2 et pré‑correction GPT ---------------------------------------
# # ---------------------------------------------------------------------------

# def render_latex(meta: dict, context: dict) -> str:
#     tpl_path = Path(meta["latex_path"])
#     env = Environment(
#         loader=FileSystemLoader(tpl_path.parent),
#         autoescape=select_autoescape([]),
#         block_start_string="{%", block_end_string="%}",
#         variable_start_string="{{", variable_end_string="}}",
#         comment_start_string="((#", comment_end_string="#))",
#     )
#     return env.get_template(tpl_path.name).render(**context)


# def gpt_clean_latex(tex: str) -> str:
#     """Passe GPT‑4o pour corriger/optimiser le LaTeX (ciblé *pdflatex* uniquement)."""
#     if not openai.api_key:
#         return tex
#     sys = (
#         "Tu es un expert LaTeX. Le document doit être compilable avec pdflatex uniquement. "
#         "Corrige les erreurs éventuelles, rétablis les commandes incompatibles avec fontspec ou xelatex, "
#         "améliore la mise en page (lignes trop longues, items coupés) mais NE MODIFIE PAS le contenu. "
#         "Renvoie exclusivement le code final sans commentaire." )
#     resp = openai.ChatCompletion.create(
#         model=OPENAI_MODEL,
#         messages=[{"role":"system","content":sys}, {"role":"user","content":tex}])
#     cleaned = re.sub(r"^```.*?\n|\n?```$", "", resp.choices[0].message.content.strip(), flags=re.S)
#     return cleaned or tex


# # ---------------------------------------------------------------------------
# #  Compilation PDF -----------------------------------------------------------
# # ---------------------------------------------------------------------------

# def copy_template(meta: dict) -> Path:
#     src = Path(meta["latex_path"]).parent
#     dst = app.config["OUTPUT_FOLDER"] / uuid.uuid4().hex
#     shutil.copytree(src, dst)
#     return dst


# def _run_pdflatex(build: Path) -> subprocess.CompletedProcess:
#     return subprocess.run([
#         "pdflatex", "-interaction=nonstopmode", "main.tex"],
#         cwd=build, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


# def compile_pdf(tex: str, meta: dict, ctx: dict) -> Path:
#     """Compile une unique fois avec pdflatex (le LaTeX a déjà été passé à GPT)."""
#     build = copy_template(meta)
#     tex_path = build / "main.tex"
#     tex_path.write_text(tex, encoding="utf-8")

#     # copie éventuelle de la photo
#     if (photo := ctx.get("photo")):
#         src = app.config["UPLOAD_FOLDER"] / photo
#         if src.exists(): shutil.copy(src, build / photo)

#     proc = subprocess.run([
#         "pdflatex", "-interaction=nonstopmode", tex_path.name
#     ], cwd=build, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

#     if proc.returncode != 0:
#         log = (build / "main.log").read_text(errors="ignore")
#         raise RuntimeError("pdflatex a échoué." + log[:1500])

#     return build / "main.pdf"

#     # --- première erreur : on lit le log et demande à GPT de corriger --------
#     log_txt = (build / "main.log").read_text(errors="ignore")
#     if not openai.api_key:
#         raise RuntimeError("pdflatex a échoué et aucune clé GPT pour corriger." + log_txt[:1500])

#     sys = (
#         "Tu es un correcteur LaTeX. On doit absolument compiler avec pdflatex. "
#         "On te donne le fichier et le log d'erreur. Corrige uniquement ce qui empêche la compilation. "
#         "Ne touche pas au contenu textuel. Renvoie le code corrigé sans commentaire."
#     )
#     prompt = f"""--- TEX ---
# {tex}
# --- LOG ---
# {log_txt[:2000]}
# --- FIN ---"""
#     resp = openai.ChatCompletion.create(model=OPENAI_MODEL,
#                                         messages=[{"role":"system","content":sys},
#                                                   {"role":"user","content":prompt}]
#                                         )
#     fixed_tex = re.sub(r"^```.*?\n|\n?```$", "", resp.choices[0].message.content.strip(), flags=re.S)
#     tex_path.write_text(fixed_tex, encoding="utf-8")

#     proc2 = _run_pdflatex(build)
#     if proc2.returncode != 0:
#         log2 = (build / "main.log").read_text(errors="ignore")
#         raise RuntimeError("pdflatex échoue après correction GPT." + log2[:1500])

#     return build / "main.pdf"(f"Compilation LaTeX échouée. Engins testés : {', '.join(tried)}")

# # ---------------------------------------------------------------------------
# #  Routes HTTP ---------------------------------------------------------------
# # ---------------------------------------------------------------------------

# @app.route("/")
# def index():
#     return render_template("index.html", templates=CV_TEMPLATES)


# @app.route("/select/<template_id>")
# def select_template(template_id):
#     if not get_template_meta(template_id):
#         flash("Modèle invalide", "danger"); return redirect(url_for("index"))
#     session.clear(); session["template_id"] = template_id
#     return redirect(url_for("form"))


# @app.route("/form", methods=["GET", "POST"])
# def form():
#     if "template_id" not in session: return redirect(url_for("index"))
#     meta = get_template_meta(session["template_id"])
#     session.setdefault("schema", load_schema(meta))

#     if request.method == "POST":
#         session["cv_data"] = parse_form_data(session["schema"], request.form, request.files)
#         return redirect(url_for("preview"))

#     return render_template("form_schema.html", schema=session["schema"])


# @app.route("/preview")
# def preview():
#     if "cv_data" not in session: return redirect(url_for("form"))
#     meta = get_template_meta(session["template_id"])
#     raw_tex   = render_latex(meta, session["cv_data"])
#     cleaned   = gpt_clean_latex(raw_tex)
#     session["last_tex"] = cleaned
#     pdf = compile_pdf(cleaned, meta, session["cv_data"])
#     rel = pdf.relative_to(app.config["OUTPUT_FOLDER"])
#     session["pdf_filename"] = str(rel)
#     return render_template("preview.html", pdf_filename=rel)


# @app.route("/download")
# def download():
#     if "pdf_filename" not in session: return redirect(url_for("form"))
#     return send_file(app.config["OUTPUT_FOLDER"] / session["pdf_filename"], as_attachment=True)


# # ----------------------- Edition libre GPT ---------------------------------

# def gpt_edit(tex: str, instr: str) -> str:
#     if not openai.api_key:
#         raise RuntimeError("OPENAI_API_KEY manquant pour /edit")
#     sys="Tu es un expert LaTeX. Applique l'instruction et renvoie uniquement le code final."
#     msgs=[{"role":"system","content":sys},{"role":"user","content":f"Instruction : {instr}\n---\n{tex}"}]
#     rep=openai.ChatCompletion.create(model=OPENAI_MODEL,messages=msgs)
#     return re.sub(r"^```.*?\n|\n?```$","",rep.choices[0].message.content.strip(),flags=re.S)


# @app.route("/edit", methods=["POST"])
# def edit():
#     if "last_tex" not in session: return redirect(url_for("preview"))
#     instr=request.form.get("instruction","" ).strip()
#     if not instr: return redirect(url_for("preview"))
#     try:
#         new_tex = gpt_edit(session["last_tex"], instr)
#         meta    = get_template_meta(session["template_id"])
#         pdf     = compile_pdf(new_tex, meta, session["cv_data"])
#         session["last_tex"] = new_tex
#         session["pdf_filename"] = str(pdf.relative_to(app.config["OUTPUT_FOLDER"]))
#         flash("Modification appliquée !", "success")
#     except Exception as e:
#         flash(f"Erreur GPT/LaTeX : {e}", "danger")
#     return redirect(url_for("preview"))

# # ---------------------------------------------------------------------------
# if __name__ == "__main__":
#     app.run(debug=True, port=5000)


##################################################################################################

# import os
# import json
# import uuid
# import shutil
# import subprocess
# import re
# from pathlib import Path

# from flask import (
#     Flask, render_template, request, redirect, url_for,
#     session, send_file, flash
# )
# from jinja2 import Environment, FileSystemLoader, select_autoescape
# import openai

# # ---------------------------------------------------------------------------
# #  Configuration -------------------------------------------------------------
# # ---------------------------------------------------------------------------
# openai.api_key = os.getenv("OPENAI_API_KEY", "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")  # facultatif mais requis pour GPT
# OPENAI_MODEL  = os.getenv("OPENAI_MODEL", "o3")
# LATEX_DEFAULT = os.getenv("LATEX_BIN", "pdflatex")       # moteur par défaut

# BASE_DIR = Path(__file__).resolve().parent

# app = Flask(__name__)
# app.config.update(
#     SECRET_KEY   = os.getenv("FLASK_SECRET", "change_me"),
#     UPLOAD_FOLDER= BASE_DIR / "static" / "uploads",
#     OUTPUT_FOLDER= BASE_DIR / "generated",
# )

# # ---------------------------------------------------------------------------
# #  Catalogue des templates ---------------------------------------------------
# # ---------------------------------------------------------------------------
# with open(BASE_DIR / "config.json", encoding="utf-8") as fh:
#     CV_TEMPLATES = json.load(fh)

# def get_template_meta(tid: str):
#     return next((t for t in CV_TEMPLATES if t["id"] == tid), None)

# # ---------------------------------------------------------------------------
# #  Helpers : schema / formulaire --------------------------------------------
# # ---------------------------------------------------------------------------

# def load_schema(meta: dict) -> dict:
#     """Lit le schema.json (UTF‑8) qui décrit les champs du formulaire."""
#     p = Path(meta["latex_path"]).with_name("schema.json")
#     if not p.exists():
#         raise FileNotFoundError(f"schema.json absent pour {meta['id']}")
#     return json.loads(p.read_text(encoding="utf-8"))


# def parse_form_data(schema: dict, form, files):
#     data = {}
#     for section in schema["sections"]:
#         for field in section["fields"]:
#             fid, ftype = field["id"], field.get("type", "text")
#             if ftype == "file":
#                 fobj = files.get(fid)
#                 if fobj and fobj.filename:
#                     ext   = Path(fobj.filename).suffix
#                     fname = f"{uuid.uuid4().hex}{ext}"
#                     dest  = app.config["UPLOAD_FOLDER"] / fname
#                     dest.parent.mkdir(parents=True, exist_ok=True)
#                     fobj.save(dest)
#                     data[fid] = fname
#                 else:
#                     data[fid] = ""
#             elif ftype == "array":
#                 rows = {}
#                 rgx  = re.compile(fr"{re.escape(fid)}\[(\d+)]\[(\w+)]")
#                 for k, v in form.items():
#                     m = rgx.fullmatch(k)
#                     if m:
#                         i, sub = m.groups(); rows.setdefault(int(i), {})[sub] = v
#                 data[fid] = [rows[i] for i in sorted(rows)]
#             else:
#                 data[fid] = form.get(fid, "")
#     return data

# # ---------------------------------------------------------------------------
# #  Rendu Jinja2 et pré‑correction GPT ---------------------------------------
# # ---------------------------------------------------------------------------

# def render_latex(meta: dict, context: dict) -> str:
#     tpl_path = Path(meta["latex_path"])
#     env = Environment(
#         loader=FileSystemLoader(tpl_path.parent),
#         autoescape=select_autoescape([]),
#         block_start_string="{%", block_end_string="%}",
#         variable_start_string="{{", variable_end_string="}}",
#         comment_start_string="((#", comment_end_string="#))",
#     )
#     return env.get_template(tpl_path.name).render(**context)


# def gpt_clean_latex(tex: str) -> str:
#     """Passe GPT‑4o pour corriger/optimiser le LaTeX (ciblé *pdflatex* uniquement)."""
#     if not openai.api_key:
#         return tex
#     sys = (
#         "Tu es un expert LaTeX. Le document doit être compilable avec pdflatex uniquement. "
#         "Corrige les erreurs éventuelles, rétablis les commandes incompatibles avec fontspec ou xelatex, "
#         "améliore la mise en page (lignes trop longues, items coupés) mais NE MODIFIE PAS le contenu. "
#         "Renvoie exclusivement le code final sans commentaire." )
#     resp = openai.ChatCompletion.create(
#         model=OPENAI_MODEL,
#         messages=[{"role":"system","content":sys}, {"role":"user","content":tex}])
#     cleaned = re.sub(r"^```.*?\n|\n?```$", "", resp.choices[0].message.content.strip(), flags=re.S)
#     return cleaned or tex


# # ---------------------------------------------------------------------------
# #  Compilation PDF -----------------------------------------------------------
# # ---------------------------------------------------------------------------

# def copy_template(meta: dict) -> Path:
#     src = Path(meta["latex_path"]).parent
#     dst = app.config["OUTPUT_FOLDER"] / uuid.uuid4().hex
#     shutil.copytree(src, dst)
#     return dst


# def _run_pdflatex(build: Path) -> subprocess.CompletedProcess:
#     return subprocess.run([
#         "pdflatex", "-interaction=nonstopmode", "main.tex"],
#         cwd=build, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


# def compile_pdf(tex: str, meta: dict, ctx: dict) -> Path:
#     """Compile une unique fois avec pdflatex (le LaTeX a déjà été passé à GPT)."""
#     build = copy_template(meta)
#     tex_path = build / "main.tex"
#     tex_path.write_text(tex, encoding="utf-8")

#     # copie éventuelle de la photo
#     if (photo := ctx.get("photo")):
#         src = app.config["UPLOAD_FOLDER"] / photo
#         if src.exists(): shutil.copy(src, build / photo)

#     proc = subprocess.run([
#         "pdflatex", "-interaction=nonstopmode", tex_path.name
#     ], cwd=build, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

#     if proc.returncode != 0:
#         log = (build / "main.log").read_text(errors="ignore")
#         raise RuntimeError("pdflatex a échoué." + log[:1500])

#     return build / "main.pdf"

# #     # --- première erreur : on lit le log et demande à GPT de corriger --------
# #     log_txt = (build / "main.log").read_text(errors="ignore")
# #     if not openai.api_key:
# #         raise RuntimeError("pdflatex a échoué et aucune clé GPT pour corriger." + log_txt[:1500])

# #     sys = (
# #         "Tu es un correcteur LaTeX. On doit absolument compiler avec pdflatex. "
# #         "On te donne le fichier et le log d'erreur. Corrige uniquement ce qui empêche la compilation. "
# #         "Ne touche pas au contenu textuel. Renvoie le code corrigé sans commentaire."
# #     )
# #     prompt = f"""--- TEX ---
# # {tex}
# # --- LOG ---
# # {log_txt[:2000]}
# # --- FIN ---"""
# #     resp = openai.ChatCompletion.create(model=OPENAI_MODEL,
# #                                         messages=[{"role":"system","content":sys},
# #                                                   {"role":"user","content":prompt}],
# #                                         temperature=0)
# #     fixed_tex = re.sub(r"^```.*?\n|\n?```$", "", resp.choices[0].message.content.strip(), flags=re.S)
# #     tex_path.write_text(fixed_tex, encoding="utf-8")

# #     proc2 = _run_pdflatex(build)
# #     if proc2.returncode != 0:
# #         log2 = (build / "main.log").read_text(errors="ignore")
# #         raise RuntimeError("pdflatex échoue après correction GPT." + log2[:1500])

# #     return build / "main.pdf"(f"Compilation LaTeX échouée. Engins testés : {', '.join(tried)}")

# # ---------------------------------------------------------------------------
# #  Routes HTTP ---------------------------------------------------------------
# # ---------------------------------------------------------------------------

# @app.route("/")
# def index():
#     return render_template("index.html", templates=CV_TEMPLATES)


# @app.route("/select/<template_id>")
# def select_template(template_id):
#     if not get_template_meta(template_id):
#         flash("Modèle invalide", "danger"); return redirect(url_for("index"))
#     session.clear(); session["template_id"] = template_id
#     return redirect(url_for("form"))


# @app.route("/form", methods=["GET", "POST"])
# def form():
#     if "template_id" not in session: return redirect(url_for("index"))
#     meta = get_template_meta(session["template_id"])
#     session.setdefault("schema", load_schema(meta))

#     if request.method == "POST":
#         session["cv_data"] = parse_form_data(session["schema"], request.form, request.files)
#         return redirect(url_for("preview"))

#     return render_template("form_schema.html", schema=session["schema"])


# @app.route("/preview")
# def preview():
#     if "cv_data" not in session: return redirect(url_for("form"))
#     meta = get_template_meta(session["template_id"])
#     raw_tex   = render_latex(meta, session["cv_data"])
#     cleaned   = gpt_clean_latex(raw_tex)
#     session["last_tex"] = cleaned
#     pdf = compile_pdf(cleaned, meta, session["cv_data"])
#     rel = pdf.relative_to(app.config["OUTPUT_FOLDER"]).as_posix()
#     session["pdf_filename"] = rel
#     return render_template("preview.html", pdf_filename=rel)


# @app.route("/download")
# def download():
#     if "pdf_filename" not in session: return redirect(url_for("form"))
#     return send_file(app.config["OUTPUT_FOLDER"] / session["pdf_filename"], as_attachment=True)


# # ----------------------- Edition libre GPT ---------------------------------

# def gpt_edit(tex: str, instr: str) -> str:
#     if not openai.api_key:
#         raise RuntimeError("OPENAI_API_KEY manquant pour /edit")
#     sys="Tu es un expert LaTeX. Applique l'instruction et renvoie uniquement le code final."
#     msgs=[{"role":"system","content":sys},{"role":"user","content":f"Instruction : {instr}\n---\n{tex}"}]
#     rep=openai.ChatCompletion.create(model=OPENAI_MODEL,messages=msgs)
#     return re.sub(r"^```.*?\n|\n?```$","",rep.choices[0].message.content.strip(),flags=re.S)


# @app.route("/edit", methods=["POST"])
# def edit():
#     if "last_tex" not in session: return redirect(url_for("preview"))
#     instr=request.form.get("instruction","" ).strip()
#     if not instr: return redirect(url_for("preview"))
#     try:
#         new_tex = gpt_edit(session["last_tex"], instr)
#         meta    = get_template_meta(session["template_id"])
#         pdf     = compile_pdf(new_tex, meta, session["cv_data"])
#         session["last_tex"] = new_tex
#         session["pdf_filename"] = str(pdf.relative_to(app.config["OUTPUT_FOLDER"]))
#         flash("Modification appliquée !", "success")
#     except Exception as e:
#         flash(f"Erreur GPT/LaTeX : {e}", "danger")
#     return redirect(url_for("preview"))

# # ---------------------------------------------------------------------------
# if __name__ == "__main__":
#     app.run(debug=True, port=5000)

