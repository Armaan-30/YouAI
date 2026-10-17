"""Real rendered image-PDF OCR checks, including Devanagari shaping."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf
from app.rag import extract
samples = {'eng':('The project launch is tomorrow.','project'),
           'spa':('El proyecto comienza mañana.','proyecto'),
           'fra':('Le projet commence demain.','projet'),
           'deu':('Das Projekt beginnt morgen.','Projekt'),
           'hin':('भारत एक महान देश है','भारत')}
for lang,(text,expected) in samples.items():
    document=pymupdf.open();page=document.new_page()
    css="@font-face {font-family: local; src: url(Nirmala.ttc);} body {font-family: local; font-size:28px}"
    page.insert_htmlbox(pymupdf.Rect(30,30,560,250),text,css=css,archive=pymupdf.Archive('C:/Windows/Fonts'))
    image=page.get_pixmap(matrix=pymupdf.Matrix(2,2)).tobytes('png')
    scan=pymupdf.open();scan.new_page().insert_image(page.rect,stream=image)
    chunks,warnings=extract('language.pdf',scan.tobytes(),'eng' if lang=='eng' else 'eng+'+lang)
    result=' '.join(c['text'] for c in chunks)
    assert expected.casefold() in result.casefold(), ascii(result)
    print(lang + ': real scanned-page OCR passed')
