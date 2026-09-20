from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import os, sqlite3
from datetime import datetime, timedelta
import random
import hashlib
import secrets
import re
from difflib import SequenceMatcher
from functools import wraps

app = Flask(__name__)
app.secret_key = "musicwave_secret_key_2025"
app.permanent_session_lifetime = timedelta(days=30)

# === Konfigurasi folder upload ===
UPLOAD_SONG_FOLDER = 'static/uploads/songs'
UPLOAD_COVER_FOLDER = 'static/uploads/covers'
UPLOAD_PODCAST_FOLDER = 'static/uploads/podcasts'
UPLOAD_PODCAST_COVER = 'static/uploads/podcast_covers'
UPLOAD_PLAYLIST_COVER = 'static/uploads/playlist_covers'
UPLOAD_AVATAR_FOLDER = 'static/uploads/avatars'
DATABASE = 'musicwave.db'

# Pastikan semua folder ada
for folder in [UPLOAD_SONG_FOLDER, UPLOAD_COVER_FOLDER, UPLOAD_PODCAST_FOLDER, UPLOAD_PODCAST_COVER, UPLOAD_PLAYLIST_COVER, UPLOAD_AVATAR_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# === Database helper ===
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# === Authentication helpers ===
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(password, hashed):
    return hash_password(password) == hashed

def generate_session_token():
    return secrets.token_urlsafe(32)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('⚠️ Silakan login untuk mengakses halaman ini.', 'info')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('⚠️ Silakan login untuk mengakses halaman ini.', 'info')
            return redirect(url_for('login', next=request.url))
        
        user = get_current_user()
        if not user or user['username'] != 'admin':
            flash('❌ Akses ditolak. Halaman untuk admin saja.', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    if 'user_id' in session:
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
            return user
    return None

def delete_song_data(conn, song):
    """Remove a song's relations, database row, and uploaded files."""
    song_id = song['id']
    conn.execute("DELETE FROM playlist_songs WHERE song_id = ?", (song_id,))
    conn.execute("DELETE FROM liked_songs WHERE song_id = ?", (song_id,))
    conn.execute("DELETE FROM user_plays WHERE song_id = ?", (song_id,))
    conn.execute("DELETE FROM song_genres WHERE song_id = ?", (song_id,))
    conn.execute("DELETE FROM songs WHERE id = ?", (song_id,))

    for folder, filename in ((UPLOAD_SONG_FOLDER, song['song_file']),
                             (UPLOAD_COVER_FOLDER, song['cover_file'])):
        if filename:
            file_path = os.path.join(folder, os.path.basename(filename))
            if os.path.isfile(file_path):
                os.remove(file_path)


def delete_podcast_data(conn, podcast):
    """Remove a podcast's relations, database row, and uploaded files."""
    podcast_id = podcast['id']
    conn.execute("DELETE FROM user_podcasts WHERE podcast_id = ?", (podcast_id,))
    conn.execute("DELETE FROM podcasts WHERE id = ?", (podcast_id,))

    for folder, filename in ((UPLOAD_PODCAST_FOLDER, podcast['audio_file']),
                             (UPLOAD_PODCAST_COVER, podcast['cover_file'])):
        if filename:
            file_path = os.path.join(folder, os.path.basename(filename))
            if os.path.isfile(file_path):
                os.remove(file_path)

def normalize_search_text(value):
    """Normalize text so small spelling and spacing mistakes can be compared."""
    return re.sub(r'[^a-z0-9]+', ' ', (value or '').lower()).strip()

def song_title_similarity(query, title):
    normalized_query = normalize_search_text(query)
    normalized_title = normalize_search_text(title)
    if not normalized_query or not normalized_title:
        return 0

    whole_title_score = SequenceMatcher(None, normalized_query, normalized_title).ratio()
    compact_title_score = SequenceMatcher(
        None, normalized_query.replace(' ', ''), normalized_title.replace(' ', '')
    ).ratio()
    query_words = normalized_query.split()
    title_words = normalized_title.split()
    word_score = sum(
        max(SequenceMatcher(None, query_word, title_word).ratio() for title_word in title_words)
        for query_word in query_words
    ) / len(query_words)

    return max(whole_title_score, compact_title_score, word_score * 0.9)

def is_admin():
    user = get_current_user()
    return user and user['username'] == 'admin'

def init_db():
    with get_db() as conn:
        # Table users
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT,
                avatar TEXT,
                created_at TEXT,
                is_premium INTEGER DEFAULT 0
            )
        """)
        
        # Table user_sessions (untuk remember me)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Table lagu
        conn.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                genre TEXT,
                description TEXT,
                song_file TEXT,
                cover_file TEXT,
                uploaded_at TEXT,
                status TEXT DEFAULT 'pending',
                plays INTEGER DEFAULT 0,
                last_played_at TEXT,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Table podcast
        conn.execute("""
            CREATE TABLE IF NOT EXISTS podcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                host TEXT NOT NULL,
                category TEXT,
                description TEXT,
                audio_file TEXT,
                cover_file TEXT,
                uploaded_at TEXT,
                status TEXT DEFAULT 'pending',
                plays INTEGER DEFAULT 0,
                last_played_at TEXT,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Table user_podcasts (library)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_podcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                podcast_id INTEGER NOT NULL,
                added_at TEXT,
                FOREIGN KEY (podcast_id) REFERENCES podcasts (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Table playlists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                cover_file TEXT,
                created_at TEXT,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Table playlist_songs (many-to-many)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                song_id INTEGER NOT NULL,
                added_at TEXT,
                FOREIGN KEY (playlist_id) REFERENCES playlists (id),
                FOREIGN KEY (song_id) REFERENCES songs (id)
            )
        """)

        # Table untuk track user plays
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_plays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                song_id INTEGER NOT NULL,
                played_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (song_id) REFERENCES songs (id),
                UNIQUE(user_id, song_id)
            )
        """)

        # Insert default admin user jika belum ada
        existing_admin = conn.execute("SELECT 1 FROM users WHERE username = 'admin'").fetchone()
        if not existing_admin:
            hashed_pw = hash_password('admin123')
            conn.execute("""
                INSERT INTO users (username, email, password, full_name, created_at, is_premium)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ('admin', 'admin@musicwave.com', hashed_pw, 'Administrator', datetime.now().isoformat(), 1))
        
        # Table genres
        conn.execute("""
            CREATE TABLE IF NOT EXISTS genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT DEFAULT '#666666'
            )
        """)

        # Table song_genres (many-to-many)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS song_genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER NOT NULL,
                genre_id INTEGER NOT NULL,
                FOREIGN KEY (song_id) REFERENCES songs (id),
                FOREIGN KEY (genre_id) REFERENCES genres (id)
            )
        """)

        # Insert default genres dengan warna
        default_genres = [
            ('Pop', '#ff004c'),
            ('Rock', '#ff6b00'),
            ('Pop Rock', '#00c4ff'),
            ('Soft Rock', '#22c55e'),
            ('R&B', '#a855f7'),
            ('Jazz', '#facc15'),
            ('Dangdut', '#ef4444'),
            ('Hip-Hop', '#ec4899'),
            ('K-Pop', '#3b82f6'),
            ('Indie', '#10b981'),
            ('Electronic', '#f97316'),
            ('Classical', '#e11d48')
        ]

        for genre_name, color in default_genres:
            conn.execute("INSERT OR IGNORE INTO genres (name, color) VALUES (?, ?)", (genre_name, color))


         # Table user_settings
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                theme TEXT DEFAULT 'light',
                language TEXT DEFAULT 'id',
                notifications BOOLEAN DEFAULT 1,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Di bagian init_db(), tambahkan kolom lyrics:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            genre TEXT,
            description TEXT,
            lyrics TEXT,  -- TAMBAH INI
            song_file TEXT,
            cover_file TEXT,
            uploaded_at TEXT,
            status TEXT DEFAULT 'pending',
            plays INTEGER DEFAULT 0,
            last_played_at TEXT,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)

        # Table artists (untuk user yang menjadi artis)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                stage_name TEXT NOT NULL,
                bio TEXT,
                is_verified INTEGER DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Table user_followed_artists (many-to-many)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_followed_artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                artist_id INTEGER NOT NULL,
                followed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (artist_id) REFERENCES artists (id),
                UNIQUE(user_id, artist_id)
            )
        """)

        # Table liked_songs (untuk liked songs feature)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS liked_songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                song_id INTEGER NOT NULL,
                liked_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (song_id) REFERENCES songs (id),
                UNIQUE(user_id, song_id)
            )
        """)
                
        conn.commit()

def migrate_existing_genres():
    """Migrate existing genre data to new structure"""
    with get_db() as conn:
        # Ambil semua songs yang memiliki genre
        songs_with_genres = conn.execute("""
            SELECT id, genre FROM songs WHERE genre IS NOT NULL AND genre != ''
        """).fetchall()
        
        for song in songs_with_genres:
            if song['genre']:
                # Split genre by comma and process each
                genre_list = [g.strip() for g in song['genre'].split(',')]
                
                for genre_name in genre_list:
                    if genre_name:
                        # Cari atau buat genre
                        genre_row = conn.execute("SELECT id FROM genres WHERE name = ?", (genre_name,)).fetchone()
                        if not genre_row:
                            # Buat genre baru dengan warna random
                            colors = ["#ff004c", "#ff6b00", "#00c4ff", "#22c55e", "#a855f7", 
                                     "#facc15", "#ef4444", "#ec4899", "#3b82f6", "#10b981"]
                            color = random.choice(colors)
                            cursor = conn.execute("INSERT INTO genres (name, color) VALUES (?, ?)", 
                                                (genre_name, color))
                            genre_id = cursor.lastrowid
                        else:
                            genre_id = genre_row['id']
                        
                        # Insert relation
                        conn.execute("INSERT OR IGNORE INTO song_genres (song_id, genre_id) VALUES (?, ?)", 
                                    (song['id'], genre_id))
        
        conn.commit()
        print(f"✅ Migrated {len(songs_with_genres)} songs to new genre system")

