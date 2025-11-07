import os
from flask import Flask, render_template, session, request, redirect, url_for, flash, jsonify
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from MySQLdb.cursors import DictCursor
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
hashed = generate_password_hash('12345')
print(hashed)


app = Flask(__name__)


app.secret_key = '!@#$%' 


app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'portfolio_db' 


UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}


mysql = MySQL(app)
bcrypt = Bcrypt(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- RUTE PUBLIK ---
@app.route('/')
def index():
    cur = mysql.connection.cursor(DictCursor) 
    
    cur.execute("SELECT * FROM users ORDER BY id DESC LIMIT 1")
    profile = cur.fetchone()
    
    cur.execute("SELECT * FROM projects ORDER BY id DESC")
    projects = cur.fetchall()  

    cur.execute("SELECT * FROM skills ORDER BY level DESC")
    skills = cur.fetchall()
    cur.close()
    
    return render_template('index.html', 
                           profile=profile, 
                           projects=projects, 
                           skills=skills)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'is_logged_in' in session:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST' and 'inpUsername' in request.form and 'inpPass' in request.form:
        username = request.form['inpUsername']
        passwd_candidate = request.form['inpPass'] 

        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", [username])
        result = cur.fetchone()
        cur.close()

        if result:
            if bcrypt.check_password_hash(result['password'], passwd_candidate):

                session['is_logged_in'] = True
                session['username'] = result['username']
                session['user_id'] = result['id'] 
                flash('Login berhasil!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Password salah', 'danger')
        else:
            flash('Username tidak ditemukan', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear() 
    flash('Anda telah logout', 'success')
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if 'is_logged_in' not in session:
        flash('Harap login terlebih dahulu', 'danger')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT * FROM users WHERE id = %s", [session['user_id']])
    profile = cur.fetchone()
    
    cur.execute("SELECT * FROM projects")
    projects = cur.fetchall()
    
    cur.execute("SELECT * FROM skills")
    skills = cur.fetchall()
    
    cur.close()
    
    return render_template('admin.html', 
                           profile=profile, 
                           projects=projects, 
                           skills=skills)


@app.route('/admin/profile/edit', methods=['POST'])
def edit_profile():
    if 'is_logged_in' not in session:
        return redirect(url_for('login'))
        
    name = request.form.get('name')
    bio = request.form.get('bio')
    
    cur = mysql.connection.cursor()
    
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            

            cur.execute("UPDATE users SET name=%s, bio=%s, photo=%s WHERE id=%s",
                        (name, bio, filename, session['user_id']))
        else:
            cur.execute("UPDATE users SET name=%s, bio=%s WHERE id=%s",
                        (name, bio, session['user_id']))
    
    mysql.connection.commit()
    cur.close()
    flash('Profil berhasil diperbarui.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/project/add', methods=['POST'])
def add_project():
    if 'is_logged_in' not in session:
        return redirect(url_for('login'))

    title = request.form.get('title')
    description = request.form.get('description')
    link = request.form.get('link')
    
    filename = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO projects (title, description, link, image) VALUES (%s, %s, %s, %s)",
                (title, description, link, filename))
    mysql.connection.commit()
    cur.close()
    
    flash('Proyek baru ditambahkan.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/project/<int:id>/delete')
def delete_project(id):
    if 'is_logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT image FROM projects WHERE id = %s", [id])
    project = cur.fetchone()
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT image FROM projects WHERE id = %s", [id])
    project = cur.fetchone()
    if project and project['image']: # <-- PERBAIKAN 1
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], project['image'])) # <-- PERBAIKAN 2
        except OSError:
            pass 
            
    cur.execute("DELETE FROM projects WHERE id = %s", [id])
    mysql.connection.commit()
    cur.close()
    
    flash('Proyek telah dihapus.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/project/<int:id>/edit', methods=['GET'])
