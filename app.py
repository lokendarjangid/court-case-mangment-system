import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# PostgreSQL configuration
db = psycopg2.connect(
    host="ep-wild-snow-a4i15u74-pooler.us-east-1.aws.neon.tech",
    user="default",
    password="W0SB7gqQGMdb",
    dbname="verceldb",
    sslmode="require"  # Ensure SSL is enabled
)

# Set up cursor
cursor = db.cursor()

def initialize_db():
    # Create users table if it does not exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            role VARCHAR(10) CHECK (role IN ('admin', 'lawyer', 'client')),
            email VARCHAR(100) NOT NULL
        )
    """)

    # Create cases table if it does not exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id SERIAL PRIMARY KEY,
            case_name VARCHAR(255) NOT NULL,
            client_id INT REFERENCES users(id),
            lawyer_id INT REFERENCES users(id),
            court_date DATE NOT NULL,
            status VARCHAR(50) NOT NULL
        )
    """)

    # Create documents table if it does not exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            case_id INT REFERENCES cases(id),
            file_path VARCHAR(255) NOT NULL,
            upload_date DATE DEFAULT CURRENT_DATE
        )
    """)

    # Insert default admin user if not already present
    cursor.execute("""
        INSERT INTO users (username, password, role, email)
        SELECT 'admin', 'admin', 'admin', 'admin@gmail.com'
        WHERE NOT EXISTS (
            SELECT 1 FROM users WHERE username = 'admin'
        )
    """)

    db.commit()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session and session['role'] == 'admin':  # Only admin can register new users
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            email = request.form['email']
            role = request.form['role']

            # Check if the username already exists
            cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                return "Username already taken."

            # Insert new user
            cursor.execute("INSERT INTO users (username, password, email, role) VALUES (%s, %s, %s, %s)",
                           (username, password, email, role))
            db.commit()

            return redirect(url_for('dashboard'))

        return render_template('register.html')
    else:
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user[0]
            session['role'] = user[3]
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect(url_for('login'))


@app.route('/cases/create', methods=['GET', 'POST'])
def create_case():
    if request.method == 'POST':
        case_name = request.form['case_name']
        client_id = request.form['client_id']
        lawyer_id = request.form['lawyer_id']
        court_date = request.form['court_date']
        status = request.form['status']
        cursor.execute("INSERT INTO cases (case_name, client_id, lawyer_id, court_date, status) VALUES (%s, %s, %s, %s, %s)",
                       (case_name, client_id, lawyer_id, court_date, status))
        db.commit()
        return redirect(url_for('dashboard'))
    return render_template('create_case.html')


@app.route('/upload/<int:case_id>', methods=['GET', 'POST'])
def upload(case_id):
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cursor.execute("INSERT INTO documents (case_id, file_path, upload_date) VALUES (%s, %s, NOW())",
                           (case_id, filename))
            db.commit()
            return redirect(url_for('dashboard'))
    return render_template('upload.html', case_id=case_id)

@app.route('/show_documents/<int:case_id>', methods=['GET', 'POST'])
def show_documents(case_id):
    cursor.execute("SELECT * FROM documents WHERE case_id=%s", (case_id,))
    documents = cursor.fetchall()
    return render_template('show_documents.html', case_id=case_id, documents=documents)

@app.route('/delete_case/<int:case_id>', methods=['GET', 'POST'])
def delete_case(case_id):
    cursor.execute("DELETE FROM cases WHERE id=%s", (case_id,))
    db.commit()
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        user_role = session['role']
        user_id = session['user_id']
        if user_role == 'admin':
            cursor.execute("SELECT * FROM cases")
        elif user_role == 'lawyer':
            cursor.execute("SELECT * FROM cases WHERE lawyer_id = %s", (user_id,))
        elif user_role == 'client':
            cursor.execute("SELECT * FROM cases WHERE client_id = %s", (user_id,))
        
        cases = cursor.fetchall()
        return render_template('dashboard.html', cases=cases, role=user_role, user_id=user_id)
    else:
        return redirect(url_for('login'))


@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        search_term = request.form['search_term']
        cursor.execute("SELECT * FROM cases WHERE case_name ILIKE %s", ("%" + search_term + "%",))
        cases = cursor.fetchall()
        return render_template('search_results.html', cases=cases)
    return render_template('search.html')


if __name__ == '__main__':
    # Initialize the database
    initialize_db()
    app.run(debug=True)