def migrate_database():
    """Migrate database schema for columns added after the initial release."""
    with get_db() as conn:
        # Tambahkan bio untuk profile yang dibuat sebelum fitur bio tersedia.
        try:
            conn.execute("SELECT bio FROM users LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE users ADD COLUMN bio TEXT")

        # Tambahkan lyrics untuk database lama yang dibuat sebelum fitur lirik.
        try:
            conn.execute("SELECT lyrics FROM songs LIMIT 1")
            print("✅ songs table already has lyrics column")
        except sqlite3.OperationalError:
            print("🔄 Adding lyrics column to songs table...")
            conn.execute("ALTER TABLE songs ADD COLUMN lyrics TEXT")

        # Cek apakah kolom user_id sudah ada di tabel songs
        try:
            conn.execute("SELECT user_id FROM songs LIMIT 1")
            print("✅ songs table already has user_id column")
        except sqlite3.OperationalError:
            # Tambahkan kolom user_id ke tabel songs
            print("🔄 Adding user_id column to songs table...")
            conn.execute("ALTER TABLE songs ADD COLUMN user_id INTEGER")
            # Set user_id untuk data yang sudah ada (assign ke admin)
            admin_user = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
            if admin_user:
                conn.execute("UPDATE songs SET user_id = ? WHERE user_id IS NULL", (admin_user['id'],))
        
        # Cek apakah kolom user_id sudah ada di tabel podcasts
        try:
            conn.execute("SELECT user_id FROM podcasts LIMIT 1")
            print("✅ podcasts table already has user_id column")
        except sqlite3.OperationalError:
            # Tambahkan kolom user_id ke tabel podcasts
            print("🔄 Adding user_id column to podcasts table...")
            conn.execute("ALTER TABLE podcasts ADD COLUMN user_id INTEGER")
            # Set user_id untuk data yang sudah ada (assign ke admin)
            admin_user = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
            if admin_user:
                conn.execute("UPDATE podcasts SET user_id = ? WHERE user_id IS NULL", (admin_user['id'],))
        
        # Cek apakah kolom user_id sudah ada di tabel user_podcasts
        try:
            conn.execute("SELECT user_id FROM user_podcasts LIMIT 1")
            print("✅ user_podcasts table already has user_id column")
        except sqlite3.OperationalError:
            # Tambahkan kolom user_id ke tabel user_podcasts
            print("🔄 Adding user_id column to user_podcasts table...")
            conn.execute("ALTER TABLE user_podcasts ADD COLUMN user_id INTEGER")
            # Set user_id untuk data yang sudah ada (assign ke admin)
            admin_user = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
            if admin_user:
                conn.execute("UPDATE user_podcasts SET user_id = ? WHERE user_id IS NULL", (admin_user['id'],))
        
        # Cek apakah kolom user_id sudah ada di tabel playlists
        try:
            conn.execute("SELECT user_id FROM playlists LIMIT 1")
            print("✅ playlists table already has user_id column")
        except sqlite3.OperationalError:
            # Tambahkan kolom user_id ke tabel playlists
            print("🔄 Adding user_id column to playlists table...")
            conn.execute("ALTER TABLE playlists ADD COLUMN user_id INTEGER")
            # Set user_id untuk data yang sudah ada (assign ke admin)
            admin_user = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
            if admin_user:
                conn.execute("UPDATE playlists SET user_id = ? WHERE user_id IS NULL", (admin_user['id'],))
        
        conn.commit()
        print("✅ Database migration completed!")

# Initialize database
init_db()
migrate_database()
migrate_existing_genres()

# Auto-login dengan remember me
@app.before_request
def check_remember_me():
    if 'user_id' not in session and request.cookies.get('remember_token'):
        remember_token = request.cookies.get('remember_token')
        with get_db() as conn:
            session_data = conn.execute("""
                SELECT u.* FROM user_sessions us 
                JOIN users u ON us.user_id = u.id 
                WHERE us.session_token = ? AND us.expires_at > ?
            """, (remember_token, datetime.now().isoformat())).fetchone()
            
            if session_data:
                session['user_id'] = session_data['id']
                session['username'] = session_data['username']
                session.permanent = True

# =====================================================
# =================== FUNGSI REKOMENDASI ==============
# =====================================================

def get_personal_recommendations(user_id):
    """Mendapatkan rekomendasi personal berdasarkan riwayat putar user"""
    with get_db() as conn:
        try:
            # Ambil genre dari lagu yang sering diputar user
            favorite_genres = conn.execute("""
                SELECT g.id, g.name, COUNT(*) as play_count
                FROM songs s
                JOIN song_genres sg ON s.id = sg.song_id
                JOIN genres g ON sg.genre_id = g.id
                WHERE s.id IN (
                    SELECT song_id FROM (
                        SELECT song_id, COUNT(*) as play_count 
                        FROM user_plays 
                        WHERE user_id = ? 
                        GROUP BY song_id 
                        ORDER BY play_count DESC 
                        LIMIT 10
                    )
                )
                GROUP BY g.id, g.name
                ORDER BY play_count DESC
                LIMIT 5
            """, (user_id,)).fetchall()
            
            # Jika tidak ada riwayat, berikan rekomendasi umum
            if not favorite_genres:
                return conn.execute("""
                    SELECT DISTINCT s.* 
                    FROM songs s
                    WHERE s.status='approved'
                    ORDER BY s.plays DESC, s.uploaded_at DESC
                    LIMIT 12
                """).fetchall()
            
            # Ambil lagu dengan genre yang sama
            genre_ids = [g['id'] for g in favorite_genres]
            placeholders = ','.join('?' * len(genre_ids))
            
            recommendations = conn.execute(f"""
                SELECT DISTINCT s.*
                FROM songs s
                JOIN song_genres sg ON s.id = sg.song_id
                WHERE s.status='approved'
                AND sg.genre_id IN ({placeholders})
                AND s.id NOT IN (
                    SELECT song_id FROM user_plays WHERE user_id = ?
                )
                ORDER BY s.plays DESC, s.uploaded_at DESC
                LIMIT 12
            """, genre_ids + [user_id]).fetchall()
            
            return recommendations
        except sqlite3.OperationalError:
            # Jika ada error, return rekomendasi umum
            return conn.execute("""
                SELECT DISTINCT s.* 
                FROM songs s
                WHERE s.status='approved'
                ORDER BY s.plays DESC, s.uploaded_at DESC
                LIMIT 12
            """).fetchall()

def get_user_frequently_played(user_id):
    """Mendapatkan lagu yang sering diputar oleh user"""
    with get_db() as conn:
        try:
            return conn.execute("""
                SELECT s.*, COUNT(up.song_id) as play_count
                FROM user_plays up
                JOIN songs s ON up.song_id = s.id
                WHERE up.user_id = ? AND s.status='approved'
                GROUP BY up.song_id
                ORDER BY play_count DESC
                LIMIT 8
            """, (user_id,)).fetchall()
        except sqlite3.OperationalError:
            # Jika tabel user_plays belum ada, return empty list
            return []

def get_trending_songs():
    """Mendapatkan lagu trending (30 hari terakhir)"""
    one_month_ago = datetime.now() - timedelta(days=30)
    with get_db() as conn:
        return conn.execute("""
            SELECT DISTINCT s.*
            FROM songs s
            WHERE s.status='approved'
            AND s.last_played_at IS NOT NULL
            AND s.last_played_at >= ?
            ORDER BY s.plays DESC, s.last_played_at DESC
            LIMIT 8
        """, (one_month_ago.isoformat(),)).fetchall()

def get_latest_songs():
    """Mendapatkan lagu terbaru"""
    with get_db() as conn:
        return conn.execute("""
            SELECT DISTINCT s.*
            FROM songs s
            WHERE s.status='approved'
            ORDER BY s.uploaded_at DESC
            LIMIT 8
        """).fetchall()

def get_popular_podcasts():
    """Mendapatkan podcast populer"""
    with get_db() as conn:
        return conn.execute("""
            SELECT * FROM podcasts
            WHERE status='approved'
            ORDER BY plays DESC, uploaded_at DESC
            LIMIT 6
        """).fetchall()
    
    

# =====================================================
# =================== AUTH ROUTES =====================
# =====================================================

