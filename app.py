from flask import Flask, request
import requests
from bs4 import BeautifulSoup
from groq import Groq
import json
import pandas as pd
from datetime import datetime
import uuid
import os

app = Flask(__name__)

# =========================
# 🔑 API KEY SEGURA (desde Render)
# =========================
api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    raise ValueError("Falta la API KEY de Groq en Render")

client = Groq(api_key=api_key)

# almacenamiento temporal
quizzes = {}

# =========================
# 🧑‍💼 ADMIN
# =========================

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        content = request.form["content"]

        if content.startswith("http"):
            response = requests.get(content)
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text()
        else:
            text = content

        prompt = f"""
Respondé SOLO en JSON válido, sin texto extra.

Formato obligatorio:

[
{{
"pregunta": "texto",
"opciones": ["A","B","C","D"],
"correcta": "A"
}}
]

No agregues explicaciones.

Generá 5 preguntas.

Basado en:
{text[:2000]}
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )

        quiz_json = response.choices[0].message.content.strip()

        # limpieza automática
        start = quiz_json.find("[")
        end = quiz_json.rfind("]") + 1
        quiz_json = quiz_json[start:end]

        try:
            quiz = json.loads(quiz_json)
        except:
            return f"<pre>Error JSON:\n{quiz_json}</pre>"

        quiz_id = str(uuid.uuid4())
        quizzes[quiz_id] = quiz

        link = f"{request.url_root}quiz/{quiz_id}"

        return f"""
        <h2>✅ Quiz creado</h2>
        <p>Link para enviar:</p>
        <a href="{link}" target="_blank">{link}</a>
        <br><br><a href="/admin">Crear otro</a>
        """

    return """
    <h1>🧑‍💼 PANEL ADMIN</h1>

    <form method="post">
    <textarea name="content" rows="10" cols="60" placeholder="Pegá texto o URL"></textarea><br><br>
    <button type="submit">Generar Evaluación</button>
    </form>
    """

# =========================
# 👤 USER
# =========================

@app.route("/quiz/<quiz_id>", methods=["GET"])
def quiz(quiz_id):
    if quiz_id not in quizzes:
        return "Quiz no encontrado"

    quiz = quizzes[quiz_id]

    html = """
    <html>
    <body style="background:#f0ebf8;font-family:Arial;">
    <div style="width:60%;margin:auto;">

    <h1 style="background:#673ab7;color:white;padding:20px;border-radius:8px;">
    Evaluación
    </h1>

    <form method="post" action="/submit">
    """

    html += """
    <label>Email:</label><br>
    <input type="email" name="email" required><br><br>

    <label>Nombre:</label><br>
    <input type="text" name="nombre" required><br><br>
    """

    for i, q in enumerate(quiz):
        html += f"<div style='background:white;padding:15px;margin:10px;border-radius:8px;'>"
        html += f"<p><b>{q['pregunta']}</b></p>"

        for op in q["opciones"]:
            html += f"""
            <input type="radio" name="q{i}" value="{op}" required> {op}<br>
            """

        html += "</div>"

    html += f"""
    <input type="hidden" name="quiz_id" value="{quiz_id}">
    <button type="submit">Enviar respuestas</button>
    </form>
    </div>
    </body>
    </html>
    """

    return html

# =========================
# 📊 RESULTADOS
# =========================

@app.route("/submit", methods=["POST"])
def submit():
    nombre = request.form["nombre"]
    email = request.form["email"]
    quiz_id = request.form["quiz_id"]

    quiz = quizzes.get(quiz_id)

    score = 0
    for i, q in enumerate(quiz):
        if request.form.get(f"q{i}") == q["correcta"]:
            score += 1

    total = len(quiz)
    porcentaje = round((score / total) * 100, 2)

    data = {
        "Nombre": nombre,
        "Email": email,
        "Puntaje": score,
        "Total": total,
        "Porcentaje": porcentaje,
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    try:
        df = pd.read_excel("resultados.xlsx")
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    except:
        df = pd.DataFrame([data])

    df.to_excel("resultados.xlsx", index=False)

    return f"""
    <h2>Resultado</h2>
    <p>{nombre}</p>
    <p>{score}/{total} ({porcentaje}%)</p>
    <a href="/admin">Volver</a>
    """

# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)