def edit_project(id):
    """Menampilkan form edit untuk proyek tertentu."""
    if 'is_logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT * FROM projects WHERE id = %s", [id])
    project = cur.fetchone()
    cur.close()

    if not project:
        flash('Proyek tidak ditemukan.', 'danger')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_project.html', project=project)


@app.route('/admin/project/<int:id>/update', methods=['POST'])
def update_project(id):
    """Memproses data dari form edit."""
    if 'is_logged_in' not in session:
        return redirect(url_for('login'))

    title = request.form.get('title')
    description = request.form.get('description')
    link = request.form.get('link')

    cur = mysql.connection.cursor(DictCursor)

    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cur.execute("""
                UPDATE projects 
                SET title=%s, description=%s, link=%s, image=%s 
                WHERE id=%s
            """, (title, description, link, filename, id))
        else:
            cur.execute("""
                UPDATE projects 
                SET title=%s, description=%s, link=%s 
                WHERE id=%s
            """, (title, description, link, id))
    
    mysql.connection.commit()
    cur.close()

    flash('Proyek berhasil diperbarui.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/skill/add', methods=['POST'])
def add_skill():
    if 'is_logged_in' not in session:
        return redirect(url_for('login'))
        
    name = request.form.get('name')
    level = request.form.get('level')
    icon = request.form.get('icon')
    
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO skills (name, level, icon) VALUES (%s, %s, %s)",
                (name, level, icon))
    mysql.connection.commit()
    cur.close()
    
    flash('Skill baru ditambahkan.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/skill/<int:id>/delete')
def delete_skill(id):
    if 'is_logged_in' not in session:
        return redirect(url_for('login'))
        
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM skills WHERE id = %s", [id])
    mysql.connection.commit()
    cur.close()
    
    flash('Skill telah dihapus.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/skill/<int:id>/edit', methods=['GET'])
def edit_skill(id):
    """Menampilkan form edit untuk skill tertentu."""
    if 'is_logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT * FROM skills WHERE id = %s", [id])
    skill = cur.fetchone()
    cur.close()

    if not skill:
        flash('Skill tidak ditemukan.', 'danger')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_skill.html', skill=skill)

@app.route('/admin/skill/<int:id>/update', methods=['POST'])
def update_skill(id):
    """Memproses data dari form edit skill."""
    if 'is_logged_in' not in session:
        return redirect(url_for('login'))

    name = request.form.get('name')
    level = request.form.get('level')
    icon = request.form.get('icon')

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE skills 
        SET name=%s, level=%s, icon=%s 
        WHERE id=%s
    """, (name, level, icon, id))
    
    mysql.connection.commit()
    cur.close()

    flash('Skill berhasil diperbarui.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/api/projects')
def api_projects():
    cur = mysql.connection.cursor(DictCursor)
    cur.execute("SELECT * FROM projects")
    projects = cur.fetchall()
    cur.close()
    return jsonify(projects)

@app.route('/api/create_user', methods=['POST'])
def api_create_user():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password') 

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    cur = mysql.connection.cursor()
    try:
        cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                    (username, email, hashed_password))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "User created successfully"}), 201
    except Exception as e:
        cur.close()
        return jsonify({"error": str(e)}), 400

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'is_logged_in' in session:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        bio = request.form.get('bio')
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        try:
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO users (username, email, password, name, bio) VALUES (%s, %s, %s, %s, %s)",
                (username, email, hashed_password, name, bio)
            )
            mysql.connection.commit()
            cur.close()
            
            flash('Akun admin berhasil dibuat! Silakan login.', 'success')
            return redirect(url_for('login'))
        
        except Exception as e:
            if 'Duplicate entry' in str(e):
                flash('Error: Username atau Email sudah terdaftar.', 'danger')
            else:
                flash(f'Terjadi error: {e}', 'danger')
            return redirect(url_for('register')) 

    return render_template('register.html')

if __name__ == '__main__':
    app.run(debug=True)