# Context processor untuk membuat current_user available di semua template
@app.context_processor
def inject_user():
    return dict(current_user=get_current_user())

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Jika sudah login, redirect ke home sesuai role
    if 'user_id' in session:
        print("✅ User sudah login, redirect sesuai role")
        if is_admin():
            return redirect(url_for('admin_songs'))
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        print("📨 Login form submitted")
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        remember_me = request.form.get('remember_me') == 'true'
        
        print(f"🔑 Login attempt - Username: {username}, Remember: {remember_me}")
        
        if not username or not password:
            flash('❌ Username dan password harus diisi.', 'error')
            return render_template('auth/login.html', title="Login")
        
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", 
                               (username, username)).fetchone()
            
            if user:
                print(f"👤 User found: {user['username']}")
                if check_password(password, user['password']):
                    print("✅ Password correct, logging in...")
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    
                    # Handle remember me
                    if remember_me:
                        session.permanent = True
                        session_token = generate_session_token()
                        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
                        conn.execute("INSERT INTO user_sessions (user_id, session_token, expires_at) VALUES (?, ?, ?)",
                                    (user['id'], session_token, expires_at))
                        conn.commit()
                        
                        # Redirect berdasarkan role
                        if user['username'] == 'admin':
                            response = redirect(url_for('admin_songs'))
                            flash('🎉 Login berhasil! Selamat datang Admin.', 'success')
                        else:
                            response = redirect(url_for('index'))
                            flash('🎉 Login berhasil! Selamat datang di MusicWave.', 'success')
                        
                        response.set_cookie('remember_token', session_token, max_age=30*24*60*60)
                        print("🔐 Remember me enabled, redirecting...")
                        return response
                    
                    # Redirect berdasarkan role tanpa remember me
                    if user['username'] == 'admin':
                        flash('🎉 Login berhasil! Selamat datang Admin.', 'success')
                        print("✅ Admin login successful, redirecting to admin...")
                        return redirect(url_for('admin_songs'))
                    else:
                        flash('🎉 Login berhasil! Selamat datang di MusicWave.', 'success')
                        print("✅ User login successful, redirecting to index...")
                        return redirect(url_for('index'))
                else:
                    print("❌ Password incorrect")
                    flash('❌ Username/email atau password salah.', 'error')
            else:
                print("❌ User not found")
                flash('❌ Username/email atau password salah.', 'error')
    
    return render_template('auth/login.html', title="Login")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        if is_admin():
            return redirect(url_for('admin_songs'))
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        full_name = request.form.get('full_name', '')
        
        # Validasi
        if password != confirm_password:
            flash('❌ Password dan konfirmasi password tidak cocok.', 'error')
            return redirect(url_for('register'))
        
        if len(password) < 6:
            flash('❌ Password harus minimal 6 karakter.', 'error')
            return redirect(url_for('register'))
        
        with get_db() as conn:
            # Cek apakah username/email sudah ada
            existing_user = conn.execute(
                "SELECT 1 FROM users WHERE username = ? OR email = ?", 
                (username, email)
            ).fetchone()
            
            if existing_user:
                flash('❌ Username atau email sudah terdaftar.', 'error')
                return redirect(url_for('register'))
            
            # Insert user baru
            hashed_pw = hash_password(password)
            conn.execute("""
                INSERT INTO users (username, email, password, full_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (username, email, hashed_pw, full_name, datetime.now().isoformat()))
            conn.commit()
            
            flash('🎉 Registrasi berhasil! Silakan login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('auth/register.html', title="Register")

@app.route('/test-db')
def test_db():
    """Route untuk test koneksi database dan data user"""
    with get_db() as conn:
        users = conn.execute("SELECT id, username, email FROM users").fetchall()
        result = "Users in database:<br>"
        for user in users:
            result += f"ID: {user['id']}, Username: {user['username']}, Email: {user['email']}<br>"
        
        # Test password admin
        admin_user = conn.execute("SELECT password FROM users WHERE username = 'admin'").fetchone()
        if admin_user:
            result += f"<br>Admin password hash: {admin_user['password']}<br>"
            result += f"Password 'admin123' matches: {check_password('admin123', admin_user['password'])}"
        
        return result
    
@app.route('/create-test-user')
def create_test_user():
    """Route untuk membuat user test"""
    with get_db() as conn:
        # Cek apakah user test sudah ada
        existing = conn.execute("SELECT 1 FROM users WHERE username = 'testuser'").fetchone()
        if not existing:
            hashed_pw = hash_password('test123')
            conn.execute("""
                INSERT INTO users (username, email, password, full_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, ('testuser', 'test@musicwave.com', hashed_pw, 'Test User', datetime.now().isoformat()))
            conn.commit()
            return "User testuser created with password: test123"
        else:
            return "User testuser already exists"

@app.route('/create-admin-test')
def create_admin_test():
    """Route untuk membuat user admin test"""
    with get_db() as conn:
        # Cek apakah user admin2 sudah ada
        existing = conn.execute("SELECT 1 FROM users WHERE username = 'admin2'").fetchone()
        if not existing:
            hashed_pw = hash_password('admin123')
            conn.execute("""
                INSERT INTO users (username, email, password, full_name, created_at, is_premium)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ('admin2', 'admin2@musicwave.com', hashed_pw, 'Admin Test', datetime.now().isoformat(), 1))
            conn.commit()
            return "User admin2 created with password: admin123"
        else:
            return "User admin2 already exists"

@app.route('/migrate-db')
def manual_migrate():
    """Route untuk manual migration (debug purposes)"""
    try:
        migrate_database()
        return "✅ Database migration completed successfully!"
    except Exception as e:
        return f"❌ Migration failed: {str(e)}"

# === Route logout yang benar (pastikan hanya ada satu) ===
@app.route('/logout')
def logout():
    # Hapus session token dari cookie dan database
    remember_token = request.cookies.get('remember_token')
    if remember_token:
        with get_db() as conn:
            conn.execute("DELETE FROM user_sessions WHERE session_token = ?", (remember_token,))
            conn.commit()
    
    session.clear()
    flash('👋 Anda telah logout.', 'info')
    return redirect(url_for('index'))


# =====================================================
# =================== USER ROUTES =====================
# =====================================================

@app.route('/')
def index():
    user_id = session.get('user_id')
    
    with get_db() as conn:
        # Data untuk semua user
        trending_songs = get_trending_songs()
        latest_songs = get_latest_songs()
        popular_podcasts = get_popular_podcasts()
        
        # Data khusus user yang login
        personal_recommendations = []
        frequently_played = []
        user_playlists = []
        
        if user_id:
            personal_recommendations = get_personal_recommendations(user_id)
            frequently_played = get_user_frequently_played(user_id)
            user_playlists = conn.execute("""
                SELECT * FROM playlists 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 5
            """, (user_id,)).fetchall()
        else:
            # Untuk guest, ambil playlist public/random
            user_playlists = conn.execute("""
                SELECT * FROM playlists 
                ORDER BY created_at DESC 
                LIMIT 5
            """).fetchall()

    return render_template('user/index.html', 
                         title="Dashboard",
                         trending_songs=trending_songs,
                         latest_songs=latest_songs,
                         popular_podcasts=popular_podcasts,
                         personal_recommendations=personal_recommendations,
                         frequently_played=frequently_played,
                         playlists=user_playlists,
                         user_id=user_id,
                         active_page='dashboard')

@app.route('/library')
@login_required
def library():
    user_id = session['user_id']
    with get_db() as conn:
        liked_songs_count = conn.execute(
            "SELECT COUNT(*) AS count FROM liked_songs WHERE user_id = ?",
            (user_id,)
        ).fetchone()['count']
        podcasts = conn.execute("""
            SELECT p.*
            FROM podcasts p
            JOIN user_podcasts up ON p.id = up.podcast_id
            WHERE up.user_id = ?
            ORDER BY up.added_at DESC
        """, (user_id,)).fetchall()

        playlists = conn.execute("""
            SELECT * FROM playlists 
            WHERE user_id = ? 
            ORDER BY id DESC
        """, (user_id,)).fetchall()
        
        # Get user's followed artists
        followed_artists = get_user_followed_artists(user_id)
        
        # Check if user is already an artist
        is_artist = conn.execute(
            "SELECT 1 FROM artists WHERE user_id = ?", (user_id,)
        ).fetchone()

    return render_template('user/library.html', 
                         title="Library", 
                         podcasts=podcasts, 
                         playlists=playlists,
                         liked_songs_count=liked_songs_count,
                         followed_artists=followed_artists,
                         is_artist=bool(is_artist),
                         active_page='library')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('⚠️ Silakan login untuk mengakses profile.', 'info')
        return redirect(url_for('login'))
    
    user = get_current_user()
    if not user:
        flash('❌ User tidak ditemukan.', 'error')
        return redirect(url_for('login'))
    
    try:
        # Get user stats
        with get_db() as conn:
            # Hitung jumlah playlist
            playlist_count = conn.execute("""
                SELECT COUNT(*) as count FROM playlists WHERE user_id = ?
            """, (user['id'],)).fetchone()['count']
            
            # Hitung jumlah lagu yang diupload
            songs_count = conn.execute("""
                SELECT COUNT(*) as count FROM songs WHERE user_id = ?
            """, (user['id'],)).fetchone()['count']
            
            # Hitung jumlah podcast yang diupload
            podcasts_count = conn.execute("""
                SELECT COUNT(*) as count FROM podcasts WHERE user_id = ?
            """, (user['id'],)).fetchone()['count']
            
            # Ambil playlist user
            playlists = conn.execute("""
                SELECT * FROM playlists 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            """, (user['id'],)).fetchall()

            # Ambil lagu yang diunggah user agar tampil di profil.
            uploaded_songs = conn.execute("""
                SELECT * FROM songs
                WHERE user_id = ?
                ORDER BY uploaded_at DESC
            """, (user['id'],)).fetchall()
        
        return render_template('user/profile.html', title="Profile", 
                             user=user, 
                             playlist_count=playlist_count,
                             songs_count=songs_count,
                             podcasts_count=podcasts_count,
                             playlists=playlists,
                             uploaded_songs=uploaded_songs)
    
    except sqlite3.OperationalError as e:
        print(f"Database error in profile: {e}")
        # Jika masih ada error, tampilkan profile tanpa stats
        return render_template('user/profile.html', title="Profile", 
                             user=user, 
                             playlist_count=0,
                             songs_count=0,
                             podcasts_count=0,
                             playlists=[],
                             uploaded_songs=[])
    
    # === Become Artist ===
@app.route('/become_artist', methods=['GET', 'POST'])
@login_required
def become_artist():
    user_id = session['user_id']
    
    with get_db() as conn:
        # Cek apakah user sudah menjadi artis
        existing_artist = conn.execute(
            "SELECT * FROM artists WHERE user_id = ?", (user_id,)
        ).fetchone()
        
        if existing_artist:
            flash('🎤 Anda sudah terdaftar sebagai artis!', 'info')
            return redirect(url_for('library'))
        
        if request.method == 'POST':
            stage_name = request.form.get('stage_name', '').strip()
            bio = request.form.get('bio', '').strip()
            
            if not stage_name:
                flash('❌ Nama panggung wajib diisi.', 'error')
                return render_template('user/become_artist.html', title="Daftar sebagai Artis")
            
            # Insert sebagai artis
            conn.execute("""
                INSERT INTO artists (user_id, stage_name, bio, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, stage_name, bio, datetime.now().isoformat()))
            conn.commit()
            
            flash('🎉 Selamat! Anda sekarang terdaftar sebagai artis.', 'success')
            return redirect(url_for('library'))
    
    return render_template('user/become_artist.html', title="Daftar sebagai Artis")

# === Follow/Unfollow Artist ===
@app.route('/follow_artist/<int:artist_id>', methods=['POST'])
@login_required
def follow_artist(artist_id):
    user_id = session['user_id']
    
    with get_db() as conn:
        # Cek apakah sudah follow
        existing_follow = conn.execute(
            "SELECT 1 FROM user_followed_artists WHERE user_id = ? AND artist_id = ?",
            (user_id, artist_id)
        ).fetchone()
        
        if existing_follow:
            # Unfollow
            conn.execute(
                "DELETE FROM user_followed_artists WHERE user_id = ? AND artist_id = ?",
                (user_id, artist_id)
            )
            action = 'unfollowed'
        else:
            # Follow
            conn.execute(
                "INSERT INTO user_followed_artists (user_id, artist_id, followed_at) VALUES (?, ?, ?)",
                (user_id, artist_id, datetime.now().isoformat())
            )
            action = 'followed'
        
        conn.commit()
    
    return jsonify({'status': 'success', 'action': action})

# === Get User's Followed Artists ===
def get_user_followed_artists(user_id):
    with get_db() as conn:
        return conn.execute("""
            SELECT a.*, u.username, u.avatar, u.full_name
            FROM artists a
            JOIN users u ON a.user_id = u.id
            JOIN user_followed_artists ufa ON a.id = ufa.artist_id
            WHERE ufa.user_id = ?
            ORDER BY ufa.followed_at DESC
        """, (user_id,)).fetchall()


def get_verified_artists(limit=8, query=None):
    with get_db() as conn:
        sql = """
            SELECT a.*, u.username, u.avatar, u.full_name,
                   (SELECT COUNT(*) FROM user_followed_artists WHERE artist_id = a.id) as follower_count,
                   (SELECT COUNT(*) FROM songs WHERE user_id = a.user_id AND status='approved') as song_count
            FROM artists a
            JOIN users u ON a.user_id = u.id
            WHERE a.is_verified = 1
        """
        params = []

        if query:
            sql += " AND (LOWER(a.stage_name) LIKE ? OR LOWER(u.username) LIKE ? OR LOWER(u.full_name) LIKE ?)"
            q = f"%{query.lower()}%"
            params.extend([q, q, q])

        sql += " ORDER BY follower_count DESC, a.created_at DESC LIMIT ?"
        params.append(limit)

        return conn.execute(sql, params).fetchall()


def get_artist_recommendations(user_id=None, limit=8):
    with get_db() as conn:
        if user_id:
            favorite_genres = conn.execute("""
                SELECT sg.genre_id, COUNT(*) as play_count
                FROM user_plays up
                JOIN songs s ON s.id = up.song_id
                JOIN song_genres sg ON sg.song_id = s.id
                WHERE up.user_id = ?
                GROUP BY sg.genre_id
                ORDER BY play_count DESC
                LIMIT 5
            """, (user_id,)).fetchall()

            if favorite_genres:
                genre_ids = [row['genre_id'] for row in favorite_genres]
                placeholders = ','.join('?' * len(genre_ids))
                query = f"""
                    SELECT DISTINCT a.*, u.username, u.avatar, u.full_name,
                           (SELECT COUNT(*) FROM user_followed_artists WHERE artist_id = a.id) as follower_count,
                           (SELECT COUNT(*) FROM songs WHERE user_id = a.user_id AND status='approved') as song_count
                    FROM artists a
                    JOIN users u ON u.id = a.user_id
                    JOIN songs s ON s.user_id = a.user_id AND s.status = 'approved'
                    JOIN song_genres sg ON sg.song_id = s.id
                    WHERE a.is_verified = 1
                    AND sg.genre_id IN ({placeholders})
                    GROUP BY a.id
                    ORDER BY follower_count DESC, song_count DESC, a.created_at DESC
                    LIMIT ?
                """
                artists = conn.execute(query, genre_ids + [limit]).fetchall()
                if artists:
                    return artists

        return get_verified_artists(limit=limit)

# === Get All Artists ===
def get_all_artists():
    with get_db() as conn:
        return conn.execute("""
            SELECT a.*, u.username, u.avatar, u.full_name,
                   (SELECT COUNT(*) FROM user_followed_artists WHERE artist_id = a.id) as follower_count
            FROM artists a
            JOIN users u ON a.user_id = u.id
            WHERE a.is_verified = 1
            ORDER BY follower_count DESC
        """).fetchall()

# === Artist Detail ===
@app.route('/artist/<int:artist_id>')
def artist_detail(artist_id):
    with get_db() as conn:
        artist = conn.execute("""
            SELECT a.*, u.username, u.avatar, u.full_name, u.email,
                   (SELECT COUNT(*) FROM user_followed_artists WHERE artist_id = a.id) as follower_count,
                   (SELECT COUNT(*) FROM songs WHERE user_id = a.user_id AND status='approved') as song_count
            FROM artists a
            JOIN users u ON a.user_id = u.id
            WHERE a.id = ?
        """, (artist_id,)).fetchone()
        
        if not artist:
            flash('❌ Artis tidak ditemukan.', 'error')
            return redirect(url_for('explore'))
        
        # Get artist's songs
        songs = conn.execute("""
            SELECT * FROM songs 
            WHERE user_id = ? AND status='approved'
            ORDER BY uploaded_at DESC
        """, (artist['user_id'],)).fetchall()
        
        # Check if current user is following this artist
        is_following = False
        if 'user_id' in session:
            follow_check = conn.execute(
                "SELECT 1 FROM user_followed_artists WHERE user_id = ? AND artist_id = ?",
                (session['user_id'], artist_id)
            ).fetchone()
            is_following = bool(follow_check)
    
    return render_template('user/artist_detail.html',
                         artist=artist,
                         songs=songs,
                         is_following=is_following,
                         title=artist['stage_name'])

# === Admin Artists Management ===
@app.route('/admin/artists')
@admin_required
def admin_artists():
    with get_db() as conn:
        artists = conn.execute("""
            SELECT a.*, u.username, u.email, u.full_name, u.created_at as user_joined,
                   (SELECT COUNT(*) FROM user_followed_artists WHERE artist_id = a.id) as follower_count,
                   (SELECT COUNT(*) FROM songs WHERE user_id = a.user_id) as song_count
            FROM artists a
            JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC
        """).fetchall()
    
    return render_template('admin/admin_artists.html', 
                         artists=artists, 
                         title="Admin - Artists Management")

# === Verify Artist ===
@app.route('/admin/verify_artist/<int:artist_id>')
@admin_required
def verify_artist(artist_id):
    with get_db() as conn:
        conn.execute("UPDATE artists SET is_verified = 1 WHERE id = ?", (artist_id,))
        conn.commit()
    
    flash('✅ Artis berhasil diverifikasi!', 'success')
    return redirect(url_for('admin_artists'))

# === Remove Artist ===
@app.route('/admin/remove_artist/<int:artist_id>')
@admin_required
def remove_artist(artist_id):
    with get_db() as conn:
        conn.execute("DELETE FROM artists WHERE id = ?", (artist_id,))
        conn.execute("DELETE FROM user_followed_artists WHERE artist_id = ?", (artist_id,))
        conn.commit()
    
    flash('🗑️ Artis berhasil dihapus!', 'success')
    return redirect(url_for('admin_artists'))
    
#=== Update profile route ===
@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user_id = session['user_id']
    username = request.form.get('username', '').strip()
    full_name = request.form.get('full_name', '').strip()
    avatar_file = request.files.get('avatar')
    
    with get_db() as conn:
        # Cek apakah username sudah digunakan oleh user lain
        existing_user = conn.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?", 
            (username, user_id)
        ).fetchone()
        
        if existing_user:
            flash('❌ Username sudah digunakan.', 'error')
            return redirect(url_for('profile'))
        
        avatar_filename = None
        if avatar_file and avatar_file.filename:
            # Validasi file type
            allowed_extensions = {'jpg', 'jpeg', 'png', 'gif'}
            file_ext = avatar_file.filename.rsplit('.', 1)[1].lower() if '.' in avatar_file.filename else ''
            
            if file_ext not in allowed_extensions:
                flash('❌ Format file tidak didukung. Gunakan JPG, PNG, atau GIF.', 'error')
                return redirect(url_for('profile'))
            
            # Validasi file size (max 2MB)
            avatar_file.seek(0, os.SEEK_END)
            file_size = avatar_file.tell()
            avatar_file.seek(0)
            
            if file_size > 2 * 1024 * 1024:  # 2MB
                flash('❌ Ukuran file terlalu besar. Maksimal 2MB.', 'error')
                return redirect(url_for('profile'))
            
            # Generate filename
            avatar_filename = f"avatar_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_ext}"
            avatar_file.save(os.path.join(UPLOAD_AVATAR_FOLDER, avatar_filename))
            
            # Update dengan avatar baru
            conn.execute("""
                UPDATE users 
                SET username = ?, full_name = ?, avatar = ?
                WHERE id = ?
            """, (username, full_name or None, avatar_filename, user_id))
        else:
            # Update tanpa avatar
            conn.execute("""
                UPDATE users 
                SET username = ?, full_name = ?
                WHERE id = ?
            """, (username, full_name or None, user_id))
        
        conn.commit()
        
        # Update session username jika berubah
        if 'username' in session:
            session['username'] = username
        
        flash('✅ Profile berhasil diperbarui!', 'success')
        return redirect(url_for('profile'))




