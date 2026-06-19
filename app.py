from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import pytesseract
from PIL import Image
import numpy  # must load before sumy so LSA summarizer sees NumPy
from deep_translator import GoogleTranslator
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
import os
import json
from werkzeug.utils import secure_filename
import io
import tempfile
import secrets

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
except Exception:
    pdfminer_extract_text = None

try:
    from pdf2image import convert_from_path, convert_from_bytes
except Exception:
    convert_from_path = None
    convert_from_bytes = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['RESULTS_FOLDER'] = 'results/'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

MAX_PDF_PAGES = int(os.environ.get('MAX_PDF_PAGES', '10'))

# Ensure Flask has a SECRET_KEY for session/flash. In production set the SECRET_KEY env var.
# Fallback: generate a random key for development (note: this will change on each restart).
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Optional: let user set TESSERACT_CMD and POPPLER_PATH via environment variables
if os.environ.get('TESSERACT_CMD'):
    pytesseract.pytesseract.tesseract_cmd = os.environ.get('TESSERACT_CMD')

POPPLER_PATH = os.environ.get('POPPLER_PATH')  # optional


def ensure_nltk_data():
    import nltk
    for package in ('punkt', 'punkt_tab'):
        try:
            nltk.data.find(f'tokenizers/{package}')
        except LookupError:
            nltk.download(package, quiet=True)


