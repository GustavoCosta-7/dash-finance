import os
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do ficheiro .env (para desenvolvimento local)
load_dotenv()

# --- Configuração da Aplicação Flask ---
app = Flask(__name__)
CORS(app)  # Permite requisições do seu frontend no Netlify

# --- Configuração da Base de Dados e Admin ---
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123') # Senha para a área de admin

# --- Funções de Base de Dados ---

def get_db_connection():
    """Cria e retorna uma conexão com a base de dados PostgreSQL."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Erro ao conectar à base de dados: {e}")
        return None

def init_db():
    """Cria a tabela de utilizadores se ela não existir."""
    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    password_hash VARCHAR(256) NOT NULL,
                    name VARCHAR(100),
                    photo TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()
        conn.close()
        print("Base de dados inicializada com sucesso.")

# --- Template HTML da Interface de Admin ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8"><title>Admin FinanSmart</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100">
    <div class="container mx-auto p-8 max-w-2xl">
        <h1 class="text-3xl font-bold mb-6 text-slate-800">Admin - Gestão de Utilizadores</h1>
        
        <!-- Formulário de Criação -->
        <div class="bg-white p-6 rounded-lg shadow-md mb-8">
            <h2 class="text-xl font-semibold mb-4">Criar Novo Utilizador</h2>
            <form method="POST" action="{{ url_for('admin') }}" class="space-y-4">
                <input type="hidden" name="action" value="create">
                <div>
                    <label for="name" class="block text-sm font-medium text-gray-700">Nome</label>
                    <input type="text" name="name" id="name" required class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-sky-500 focus:ring-sky-500">
                </div>
                <div>
                    <label for="email" class="block text-sm font-medium text-gray-700">Email</label>
                    <input type="email" name="email" id="email" required class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-sky-500 focus:ring-sky-500">
                </div>
                <div>
                    <label for="password" class="block text-sm font-medium text-gray-700">Senha</label>
                    <input type="password" name="password" id="password" required class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-sky-500 focus:ring-sky-500">
                </div>
                <div>
                    <label for="admin_password" class="block text-sm font-medium text-gray-700">Senha de Admin</label>
                    <input type="password" name="admin_password" id="admin_password" required class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-sky-500 focus:ring-sky-500">
                </div>
                <button type="submit" class="w-full bg-sky-600 text-white py-2 px-4 rounded-md hover:bg-sky-700">Criar Utilizador</button>
            </form>
        </div>

        <!-- Mensagem de Feedback -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="p-4 mb-4 text-sm rounded-lg {% if category == 'success' %} bg-green-100 text-green-800 {% else %} bg-red-100 text-red-800 {% endif %}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Lista de Utilizadores -->
        <div class="bg-white p-6 rounded-lg shadow-md">
            <h2 class="text-xl font-semibold mb-4">Utilizadores Registados</h2>
            <ul class="space-y-2">
                {% for user in users %}
                <li class="p-3 bg-slate-50 rounded-md flex justify-between items-center">
                    <span>{{ user.name }} ({{ user.email }})</span>
                </li>
                {% else %}
                <li>Nenhum utilizador encontrado.</li>
                {% endfor %}
            </ul>
        </div>
    </div>
</body>
</html>
"""

# --- Rotas da Aplicação ---

@app.route('/login', methods=['POST'])
def login():
    """Valida as credenciais do utilizador."""
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'success': False, 'error': 'Email e senha são obrigatórios.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Erro de conexão com a base de dados.'}), 500

    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (data['email'],))
        user = cur.fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], data['password']):
        user_profile = {
            "name": user['name'],
            "email": user['email'],
            "photo": user['photo'] or ""
        }
        return jsonify({'success': True, 'user': user_profile}), 200
    else:
        return jsonify({'success': False, 'error': 'Credenciais inválidas.'}), 401

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """Página de administração para criar utilizadores."""
    from flask import flash, get_flashed_messages
    
    conn = get_db_connection()
    if not conn:
        return "Erro de conexão com a base de dados.", 500

    if request.method == 'POST':
        # Verifica a senha de admin
        if request.form.get('admin_password') != ADMIN_PASSWORD:
            flash('Senha de admin incorreta!', 'error')
            return redirect(url_for('admin'))

        # Lógica para criar utilizador
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                    (name, email, password_hash)
                )
            conn.commit()
            flash(f'Utilizador {email} criado com sucesso!', 'success')
        except psycopg2.IntegrityError:
            conn.rollback()
            flash(f'O email {email} já existe.', 'error')
        except Exception as e:
            conn.rollback()
            flash(f'Ocorreu um erro: {e}', 'error')

    # Lógica para exibir a página (GET)
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT name, email FROM users ORDER BY created_at DESC")
        users = cur.fetchall()
    conn.close()
    
    return render_template_string(ADMIN_TEMPLATE, users=users)

# --- Ponto de Entrada ---
if __name__ == '__main__':
    app.secret_key = os.urandom(24) # Necessário para as mensagens 'flash'
    init_db()
    # A porta é definida pela variável de ambiente PORT, padrão 5000 para local
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