# === Update Password ===
@app.route('/update_password', methods=['POST'])
@login_required
def update_password():
    user_id = session['user_id']
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    with get_db() as conn:
        user = conn.execute("SELECT password FROM users WHERE id = ?", (user_id,)).fetchone()
        
        if not check_password(current_password, user['password']):
            flash('❌ Password saat ini salah.', 'error')
            return redirect(url_for('settings'))
        
        if new_password != confirm_password:
            flash('❌ Password baru tidak cocok.', 'error')
            return redirect(url_for('settings'))
        
        if len(new_password) < 6:
            flash('❌ Password harus minimal 6 karakter.', 'error')
            return redirect(url_for('settings'))
        
        hashed_new_password = hash_password(new_password)
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_new_password, user_id))
        conn.commit()
    
    flash('✅ Password berhasil diubah!', 'success')
    return redirect(url_for('settings'))

# === Update Settings ===
@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    user_id = session['user_id']
    theme = request.form.get('theme', 'light')
    language = request.form.get('language', 'id')
    notifications = request.form.get('notifications', 'false')
    
    with get_db() as conn:
        # Simpan settings ke database (atau session)
        conn.execute("""
            INSERT OR REPLACE INTO user_settings (user_id, theme, language, notifications, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, theme, language, notifications == 'true', datetime.now().isoformat()))
        conn.commit()
    
    # Simpan di session juga untuk akses cepat
    session['user_theme'] = theme
    session['user_language'] = language
    session['user_notifications'] = notifications == 'true'
    
    flash('✅ Pengaturan berhasil disimpan!', 'success')
    return redirect(url_for('settings'))

# === Delete Account ===
@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user_id = session['user_id']
    confirmation = request.form.get('confirmation')
    
    if confirmation != 'HAPUS':
        flash('❌ Konfirmasi tidak sesuai.', 'error')
        return redirect(url_for('settings'))
    
    with get_db() as conn:
        # Hapus semua data user
        conn.execute("DELETE FROM playlists WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_podcasts WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_plays WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    
    session.clear()
    flash('👋 Akun Anda telah berhasil dihapus.', 'info')
    return redirect(url_for('index'))


@app.route('/settings')
@login_required
def settings():
    return render_template('user/settings.html', title="Settings", active_page='settings')


@app.route('/info/<page>')
def info_page(page):
    pages = {
        'about': {
            'title': 'About MusicWave',
            'heading': 'Tentang MusicWave',
            'content': [
                'MusicWave adalah platform untuk menemukan, mendengarkan, dan membagikan musik serta podcast favorit Anda.',
                'MusicWave dikembangkan oleh Muhammad Faris Naufal.'
            ]
        },
        'support': {
            'title': 'Support - MusicWave',
            'heading': 'Support',
            'content': [
                'Butuh bantuan? Pastikan aplikasi dan koneksi internet Anda berjalan dengan baik, lalu coba muat ulang halaman.',
                'Untuk pertanyaan atau laporan masalah, silakan hubungi tim MusicWave melalui media sosial yang tersedia di footer.'
            ]
        },
        'privacy': {
            'title': 'Privacy - MusicWave',
            'heading': 'Privacy',
            'content': [
                'MusicWave menghargai privasi Anda. Informasi akun digunakan untuk menyediakan fitur login, profil, playlist, dan rekomendasi musik.',
                'Kami tidak menjual data pribadi pengguna kepada pihak lain.'
            ]
        },
        'terms': {
            'title': 'Terms - MusicWave',
            'heading': 'Terms',
            'content': [
                'Gunakan MusicWave secara bertanggung jawab dan hanya unggah konten yang Anda miliki atau berhak gunakan.',
                'Dengan menggunakan MusicWave, Anda menyetujui ketentuan penggunaan layanan ini.'
            ]
        }
    }

    page_data = pages.get(page)
    if not page_data:
        return redirect(url_for('index'))

    return render_template('info.html', active_page=None, **page_data)


@app.route('/explore')
def explore():
    user_id = session.get('user_id')
    with get_db() as conn:
        latest_songs = conn.execute("""
            SELECT DISTINCT s.*
            FROM songs s
            LEFT JOIN song_genres sg ON s.id = sg.song_id
            LEFT JOIN genres g ON sg.genre_id = g.id
            WHERE s.status='approved'
            GROUP BY s.id
            ORDER BY s.uploaded_at DESC
            LIMIT 10
        """).fetchall()

        one_month_ago = datetime.now() - timedelta(days=30)
        trending_songs = conn.execute("""
            SELECT DISTINCT s.*
            FROM songs s
            LEFT JOIN song_genres sg ON s.id = sg.song_id
            LEFT JOIN genres g ON sg.genre_id = g.id
            WHERE s.status='approved'
            AND s.last_played_at IS NOT NULL
            AND s.last_played_at >= ?
            GROUP BY s.id
            ORDER BY s.plays DESC, s.last_played_at DESC
            LIMIT 10
        """, (one_month_ago.isoformat(),)).fetchall()

        podcasts = conn.execute("""
            SELECT * FROM podcasts
            WHERE status='approved'
            ORDER BY uploaded_at DESC
            LIMIT 10
        """).fetchall()

        artists = get_artist_recommendations(user_id=user_id, limit=6)

        genres = conn.execute("SELECT * FROM genres ORDER BY name").fetchall()
        genre_colors = {g['name']: g['color'] for g in genres}

    return render_template(
        'user/explore.html',
        title="Explore",
        latest_songs=latest_songs,
        trending_songs=trending_songs,
        podcasts=podcasts,
        artists=artists,
        genre_colors=genre_colors,
        active_page='explore'
    )

# === ADD PODCAST PAGE ===
@app.route('/add_podcast', methods=['GET', 'POST'])
@login_required
def add_podcast():
    user_id = session['user_id']
    with get_db() as conn:
        podcasts = conn.execute("""
            SELECT * FROM podcasts 
            WHERE status='approved'
            AND id NOT IN (SELECT podcast_id FROM user_podcasts WHERE user_id = ?)
            ORDER BY uploaded_at DESC
        """, (user_id,)).fetchall()

        if request.method == 'POST':
            selected = request.form.getlist('podcast_ids')
            for pid in selected:
                exists = conn.execute("SELECT 1 FROM user_podcasts WHERE podcast_id = ? AND user_id = ?", 
                                     (pid, user_id)).fetchone()
                if not exists:
                    conn.execute("INSERT INTO user_podcasts (user_id, podcast_id, added_at) VALUES (?, ?, ?)",
                                 (user_id, pid, datetime.now().isoformat()))
            conn.commit()
            flash('🎧 Podcast berhasil ditambahkan ke Library!')
            return redirect(url_for('library'))

    return render_template('user/add_podcast.html', podcasts=podcasts, title="Tambah Podcast")

# === Playlist: create, detail, add/remove songs ===
@app.route('/add_playlist', methods=['GET', 'POST'])
@login_required
def add_playlist():
    user_id = session['user_id']
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        cover_file = request.files.get('cover_file')

        if not name:
            flash("Nama playlist wajib diisi.")
            return redirect(url_for('add_playlist'))

        cover_filename = None
        if cover_file and cover_file.filename:
            cover_filename = datetime.now().strftime("%Y%m%d%H%M%S_") + cover_file.filename
            cover_file.save(os.path.join(UPLOAD_PLAYLIST_COVER, cover_filename))

        with get_db() as conn:
            conn.execute("""
                INSERT INTO playlists (name, description, cover_file, created_at, user_id)
                VALUES (?, ?, ?, ?, ?)
            """, (name, description or None, cover_filename, datetime.now().isoformat(), user_id))
            conn.commit()

            # ambil id playlist terbaru
            playlist_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()['id']

        flash("🎶 Playlist berhasil dibuat!")
        return redirect(url_for('playlist_detail', playlist_id=playlist_id))

    return render_template('user/add_playlist.html', title="Buat Playlist")

@app.route('/playlist/<int:playlist_id>', methods=['GET'])
@login_required
def playlist_detail(playlist_id):
    user_id = session['user_id']
    with get_db() as conn:
        # Cek apakah playlist milik user
        playlist = conn.execute("SELECT * FROM playlists WHERE id = ? AND user_id = ?", 
                               (playlist_id, user_id)).fetchone()
        if not playlist:
            flash("Playlist tidak ditemukan atau Anda tidak memiliki akses.")
            return redirect(url_for('library'))

        # Lagu yang sudah masuk playlist
        playlist_songs = conn.execute("""
            SELECT s.* FROM songs s
            JOIN playlist_songs ps ON s.id = ps.song_id
            WHERE ps.playlist_id = ?
            ORDER BY ps.added_at DESC
        """, (playlist_id,)).fetchall()

        # Ambil daftar lagu approved yang belum ada di playlist
        available_songs = conn.execute("""
            SELECT * FROM songs
            WHERE status='approved'
            AND song_file IS NOT NULL
            AND id NOT IN (SELECT song_id FROM playlist_songs WHERE playlist_id = ?)
            ORDER BY uploaded_at DESC
            LIMIT 50
        """, (playlist_id,)).fetchall()

    return render_template('user/playlist_detail.html',
                           playlist=playlist,
                           playlist_songs=playlist_songs,
                           available_songs=available_songs,
                           title=playlist['name'])

# API untuk pencarian lagu real-time
@app.route('/api/search_songs')
@login_required
def api_search_songs():
    query = request.args.get('q', '').strip().lower()
    playlist_id = request.args.get('playlist_id', type=int)
    
    with get_db() as conn:
        if query:
            songs = conn.execute("""
                SELECT * FROM songs
                WHERE status='approved'
                AND song_file IS NOT NULL
                AND (LOWER(title) LIKE ? OR LOWER(artist) LIKE ?)
                AND id NOT IN (SELECT song_id FROM playlist_songs WHERE playlist_id = ?)
                ORDER BY uploaded_at DESC
                LIMIT 20
            """, (f"%{query}%", f"%{query}%", playlist_id)).fetchall()
        else:
            songs = conn.execute("""
                SELECT * FROM songs
                WHERE status='approved'
                AND song_file IS NOT NULL
                AND id NOT IN (SELECT song_id FROM playlist_songs WHERE playlist_id = ?)
                ORDER BY uploaded_at DESC
                LIMIT 20
            """, (playlist_id,)).fetchall()
    
    songs_data = []
    for song in songs:
        songs_data.append({
            'id': song['id'],
            'title': song['title'],
            'artist': song['artist'],
            'cover': url_for('static', filename='uploads/covers/' + (song['cover_file'] or 'default_cover.jpg')),
            'genre': song['genre'] or 'Single',
            'audio_url': url_for('static', filename='uploads/songs/' + song['song_file']) if song['song_file'] else None
        })
    
    return jsonify(songs_data)

# Route untuk get song details dengan lirik
@app.route('/api/song/<int:song_id>')
def get_song_details(song_id):
    with get_db() as conn:
        song = conn.execute("""
            SELECT s.*, 
                   GROUP_CONCAT(g.name) as genres,
                   u.username as uploader
            FROM songs s
            LEFT JOIN song_genres sg ON s.id = sg.song_id
            LEFT JOIN genres g ON sg.genre_id = g.id
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.id = ?
            GROUP BY s.id
        """, (song_id,)).fetchone()
        
        if song:
            return jsonify({
                'id': song['id'],
                'title': song['title'],
                'artist': song['artist'],
                'lyrics': song['lyrics'] or 'Lirik belum tersedia untuk lagu ini.',
                'cover': url_for('static', filename='uploads/covers/' + (song['cover_file'] or 'default_cover.jpg')),
                'genres': song['genres'],
                'plays': song['plays'],
                'uploader': song['uploader'],
                'uploaded_at': song['uploaded_at']
            })
        return jsonify({'error': 'Song not found'}), 404

@app.route('/song/<int:song_id>')
def song_page(song_id):
    with get_db() as conn:
        song = conn.execute("""
            SELECT s.*, GROUP_CONCAT(DISTINCT g.name) AS genres, u.username AS uploader
            FROM songs s
            LEFT JOIN song_genres sg ON s.id = sg.song_id
            LEFT JOIN genres g ON sg.genre_id = g.id
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.id = ? AND s.status = 'approved'
            GROUP BY s.id
        """, (song_id,)).fetchone()

    if not song:
        flash('Lagu tidak ditemukan.', 'error')
        return redirect(url_for('explore'))

    return render_template('user/song_detail.html', song=song, title=song['title'])


# Route edit playlist
@app.route('/playlist/<int:playlist_id>/edit', methods=['POST'])
@login_required
def edit_playlist(playlist_id):
    user_id = session['user_id']
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        cover_file = request.files.get('cover_file')

        with get_db() as conn:
            # Cek kepemilikan playlist
            playlist = conn.execute("SELECT * FROM playlists WHERE id = ? AND user_id = ?", 
                                   (playlist_id, user_id)).fetchone()
            if not playlist:
                flash("Anda tidak memiliki akses ke playlist ini.")
                return redirect(url_for('library'))

            if cover_file and cover_file.filename:
                cover_filename = datetime.now().strftime("%Y%m%d%H%M%S_") + cover_file.filename
                cover_file.save(os.path.join(UPLOAD_PLAYLIST_COVER, cover_filename))
                conn.execute("""
                    UPDATE playlists 
                    SET name = ?, description = ?, cover_file = ?
                    WHERE id = ? AND user_id = ?
                """, (name, description or None, cover_filename, playlist_id, user_id))
            else:
                conn.execute("""
                    UPDATE playlists 
                    SET name = ?, description = ?
                    WHERE id = ? AND user_id = ?
                """, (name, description or None, playlist_id, user_id))
            
            conn.commit()

        flash('✅ Playlist berhasil diperbarui!')
        return redirect(url_for('playlist_detail', playlist_id=playlist_id))

@app.route('/playlist/<int:playlist_id>/add_song', methods=['POST'])
@login_required
def add_song_to_playlist(playlist_id):
    user_id = session['user_id']
    song_id = request.form.get('song_id')
    if not song_id:
        flash("Pilih lagu untuk ditambahkan.")
        return redirect(url_for('playlist_detail', playlist_id=playlist_id))

    with get_db() as conn:
        # Cek kepemilikan playlist
        playlist = conn.execute("SELECT * FROM playlists WHERE id = ? AND user_id = ?", 
                               (playlist_id, user_id)).fetchone()
        if not playlist:
            flash("Anda tidak memiliki akses ke playlist ini.")
            return redirect(url_for('library'))

        exists = conn.execute("SELECT 1 FROM playlist_songs WHERE playlist_id = ? AND song_id = ?", 
                             (playlist_id, song_id)).fetchone()
        if exists:
            flash("Lagu sudah ada di playlist.")
            return redirect(url_for('playlist_detail', playlist_id=playlist_id))

        conn.execute("INSERT INTO playlist_songs (playlist_id, song_id, added_at) VALUES (?, ?, ?)",
                     (playlist_id, song_id, datetime.now().isoformat()))
        conn.commit()

    flash("Lagu berhasil ditambahkan ke playlist.")
    return redirect(url_for('playlist_detail', playlist_id=playlist_id))

@app.route('/playlist/<int:playlist_id>/remove_song', methods=['POST'])
@login_required
def remove_song_from_playlist(playlist_id):
    user_id = session['user_id']
    song_id = request.form.get('song_id')
    if not song_id:
        flash("Tidak ada lagu yang dipilih.")
        return redirect(url_for('playlist_detail', playlist_id=playlist_id))

    with get_db() as conn:
        # Cek kepemilikan playlist
        playlist = conn.execute("SELECT * FROM playlists WHERE id = ? AND user_id = ?", 
                               (playlist_id, user_id)).fetchone()
        if not playlist:
            flash("Anda tidak memiliki akses ke playlist ini.")
            return redirect(url_for('library'))

        conn.execute("DELETE FROM playlist_songs WHERE playlist_id = ? AND song_id = ?", (playlist_id, song_id))
        conn.commit()

    flash("Lagu dihapus dari playlist.")
    return redirect(url_for('playlist_detail', playlist_id=playlist_id))

@app.route('/genre/<genre_name>')
def genre_page(genre_name):
    with get_db() as conn:
        # Cari genre berdasarkan name
        genre = conn.execute("SELECT * FROM genres WHERE name = ?", (genre_name,)).fetchone()
        
        if not genre:
            flash('❌ Genre tidak ditemukan.', 'error')
            return redirect(url_for('explore'))
        
        # Perbaiki query: Gunakan DISTINCT untuk menghindari duplikasi
        songs = conn.execute("""
            SELECT DISTINCT s.* 
            FROM songs s
            JOIN song_genres sg ON s.id = sg.song_id
            WHERE sg.genre_id = ? AND s.status='approved'
            ORDER BY s.uploaded_at DESC
        """, (genre['id'],)).fetchall()
    
    return render_template(
        'user/genre_page.html',
        title=f"{genre_name} Genre",
        genre_name=genre_name,
        songs=songs
    )



@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    suggested_songs = []
    artists = []

    with get_db() as conn:
        if query:
            songs = conn.execute("""
                SELECT DISTINCT s.* 
                FROM songs s
                LEFT JOIN song_genres sg ON s.id = sg.song_id
                WHERE s.status='approved'
                AND (s.title LIKE ? OR s.artist LIKE ?)
                GROUP BY s.id
                ORDER BY s.uploaded_at DESC
            """, (f"%{query}%", f"%{query}%")).fetchall()

            if not songs:
                candidates = conn.execute("""
                    SELECT DISTINCT s.*
                    FROM songs s
                    WHERE s.status = 'approved'
                    AND s.song_file IS NOT NULL
                """).fetchall()
                scored_candidates = [
                    (song_title_similarity(query, song['title']), song)
                    for song in candidates
                ]
                suggested_songs = [
                    song for score, song in sorted(
                        scored_candidates, key=lambda item: item[0], reverse=True
                    )[:5]
                    if score >= 0.45
                ]

            podcasts = conn.execute("""
                SELECT * FROM podcasts
                WHERE status='approved'
                AND (title LIKE ? OR host LIKE ? OR category LIKE ?)
                ORDER BY uploaded_at DESC
            """, (f"%{query}%", f"%{query}%", f"%{query}%")).fetchall()

            artists = get_verified_artists(limit=6, query=query)
            latest_songs = []
            trending_songs = []

        else:
            songs = conn.execute("""
                SELECT DISTINCT s.* 
                FROM songs s
                WHERE s.status='approved'
                GROUP BY s.id
                ORDER BY s.uploaded_at DESC
                LIMIT 10
            """).fetchall()

            one_month_ago = datetime.now() - timedelta(days=30)
            trending_songs = conn.execute("""
                SELECT DISTINCT s.* 
                FROM songs s
                WHERE s.status='approved'
                AND s.last_played_at IS NOT NULL
                AND s.last_played_at >= ?
                GROUP BY s.id
                ORDER BY s.plays DESC, s.last_played_at DESC
                LIMIT 10
            """, (one_month_ago.isoformat(),)).fetchall()

            podcasts = conn.execute("""
                SELECT * FROM podcasts
                WHERE status='approved'
                ORDER BY uploaded_at DESC
                LIMIT 10
            """).fetchall()

            latest_songs = songs
            artists = get_artist_recommendations(user_id=session.get('user_id'), limit=6)

    colors = [
        "#ff004c", "#ff6b00", "#00c4ff", "#22c55e",
        "#a855f7", "#facc15", "#ef4444", "#ec4899",
        "#3b82f6", "#10b981", "#f97316", "#e11d48"
    ]

    genres = ['Pop', 'Rock', 'Pop Rock', 'Soft Rock', 'R&B', 'Jazz', 'Dangdut', 'Hip-Hop', 'K-Pop', 'Indie']
    genre_colors = {g: random.choice(colors) for g in genres}

    return render_template(
        'user/explore.html',
        title=f"Search Results for '{query}'" if query else "Explore",
        query=query,
        songs=songs,
        suggested_songs=suggested_songs,
        latest_songs=latest_songs,
        trending_songs=trending_songs,
        podcasts=podcasts,
        artists=artists,
        genre_colors=genre_colors,
        is_search=bool(query)
    )

# Update upload_song untuk include lyrics
@app.route('/upload_song', methods=['GET', 'POST'])
@login_required
def upload_song():
    user_id = session['user_id']
    
    with get_db() as conn:
        genres = conn.execute("SELECT * FROM genres ORDER BY name").fetchall()
    
    if request.method == 'POST':
        title = request.form['title']
        artist = request.form['artist']
        description = request.form.get('description', '')
        lyrics = request.form.get('lyrics', '')  # TAMBAH INI
        song_file = request.files['song_file']
        cover_file = request.files.get('cover_file')
        selected_genres = request.form.getlist('genres')

        if not selected_genres:
            flash('❌ Pilih minimal satu genre.', 'error')
            return render_template('user/upload_song.html', title="Upload Song", genres=genres)

        song_filename = None
        if song_file and song_file.filename:
            song_filename = datetime.now().strftime("%Y%m%d%H%M%S_") + song_file.filename
            song_file.save(os.path.join(UPLOAD_SONG_FOLDER, song_filename))

        cover_filename = None
        if cover_file and cover_file.filename:
            cover_filename = datetime.now().strftime("%Y%m%d%H%M%S_") + cover_file.filename
            cover_file.save(os.path.join(UPLOAD_COVER_FOLDER, cover_filename))

        with get_db() as conn:
            # Insert song dengan lyrics
            cursor = conn.execute("""
                INSERT INTO songs (title, artist, description, lyrics, song_file, cover_file, uploaded_at, status, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, artist, description, lyrics, song_filename, cover_filename, datetime.now().isoformat(), 'pending', user_id))
            
            song_id = cursor.lastrowid
            
            for genre_id in selected_genres:
                conn.execute("INSERT INTO song_genres (song_id, genre_id) VALUES (?, ?)", (song_id, genre_id))
            
            conn.commit()

        flash('🎵 Lagu berhasil diunggah dan menunggu persetujuan admin.')
        return redirect(url_for('profile'))

    return render_template('user/upload_song.html', title="Upload Song", genres=genres)

