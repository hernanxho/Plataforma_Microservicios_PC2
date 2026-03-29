from flask import Flask, request, jsonify, render_template
import os
import subprocess
import textwrap
import shutil
import requests

app = Flask(__name__)

BASE_DIR = "servicios"

# 🔥 ahora guardamos más info
servicios_puertos = {}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/crear", methods=["POST"])
def crear_microservicio():
    data = request.json

    nombre = data.get("nombre")
    codigo = data.get("codigo")
    lenguaje = data.get("lenguaje")

    if not nombre or not codigo or not lenguaje:
        return jsonify({"error": "Faltan datos"}), 400

    # 🔥 evitar duplicados
    if nombre in servicios_puertos or os.path.exists(os.path.join(BASE_DIR, nombre)):
        return jsonify({"error": "Ya existe un microservicio con ese nombre"}), 400

    ruta = os.path.join(BASE_DIR, nombre)
    os.makedirs(ruta)

    # =========================
    # PYTHON
    # =========================
    if lenguaje == "python":
        archivo = "app.py"
        codigo_escaped = repr(codigo)

        codigo_final = textwrap.dedent(f"""\
# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import sys
import io

app = Flask(__name__)

{codigo}

@app.route("/")
def endpoint():
    try:
        import re

        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()

        match = re.search(r"def\\s+(\\w+)\\((.*?)\\)", {codigo_escaped})

        if match:
            nombre_funcion = match.group(1)
            func = globals()[nombre_funcion]

            args = request.args.to_dict()

            for k, v in args.items():
                if v.isdigit():
                    args[k] = int(v)

            try:
                resultado = func(**args)
            except:
                resultado = func()
        else:
            resultado = "No se encontro funcion"

        output = buffer.getvalue()
        sys.stdout = old_stdout

        return jsonify({{
            "resultado": resultado,
            "prints": output
        }})

    except Exception as e:
        return jsonify({{"error": str(e)}})

app.run(host="0.0.0.0", port=5000)
""")

        with open(os.path.join(ruta, archivo), "w", encoding="utf-8") as f:
            f.write(codigo_final)

        dockerfile = textwrap.dedent("""\
FROM python:3.10
WORKDIR /app
COPY . .
RUN pip install flask
CMD ["python", "app.py"]
""")

    elif lenguaje == "node":
        archivo = "app.js"
        codigo_escaped = repr(codigo)

        codigo_final = textwrap.dedent(f"""\
const express = require("express");
const app = express();

let logs = [];
const originalLog = console.log;
console.log = (...args) => {{
    logs.push(args.join(" "));
    originalLog(...args);
}};

{codigo}

app.get("/", (req, res) => {{
    try {{
        const match = {codigo_escaped}.match(/function\\s+(\\w+)\\((.*?)\\)/);

        if (match) {{
            const nombreFuncion = match[1];
            const params = match[2].split(",").map(p => p.trim()).filter(p => p);

            let args = [];

            for (let p of params) {{
                let val = req.query[p];
                if (!isNaN(val)) val = Number(val);
                args.push(val);
            }}

            let resultado;

            try {{
                resultado = eval(nombreFuncion)(...args);
            }} catch {{
                resultado = eval(nombreFuncion)();
            }}

            res.json({{
                resultado: resultado,
                prints: logs.join("\\n")
            }});

        }} else {{
            res.json({{ resultado: "No se encontro funcion" }});
        }}

    }} catch (error) {{
        res.json({{ error: error.toString() }});
    }}
}});

app.listen(5000, "0.0.0.0");
""")

        with open(os.path.join(ruta, archivo), "w", encoding="utf-8") as f:
            f.write(codigo_final)

        with open(os.path.join(ruta, "package.json"), "w") as f:
            f.write("""{
  "name": "microservicio",
  "version": "1.0.0",
  "main": "app.js",
  "dependencies": {
    "express": "^4.18.2"
  }
}""")

        dockerfile = textwrap.dedent("""\
FROM node:18
WORKDIR /app
COPY . .
RUN npm install
CMD ["node", "app.js"]
""")

    else:
        return jsonify({"error": "Lenguaje no soportado"}), 400

    with open(os.path.join(ruta, "Dockerfile"), "w") as f:
        f.write(dockerfile)

    try:
        subprocess.run(["docker", "build", "-t", nombre, "."], cwd=ruta, check=True)

        puerto = 5000 + len(servicios_puertos) + 1

        # 🔥 guardamos todo
        servicios_puertos[nombre] = {
            "puerto": puerto,
            "lenguaje": lenguaje,
            "status": "running"
        }

        subprocess.Popen(
            ["docker", "run", "-d", "--name", nombre, "-p", f"{puerto}:5000", nombre]
        )

        return jsonify({
            "mensaje": "Microservicio creado",
            "url": f"http://localhost:{puerto}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# LISTAR
# =========================
@app.route("/listar")
def listar():
    return jsonify([
        {
            "name": nombre,
            "port": data["puerto"],
            "lenguaje": data["lenguaje"],
            "status": data.get("status", "stopped")
        }
        for nombre, data in servicios_puertos.items()
    ])


@app.route("/detener", methods=["POST"])
def detener():
    data = request.json
    nombre = data.get("nombre")

    if nombre not in servicios_puertos:
        return jsonify({"error": "Microservicio no encontrado"}), 404

    try:
        subprocess.run(["docker", "stop", nombre], check=True)
        servicios_puertos[nombre]["status"] = "stopped"
        return jsonify({"mensaje": "Microservicio detenido"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/iniciar", methods=["POST"])
def iniciar():
    data = request.json
    nombre = data.get("nombre")

    if nombre not in servicios_puertos:
        return jsonify({"error": "Microservicio no encontrado"}), 404

    try:
        subprocess.run(["docker", "start", nombre], check=True)
        servicios_puertos[nombre]["status"] = "running"
        return jsonify({"mensaje": "Microservicio iniciado"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# ELIMINAR
# =========================
@app.route("/eliminar", methods=["POST"])
def eliminar():
    data = request.json
    nombre = data.get("nombre")

    try:
        subprocess.run(["docker", "rm", "-f", nombre], check=True)

        ruta = os.path.join(BASE_DIR, nombre)
        if os.path.exists(ruta):
            shutil.rmtree(ruta)

        servicios_puertos.pop(nombre, None)

        return jsonify({"mensaje": "Eliminado correctamente"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=3000)