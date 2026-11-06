import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app)  # Permite peticiones CORS desde Netlify

# Configuración con credenciales exactas de Aiven
db_config = {
    'host': os.environ.get('DB_HOST', 'muraliasql-muralia.g.aivencloud.com'),
    'port': int(os.environ.get('DB_PORT', 14433)),
    'user': os.environ.get('DB_USER', 'avnadmin'),
    'password': os.environ.get('DB_PASSWORD', 'AVNS_bpwXhJWGmadm6-TAZEN'),
    'database': os.environ.get('DB_NAME', 'muralia'),
    'ssl_disabled': False
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# -------------------------------------------------------------
# RUTAS DE LA API
# -------------------------------------------------------------

# 1. Obtener murales aprobados y sus comentarios
@app.route('/api/murals', methods=['GET'])
def get_murals():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM murales WHERE estatus = 'aprobado' ORDER BY fecha_registro DESC")
        murals = cursor.fetchall()
        
        for mural in murals:
            cursor.execute("""
                SELECT c.texto, c.fecha, u.nombre_tag AS author 
                FROM comentarios c 
                JOIN usuarios u ON c.id_usuario = u.id_usuario 
                WHERE c.id_mural = %s 
                ORDER BY c.fecha ASC
            """, (mural['id_mural'],))
            mural['comments'] = cursor.fetchall()
            
        cursor.close()
        conn.close()
        return jsonify(murals), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. Enviar propuesta de mural
@app.route('/api/propose', methods=['POST'])
def propose_mural():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO murales (id_usuario, titulo, artista_crew, ubicacion_texto, latitud, longitud, imagen_url, estatus)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pendiente')
        """
        values = (
            data.get('id_usuario'),
            data['titulo'],
            data.get('artista_crew', 'Comunidad'),
            data.get('ubicacion_texto'),
            data.get('latitud'),
            data.get('longitud'),
            data['imagen_url']
        )
        
        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Propuesta registrada exitosamente"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. Registrar nuevo usuario
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id_usuario FROM usuarios WHERE email = %s", (data['email'],))
        if cursor.fetchone():
            return jsonify({"error": "El correo ya está registrado"}), 400
            
        query = "INSERT INTO usuarios (nombre_tag, email, password_hash, rol) VALUES (%s, %s, %s, %s)"
        values = (data['nombre_tag'], data['email'], data['password'], data.get('rol', 'aficionado'))
        
        cursor.execute(query, values)
        conn.commit()
        
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify({
            "id_usuario": new_id,
            "nombre_tag": data['nombre_tag'],
            "email": data['email'],
            "rol": data.get('rol', 'aficionado'),
            "nivel_puntos": 0
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 4. Iniciar sesión
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id_usuario, nombre_tag, email, rol, nivel_puntos 
            FROM usuarios 
            WHERE email = %s AND password_hash = %s
        """, (data['email'], data['password']))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            return jsonify(user), 200
        else:
            return jsonify({"error": "Correo o contraseña incorrectos"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 5. Agregar un comentario
@app.route('/api/comments', methods=['POST'])
def add_comment():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "INSERT INTO comentarios (id_mural, id_usuario, texto) VALUES (%s, %s, %s)"
        cursor.execute(query, (data['id_mural'], data['id_usuario'], data['texto']))
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Comentario guardado"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 6. Obtener propuestas pendientes (Admin)
@app.route('/api/admin/pending', methods=['GET'])
def get_pending():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM murales WHERE estatus = 'pendiente' ORDER BY fecha_registro DESC")
        pending = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(pending), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 7. Aprobar propuesta (Admin)
@app.route('/api/admin/approve/<int:id_mural>', methods=['PUT'])
def approve_mural(id_mural):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("UPDATE murales SET estatus = 'aprobado' WHERE id_mural = %s", (id_mural,))
        
        cursor.execute("SELECT id_usuario FROM murales WHERE id_mural = %s", (id_mural,))
        mural = cursor.fetchone()
        
        if mural and mural['id_usuario']:
            cursor.execute("UPDATE usuarios SET nivel_puntos = nivel_puntos + 1 WHERE id_usuario = %s", (mural['id_usuario'],))
            
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Mural aprobado con éxito"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