@app.route('/edit_song/<int:song_id>', methods=['GET', 'POST'])
@login_required
def edit_song(song_id):
    user_id = session['user_id']

    with get_db() as conn:
        song = conn.execute(
            "SELECT * FROM songs WHERE id = ? AND user_id = ?",
            (song_id, user_id)
        ).fetchone()
        genres = conn.execute("SELECT * FROM genres ORDER BY name").fetchall()

        if not song:
            flash('❌ Lagu tidak ditemukan atau bukan milik Anda.', 'error')
            return redirect(url_for('profile'))

        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            artist = request.form.get('artist', '').strip()
            description = request.form.get('description', '').strip()
            lyrics = request.form.get('lyrics', '')
            cover_file = request.files.get('cover_file')

            if not title or not artist:
                flash('❌ Judul dan artis wajib diisi.', 'error')
                return render_template('user/edit_song.html', title='Edit Lagu', song=song, genres=genres)

            cover_filename = song['cover_file']
            if cover_file and cover_file.filename:
                cover_filename = datetime.now().strftime("%Y%m%d%H%M%S_") + cover_file.filename
                cover_file.save(os.path.join(UPLOAD_COVER_FOLDER, cover_filename))

            conn.execute("""
                UPDATE songs
                SET title = ?, artist = ?, description = ?, lyrics = ?, cover_file = ?, status = 'pending'
                WHERE id = ? AND user_id = ?
            """, (title, artist, description, lyrics, cover_filename, song_id, user_id))
            conn.commit()

            flash('✅ Lagu berhasil diperbarui dan menunggu persetujuan admin kembali.', 'success')
            return redirect(url_for('profile'))

    return render_template('user/edit_song.html', title='Edit Lagu', song=song, genres=genres)