ensure_nltk_data()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def save_page_result(data):
    """Store large results on disk; redirect with a short id (avoids huge session cookies)."""
    rid = secrets.token_urlsafe(12)
    path = os.path.join(app.config['RESULTS_FOLDER'], f'{rid}.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh)
    return rid


def load_page_result(rid):
    if not rid:
        return {}
    safe = secure_filename(rid)
    if safe != rid:
        return {}
    path = os.path.join(app.config['RESULTS_FOLDER'], f'{rid}.json')
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


# Home page
@app.route('/', methods=['GET'])
def index():
    page = load_page_result(request.args.get('r'))
    return render_template(
        'index.html',
        ocr_text=page.get('ocr_text'),
        pdf_text=page.get('pdf_text'),
        translated_text=page.get('translated_text'),
        summary_text=page.get('summary_text'),
        source_preview=page.get('source_preview'),
    )


@app.route('/ocr', methods=['GET'])
@app.route('/pdf', methods=['GET'])
@app.route('/translate', methods=['GET'])
@app.route('/summarize', methods=['GET'])
def form_get_redirect():
    return redirect(url_for('index'))


@app.route('/download_text', methods=['POST'])
def download_text():
    text = request.form.get('text') or ''
    filename = request.form.get('filename') or 'output.txt'
    b = text.encode('utf-8')
    return send_file(io.BytesIO(b), as_attachment=True, download_name=filename, mimetype='text/plain')


@app.route('/ocr', methods=['POST'])
def ocr():
    if 'image' not in request.files:
        flash('No image file part')
        return redirect(url_for('index'))
    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        flash('No selected file or invalid file type')
        return redirect(url_for('index'))
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    # basic preprocessing could be added here
    try:
        text = pytesseract.image_to_string(Image.open(filepath))
    except Exception as e:
        text = ''
        flash('OCR error: %s' % str(e))
    rid = save_page_result({'ocr_text': text, 'source_preview': filename})
    return redirect(url_for('index', r=rid))


@app.route('/pdf', methods=['POST'])
def pdf():
    if 'pdf' not in request.files:
        flash('No PDF file part')
        return redirect(url_for('index'))
    file = request.files['pdf']
    if file.filename == '' or not allowed_file(file.filename):
        flash('No selected file or invalid file type')
        return redirect(url_for('index'))
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    extracted_text = []

    # First try to extract text from the PDF (text-based PDFs)
    # 1) PyPDF2
    if PyPDF2 is not None:
        try:
            with open(filepath, 'rb') as fh:
                reader = PyPDF2.PdfReader(fh)
                pages = reader.pages[:MAX_PDF_PAGES]
                if len(reader.pages) > MAX_PDF_PAGES:
                    flash('PDF has %d pages; processing first %d to stay within time limits.' % (len(reader.pages), MAX_PDF_PAGES))
                for page in pages:
                    try:
                        ptext = page.extract_text() or ''
                    except Exception:
                        ptext = ''
                    if ptext:
                        extracted_text.append(ptext)
        except Exception:
            # fall through to next extractor
            extracted_text = []

    if not any(extracted_text):
        # Choose renderer: 'auto' -> try poppler/pdf2image first, then PyMuPDF; or respect PDF_RENDERER env var
        renderer = os.environ.get('PDF_RENDERER', 'auto').lower()
        used_renderer = None

        # Try pdf2image + Poppler when requested or in auto mode
        if renderer in ('auto', 'poppler') and convert_from_bytes is not None:
            try:
                with open(filepath, 'rb') as fh:
                    pdf_bytes = fh.read()
                if POPPLER_PATH:
                    images = convert_from_bytes(pdf_bytes, dpi=200, poppler_path=POPPLER_PATH)
                else:
                    images = convert_from_bytes(pdf_bytes, dpi=200)
                if len(images) > MAX_PDF_PAGES:
                    flash('PDF has %d pages; processing first %d to stay within time limits.' % (len(images), MAX_PDF_PAGES))
                    images = images[:MAX_PDF_PAGES]
                for img in images:
                    try:
                        ptext = pytesseract.image_to_string(img)
                    except Exception:
                        ptext = ''
                    extracted_text.append(ptext)
                used_renderer = 'poppler/pdf2image'
            except Exception as e:
                # record error and fall back to next renderer
                flash('Error converting PDF to images with pdf2image/poppler: %s' % str(e))

        # If no text yet and PyMuPDF is available, use it (no Poppler required)
        if not any(extracted_text) and (renderer in ('auto', 'pymupdf')):
            if fitz is None:
                # fitz not available
                if not used_renderer:
                    flash('No PDF renderer available: install Poppler (pdftoppm) or PyMuPDF. See README for options.')
            else:
                try:
                    doc = fitz.open(filepath)
                    page_count = doc.page_count
                    pages_to_read = min(page_count, MAX_PDF_PAGES)
                    if page_count > MAX_PDF_PAGES:
                        flash('PDF has %d pages; processing first %d to stay within time limits.' % (page_count, MAX_PDF_PAGES))
                    zoom = float(os.environ.get('PDF_RENDER_ZOOM', 2.0))
                    mat = fitz.Matrix(zoom, zoom)
                    for pno in range(pages_to_read):
                        page = doc.load_page(pno)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img_data = pix.tobytes('png')
                        img = Image.open(io.BytesIO(img_data))
                        try:
                            ptext = pytesseract.image_to_string(img)
                        except Exception:
                            ptext = ''
                        extracted_text.append(ptext)
                    used_renderer = 'pymupdf'
                except Exception as e:
                    flash('Error rendering PDF with PyMuPDF: %s' % str(e))

        # If still no renderer used, provide guidance
        if not any(extracted_text) and used_renderer is None:
            # If renderer explicitly set to 'poppler' but convert_from_bytes missing, give specific hint
            if renderer == 'poppler' and convert_from_bytes is None:
                flash('PDF_RENDERER=poppler was requested but pdf2image/Poppler is not available. Install Poppler or switch to PDF_RENDERER=pymupdf.')
            else:
                flash('No text could be extracted from the provided PDF. If this is a scanned PDF, install Poppler or PyMuPDF plus Tesseract (see README).')

    full_text = '\n\n'.join([t for t in extracted_text if t])
    if not full_text:
        flash('No text could be extracted from the provided PDF. If this is a scanned PDF, ensure Poppler and Tesseract are installed (see README).')
    rid = save_page_result({'pdf_text': full_text, 'source_preview': filename})
    return redirect(url_for('index', r=rid))


@app.route('/translate', methods=['POST'])
def translate():
    text = request.form.get('text')
    dest_lang = request.form.get('dest_lang')
    if not text or not dest_lang:
        flash('Missing text or target language')
        return redirect(url_for('index'))
    try:
        translated_text = GoogleTranslator(source='auto', target=dest_lang).translate(text)
    except Exception as e:
        translated_text = ''
        flash('Translation error: %s' % str(e))
    rid = save_page_result({'translated_text': translated_text})
    return redirect(url_for('index', r=rid))


@app.route('/summarize', methods=['POST'])
def summarize():
    text = request.form.get('text')
    sentences = request.form.get('sentences') or 3
    try:
        sentences = int(sentences)
    except Exception:
        sentences = 3
    if not text:
        flash('No text provided for summarization')
        return redirect(url_for('index'))
    try:
        parser = PlaintextParser.from_string(text, Tokenizer('english'))
        summarizer = LsaSummarizer()
        summary = summarizer(parser.document, sentences)
        summary_text = ' '.join(str(sentence) for sentence in summary)
    except Exception as e:
        summary_text = ''
        flash('Summarization error: %s' % str(e))
    rid = save_page_result({'summary_text': summary_text})
    return redirect(url_for('index', r=rid))


if __name__ == '__main__':
    app.run(debug=True)