@app.route('/song/<int:song_id>/request-delete', methods=['POST'])
@login_required
def request_song_deletion(song_id):
    user_id = session['user_id']
    with get_db() as conn:
        song = conn.execute(
            "SELECT * FROM songs WHERE id = ? AND user_id = ?",
            (song_id, user_id)
        ).fetchone()
        if not song:
            flash('❌ Lagu tidak ditemukan atau bukan milik Anda.', 'error')
            return redirect(url_for('profile'))

        if song['status'] == 'delete_requested':
            flash('⏳ Permintaan hapus lagu ini sudah menunggu persetujuan admin.', 'info')
        else:
            conn.execute("UPDATE songs SET status = 'delete_requested' WHERE id = ?", (song_id,))
            conn.commit()
            flash('⏳ Permintaan hapus lagu dikirim dan menunggu persetujuan admin.', 'success')

    return redirect(url_for('profile'))

# === Upload Podcast ===
@app.route('/upload_podcast', methods=['GET', 'POST'])
@login_required
def upload_podcast():
    user_id = session['user_id']
    if request.method == 'POST':
        title = request.form['title']
        host = request.form['host']
        category = request.form.get('category', '')
        description = request.form.get('description', '')
        audio_file = request.files['audio_file']
        cover_file = request.files.get('cover_file')

        audio_filename = None
        if audio_file and audio_file.filename:
            audio_filename = datetime.now().strftime("%Y%m%d%H%M%S_") + audio_file.filename
            audio_file.save(os.path.join(UPLOAD_PODCAST_FOLDER, audio_filename))

        cover_filename = None
        if cover_file and cover_file.filename:
            cover_filename = datetime.now().strftime("%Y%m%d%H%M%S_") + cover_file.filename
            cover_file.save(os.path.join(UPLOAD_PODCAST_COVER, cover_filename))

        with get_db() as conn:
            conn.execute("""
                INSERT INTO podcasts (title, host, category, description, audio_file, cover_file, uploaded_at, status, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, host, category, description, audio_filename, cover_filename, datetime.now().isoformat(), 'pending', user_id))
            conn.commit()

        flash('🎙️ Podcast berhasil diunggah dan menunggu persetujuan admin.')
        return redirect(url_for('profile'))

    return render_template('user/upload_podcast.html', title="Upload Podcast")

# === Update jumlah play lagu/podcast ===
@app.route('/play/<content_type>/<int:content_id>')
def play_content(content_type, content_id):
    table = "songs" if content_type == "song" else "podcasts"
    with get_db() as conn:
        conn.execute(f"""
            UPDATE {table}
            SET plays = plays + 1, last_played_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), content_id))
        conn.commit()
    return "OK"

# =====================================================
# =================== ADMIN ROUTES ====================
# =====================================================

@app.route('/admin/songs')
@admin_required
def admin_songs():
    with get_db() as conn:
        songs = conn.execute("SELECT * FROM songs ORDER BY uploaded_at DESC").fetchall()
    return render_template('admin/admin_songs.html', songs=songs, title="Admin - Songs")

@app.route('/admin/podcasts')
@admin_required
def admin_podcasts():
    with get_db() as conn:
        podcasts = conn.execute("SELECT * FROM podcasts ORDER BY uploaded_at DESC").fetchall()
    return render_template('admin/admin_podcasts.html', podcasts=podcasts, title="Admin - Podcasts")

@app.route('/admin/approve_podcast/<int:podcast_id>')
@admin_required
def approve_podcast(podcast_id):
    with get_db() as conn:
        conn.execute("UPDATE podcasts SET status = 'approved' WHERE id = ?", (podcast_id,))
        conn.commit()
    flash('✅ Podcast berhasil disetujui')
    return redirect(url_for('admin_podcasts'))

@app.route('/admin/approve/<int:song_id>')
@admin_required
def approve_song(song_id):
    with get_db() as conn:
        conn.execute("UPDATE songs SET status = 'approved' WHERE id = ?", (song_id,))
        conn.commit()
    flash('✅ Lagu berhasil disetujui')
    return redirect(url_for('admin_songs'))

@app.route('/admin/reject/<int:song_id>')
@admin_required
def reject_song(song_id):
    with get_db() as conn:
        conn.execute("UPDATE songs SET status = 'rejected' WHERE id = ?", (song_id,))
        conn.commit()
    flash('❌ Lagu telah ditolak')
    return redirect(url_for('admin_songs'))

@app.route('/admin/delete/<int:song_id>', methods=['POST'])
@admin_required
def admin_delete_song(song_id):
    with get_db() as conn:
        song = conn.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone()
        if not song:
            flash('❌ Lagu tidak ditemukan.', 'error')
            return redirect(url_for('admin_songs'))

        delete_song_data(conn, song)
        conn.commit()

    flash('✅ Lagu berhasil dihapus.')
    return redirect(url_for('admin_songs'))


@app.route('/admin/delete_podcast/<int:podcast_id>', methods=['POST'])
@admin_required
def admin_delete_podcast(podcast_id):
    with get_db() as conn:
        podcast = conn.execute("SELECT * FROM podcasts WHERE id = ?", (podcast_id,)).fetchone()
        if not podcast:
            flash('❌ Podcast tidak ditemukan.', 'error')
            return redirect(url_for('admin_podcasts'))

        delete_podcast_data(conn, podcast)
        conn.commit()

    flash('✅ Podcast berhasil dihapus.')
    return redirect(url_for('admin_podcasts'))

# =====================================================
# ============= PROFILE EDIT ENDPOINTS ================
# =====================================================

@app.route('/edit-profile', methods=['POST'])
@login_required
def edit_profile():
    """Edit profile: full_name, username, bio, and avatar."""
    user_id = session['user_id']
    user = get_current_user()
    
    new_full_name = request.form.get('full_name', '').strip()
    new_username = request.form.get('username', '').strip()
    new_bio = request.form.get('bio', '').strip()
    remove_avatar = request.form.get('remove_avatar') == '1'
    new_avatar = None
    
    # Validasi full_name
    if not new_full_name or len(new_full_name) < 2:
        return jsonify({'success': False, 'message': 'Nama minimal 2 karakter'}), 400
    
    # Validasi username
    if not new_username or len(new_username) < 3:
        return jsonify({'success': False, 'message': 'Username minimal 3 karakter'}), 400
    
    # Check username uniqueness (jika berubah)
    if new_username != user['username']:
        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ? AND id != ?",
                (new_username, user_id)
            ).fetchone()
            if existing:
                return jsonify({'success': False, 'message': 'Username sudah digunakan'}), 400
    
    try:
        # Handle avatar upload
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename and file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                if file_size > 5 * 1024 * 1024:
                    return jsonify({'success': False, 'message': 'Ukuran foto maksimal 5MB'}), 400

                # Remove old avatar
                if user['avatar']:
                    old_avatar = user['avatar'].replace('/static/uploads/avatars/', '')
                    old_path = os.path.join(UPLOAD_AVATAR_FOLDER, old_avatar)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Save new avatar
                filename = f"avatar_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file.filename.split('.')[-1]}"
                file.save(os.path.join(UPLOAD_AVATAR_FOLDER, filename))
                new_avatar = filename
            elif file and file.filename:
                return jsonify({'success': False, 'message': 'Format foto harus JPG, JPEG, PNG, atau GIF'}), 400

        if remove_avatar and not new_avatar and user['avatar']:
            old_avatar = user['avatar'].replace('/static/uploads/avatars/', '')
            old_path = os.path.join(UPLOAD_AVATAR_FOLDER, old_avatar)
            if os.path.exists(old_path):
                os.remove(old_path)
        
        # Update database
        with get_db() as conn:
            if new_avatar:
                conn.execute(
                    "UPDATE users SET full_name = ?, username = ?, bio = ?, avatar = ? WHERE id = ?",
                    (new_full_name, new_username, new_bio or None, new_avatar, user_id)
                )
            elif remove_avatar:
                conn.execute(
                    "UPDATE users SET full_name = ?, username = ?, bio = ?, avatar = NULL WHERE id = ?",
                    (new_full_name, new_username, new_bio or None, user_id)
                )
            else:
                conn.execute(
                    "UPDATE users SET full_name = ?, username = ?, bio = ? WHERE id = ?",
                    (new_full_name, new_username, new_bio or None, user_id)
                )
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': '✅ Profil berhasil diperbarui',
            'user': {
                'full_name': new_full_name,
                'username': new_username,
                'bio': new_bio,
                'avatar': new_avatar or user['avatar']
            }
        })
    
    except Exception as e:
        print(f"Error editing profile: {e}")
        return jsonify({'success': False, 'message': 'Terjadi kesalahan saat update profil'}), 500

# =====================================================
# ============= PLAYLIST API ENDPOINTS ================
# =====================================================

@app.route('/api/playlists', methods=['GET'])
@login_required
def get_user_playlists():
    """Get all playlists for current user"""
    user_id = session['user_id']
    
    with get_db() as conn:
        playlists = conn.execute("""
            SELECT p.*, 
                   COUNT(ps.id) as song_count
            FROM playlists p
            LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
            WHERE p.user_id = ?
            GROUP BY p.id
            ORDER BY p.created_at DESC
        """, (user_id,)).fetchall()
    
    return jsonify({
        'success': True,
        'playlists': [dict(p) for p in playlists]
    })

@app.route('/api/playlist/<int:playlist_id>/add-song/<int:song_id>', methods=['POST'])
@login_required
def api_add_song_to_playlist(playlist_id, song_id):
    """Add song to playlist via API (returns JSON)"""
    user_id = session['user_id']
    
    try:
        with get_db() as conn:
            # Cek kepemilikan playlist
            playlist = conn.execute(
                "SELECT * FROM playlists WHERE id = ? AND user_id = ?", 
                (playlist_id, user_id)
            ).fetchone()
            
            if not playlist:
                return jsonify({
                    'success': False, 
                    'message': 'Anda tidak memiliki akses ke playlist ini'
                }), 403
            
            # Cek apakah lagu sudah ada
            exists = conn.execute(
                "SELECT 1 FROM playlist_songs WHERE playlist_id = ? AND song_id = ?", 
                (playlist_id, song_id)
            ).fetchone()
            
            if exists:
                return jsonify({
                    'success': False, 
                    'message': 'Lagu sudah ada di playlist ini'
                }), 400
            
            # Add lagu ke playlist
            conn.execute(
                "INSERT INTO playlist_songs (playlist_id, song_id, added_at) VALUES (?, ?, ?)",
                (playlist_id, song_id, datetime.now().isoformat())
            )
            conn.commit()
        
        return jsonify({
            'success': True, 
            'message': '✅ Lagu berhasil ditambahkan ke playlist'
        })
    
    except Exception as e:
        print(f"Error adding song to playlist: {e}")
        return jsonify({
            'success': False, 
            'message': 'Gagal menambahkan lagu ke playlist'
        }), 500

# =====================================================
# ============= LIKE SONGS ENDPOINTS ==================
# =====================================================

@app.route('/api/like-song/<int:song_id>', methods=['POST'])
@login_required
def like_song(song_id):
    """Like a song"""
    user_id = session['user_id']
    
    with get_db() as conn:
        # Check if already liked
        existing = conn.execute(
            "SELECT id FROM liked_songs WHERE user_id = ? AND song_id = ?",
            (user_id, song_id)
        ).fetchone()
        
        if existing:
            # Unlike
            conn.execute(
                "DELETE FROM liked_songs WHERE user_id = ? AND song_id = ?",
                (user_id, song_id)
            )
            conn.commit()
            return jsonify({'success': True, 'liked': False, 'message': '❤️ Dihapus dari lagu favorit'})
        else:
            # Like
            conn.execute(
                "INSERT INTO liked_songs (user_id, song_id, liked_at) VALUES (?, ?, ?)",
                (user_id, song_id, datetime.now().isoformat())
            )
            conn.commit()
            return jsonify({'success': True, 'liked': True, 'message': '❤️ Ditambahkan ke lagu favorit'})

@app.route('/api/is-liked/<int:song_id>', methods=['GET'])
@login_required
def is_song_liked(song_id):
    """Check if song is liked by current user"""
    user_id = session['user_id']
    
    with get_db() as conn:
        liked = conn.execute(
            "SELECT id FROM liked_songs WHERE user_id = ? AND song_id = ?",
            (user_id, song_id)
        ).fetchone()
    
    return jsonify({'liked': liked is not None})

@app.route('/liked-songs')
@login_required
def liked_songs():
    """Display user's liked songs"""
    user_id = session['user_id']
    user = get_current_user()
    
    with get_db() as conn:
        liked_songs_list = conn.execute("""
            SELECT s.* FROM songs s
            JOIN liked_songs ls ON s.id = ls.song_id
            WHERE ls.user_id = ? AND s.status = 'approved'
            ORDER BY ls.liked_at DESC
        """, (user_id,)).fetchall()
        
        total_likes = len(liked_songs_list)
    
    return render_template('user/liked_songs.html', 
                         title="Lagu Favorit", 
                         songs=liked_songs_list,
                         user=user,
                         total_likes=total_likes)

# =====================================================
# =================== MAIN RUN ========================
# =====================================================

if __name__ == "__main__":
    app.run(debug=True, port=5001)