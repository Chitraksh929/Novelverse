from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort
from database import init_db, get_db
from utils.auth import hash_password, verify_password, login_required, author_required, generate_csrf_token, csrf_protect
from utils.helpers import paginate, time_ago, word_count
import os, uuid

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_cover_image(file_field):
    """
    Handles cover image from either a file upload or a URL field.
    Returns the cover URL string to store in DB, or '' if nothing provided.
    """
    # 1. File upload takes priority
    f = request.files.get(file_field)
    if f and f.filename and allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        filename = f'{uuid.uuid4().hex}.{ext}'
        f.save(os.path.join(UPLOAD_FOLDER, filename))
        return url_for('static', filename=f'uploads/{filename}')
    # 2. Fall back to URL field
    url = request.form.get('cover_url', '').strip()
    return url

app = Flask(__name__)

# ─── Secret key: stable across restarts (read from env or generate once) ─────
_KEY_FILE = '.secret_key'
if os.path.exists(_KEY_FILE):
    with open(_KEY_FILE) as f:
        app.secret_key = f.read().strip()
else:
    app.secret_key = os.urandom(32).hex()
    with open(_KEY_FILE, 'w') as f:
        f.write(app.secret_key)

app.jinja_env.filters['time_ago'] = time_ago
app.jinja_env.filters['word_count'] = word_count

# ─── Inject CSRF token into every template automatically ──────────────────────
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token())

# ─── Teardown DB connection properly ─────────────────────────────────────────
@app.teardown_appcontext
def close_db(error):
    from flask import g
    db = g.pop('db', None)
    if db is not None:
        db.close()

# ─── Init ────────────────────────────────────────────────────────────────────
with app.app_context():
    init_db()

# ─── Auth Routes ─────────────────────────────────────────────────────────────
@app.route('/register', methods=['GET','POST'])
@csrf_protect
def register():
    if request.method == 'POST':
        db = get_db()
        username = request.form['username'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        if db.execute('SELECT id FROM users WHERE username=? OR email=?',(username,email)).fetchone():
            flash('Username or email already taken.','error')
            return render_template('auth/register.html')
        pw_hash, salt = hash_password(password)
        db.execute('INSERT INTO users(username,email,password_hash,salt) VALUES(?,?,?,?)',(username,email,pw_hash,salt))
        db.commit()
        flash('Account created! Please log in.','success')
        return redirect(url_for('login'))
    return render_template('auth/register.html')

@app.route('/login', methods=['GET','POST'])
@csrf_protect
def login():
    if request.method == 'POST':
        db = get_db()
        identifier = request.form['identifier'].strip()
        password   = request.form['password']
        user = db.execute('SELECT * FROM users WHERE username=? OR email=?',(identifier,identifier)).fetchone()
        if user and verify_password(password, user['password_hash'], user['salt']):
            session['user_id']  = user['id']
            session['username'] = user['username']
            session['is_author']= bool(user['is_author'])
            db.execute('UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?',(user['id'],))
            db.commit()
            return redirect(url_for('home'))
        flash('Invalid credentials.','error')
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ─── Home ─────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    db = get_db()
    trending = db.execute('''SELECT n.*,u.username as author_name,
        COUNT(DISTINCT nv.id) as view_count,
        COUNT(DISTINCT nf.user_id) as follower_count,
        AVG(r.rating) as avg_rating,
        COUNT(DISTINCT r.id) as rating_count
        FROM novels n JOIN users u ON n.author_id=u.id
        LEFT JOIN novel_views nv ON n.id=nv.novel_id
        LEFT JOIN novel_follows nf ON n.id=nf.novel_id
        LEFT JOIN reviews r ON n.id=r.novel_id
        WHERE n.status!="draft"
        GROUP BY n.id ORDER BY view_count DESC LIMIT 6''').fetchall()
    latest = db.execute('''SELECT n.*,u.username as author_name,
        COUNT(DISTINCT r.id) as rating_count, AVG(r.rating) as avg_rating
        FROM novels n JOIN users u ON n.author_id=u.id
        LEFT JOIN reviews r ON n.id=r.novel_id
        WHERE n.status!="draft" GROUP BY n.id ORDER BY n.created_at DESC LIMIT 6''').fetchall()
    genres = db.execute('SELECT DISTINCT genre FROM novels WHERE genre IS NOT NULL AND status!="draft"').fetchall()
    recommended = []
    if 'user_id' in session:
        recommended = get_recommendations(db, session['user_id'])
    stats = db.execute('''SELECT COUNT(DISTINCT u.id) as users,
        COUNT(DISTINCT n.id) as novels, COUNT(DISTINCT c.id) as chapters
        FROM users u, novels n, chapters c''').fetchone()
    return render_template('home.html', trending=trending, latest=latest,
                           genres=[g['genre'] for g in genres],
                           recommended=recommended, stats=stats)

# ─── Browse ───────────────────────────────────────────────────────────────────
@app.route('/browse')
def browse():
    db   = get_db()
    page = int(request.args.get('page',1))
    genre  = request.args.get('genre','')
    status = request.args.get('status','')
    sort   = request.args.get('sort','updated')
    search = request.args.get('q','')
    per_page = 20

    where_clauses = ["n.status!='draft'"]
    params = []
    if genre:  where_clauses.append("n.genre=?"); params.append(genre)
    if status: where_clauses.append("n.status=?"); params.append(status)
    if search: where_clauses.append("(n.title LIKE ? OR n.description LIKE ?)"); params+=[f'%{search}%']*2
    where = ' AND '.join(where_clauses)
    order_map = {'updated':'n.updated_at DESC','views':'view_count DESC','rating':'avg_rating DESC','followers':'follower_count DESC','newest':'n.created_at DESC'}
    order = order_map.get(sort,'n.updated_at DESC')

    total = db.execute(f'SELECT COUNT(*) FROM novels n WHERE {where}', params).fetchone()[0]
    novels = db.execute(f'''SELECT n.*,u.username as author_name,
        COUNT(DISTINCT nv.id) as view_count, AVG(r.rating) as avg_rating,
        COUNT(DISTINCT r.id) as rating_count, COUNT(DISTINCT nf.user_id) as follower_count
        FROM novels n JOIN users u ON n.author_id=u.id
        LEFT JOIN novel_views nv ON n.id=nv.novel_id
        LEFT JOIN reviews r ON n.id=r.novel_id
        LEFT JOIN novel_follows nf ON n.id=nf.novel_id
        WHERE {where} GROUP BY n.id ORDER BY {order} LIMIT ? OFFSET ?''',
        params+[per_page,(page-1)*per_page]).fetchall()
    genres = db.execute("SELECT DISTINCT genre FROM novels WHERE genre IS NOT NULL AND status!='draft'").fetchall()
    pagination = paginate(total, page, per_page)
    return render_template('browse.html', novels=novels, pagination=pagination,
                           genres=[g['genre'] for g in genres], current_genre=genre,
                           current_status=status, current_sort=sort, search=search)

# ─── Novel Detail ─────────────────────────────────────────────────────────────
@app.route('/novel/<int:novel_id>')
def novel_detail(novel_id):
    db = get_db()
    novel = db.execute('''SELECT n.*,u.username as author_name,u.id as author_id,
        COUNT(DISTINCT nv.id) as view_count, AVG(r.rating) as avg_rating,
        COUNT(DISTINCT r.id) as rating_count, COUNT(DISTINCT nf.user_id) as follower_count
        FROM novels n JOIN users u ON n.author_id=u.id
        LEFT JOIN novel_views nv ON n.id=nv.novel_id
        LEFT JOIN reviews r ON n.id=r.novel_id
        LEFT JOIN novel_follows nf ON n.id=nf.novel_id
        WHERE n.id=? GROUP BY n.id''', (novel_id,)).fetchone()
    if not novel: abort(404)
    # Record view
    uid = session.get('user_id')
    if uid:
        existing = db.execute('SELECT id FROM novel_views WHERE novel_id=? AND user_id=?',(novel_id,uid)).fetchone()
        if not existing:
            db.execute('INSERT INTO novel_views(novel_id,user_id) VALUES(?,?)',(novel_id,uid))
            db.commit()
    else:
        ip = request.remote_addr
        db.execute('INSERT INTO novel_views(novel_id,ip_address) VALUES(?,?)',(novel_id,ip))
        db.commit()
    chapters = db.execute('SELECT * FROM chapters WHERE novel_id=? AND published=1 ORDER BY chapter_number',(novel_id,)).fetchall()
    reviews  = db.execute('''SELECT r.*,u.username FROM reviews r JOIN users u ON r.user_id=u.id
        WHERE r.novel_id=? ORDER BY r.created_at DESC LIMIT 10''',(novel_id,)).fetchall()
    tags = db.execute('SELECT tag FROM novel_tags WHERE novel_id=?',(novel_id,)).fetchall()
    user_review = None
    is_following = False
    user_rating  = None
    if uid:
        user_review  = db.execute('SELECT * FROM reviews WHERE novel_id=? AND user_id=?',(novel_id,uid)).fetchone()
        is_following = bool(db.execute('SELECT 1 FROM novel_follows WHERE novel_id=? AND user_id=?',(novel_id,uid)).fetchone())
        user_rating  = db.execute('SELECT rating FROM reviews WHERE novel_id=? AND user_id=?',(novel_id,uid)).fetchone()
    comments = db.execute('''SELECT c.*,u.username FROM comments c JOIN users u ON c.user_id=u.id
        WHERE c.novel_id=? AND c.chapter_id IS NULL ORDER BY c.created_at DESC LIMIT 20''',(novel_id,)).fetchall()
    return render_template('novel/detail.html', novel=novel, chapters=chapters,
                           reviews=reviews, tags=[t['tag'] for t in tags],
                           user_review=user_review, is_following=is_following,
                           user_rating=user_rating, comments=comments)

# ─── Chapter Read ─────────────────────────────────────────────────────────────
@app.route('/novel/<int:novel_id>/chapter/<int:chapter_id>')
def read_chapter(novel_id, chapter_id):
    db = get_db()
    chapter = db.execute('SELECT c.*,n.title as novel_title,n.author_id FROM chapters c JOIN novels n ON c.novel_id=n.id WHERE c.id=? AND c.novel_id=?',(chapter_id,novel_id)).fetchone()
    if not chapter or not chapter['published']: abort(404)
    db.execute('UPDATE chapters SET views=views+1 WHERE id=?',(chapter_id,))
    db.commit()
    prev_ch = db.execute('SELECT id FROM chapters WHERE novel_id=? AND chapter_number<? AND published=1 ORDER BY chapter_number DESC LIMIT 1',(novel_id,chapter['chapter_number'])).fetchone()
    next_ch = db.execute('SELECT id FROM chapters WHERE novel_id=? AND chapter_number>? AND published=1 ORDER BY chapter_number ASC  LIMIT 1',(novel_id,chapter['chapter_number'])).fetchone()
    comments = db.execute('''SELECT c.*,u.username FROM comments c JOIN users u ON c.user_id=u.id
        WHERE c.chapter_id=? ORDER BY c.created_at DESC''',(chapter_id,)).fetchall()
    # reading progress
    uid = session.get('user_id')
    if uid:
        db.execute('INSERT OR REPLACE INTO reading_progress(user_id,novel_id,chapter_id,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP)',(uid,novel_id,chapter_id))
        db.commit()
    return render_template('chapter/read.html', chapter=chapter, novel_id=novel_id,
                           prev_ch=prev_ch, next_ch=next_ch, comments=comments)

# ─── Author Portal ────────────────────────────────────────────────────────────
@app.route('/author/become', methods=['POST'])
@login_required
@csrf_protect
def become_author():
    db = get_db()
    db.execute('UPDATE users SET is_author=1 WHERE id=?',(session['user_id'],))
    db.commit()
    session['is_author'] = True
    flash('You are now an author!','success')
    return redirect(url_for('author_dashboard'))

@app.route('/author/dashboard')
@login_required
def author_dashboard():
    db = get_db()
    uid = session['user_id']
    if not session.get('is_author'):
        return render_template('author/become_author.html')
    novels = db.execute('''SELECT n.*,
        COUNT(DISTINCT c.id) as chapter_count,
        COUNT(DISTINCT nv.id) as total_views,
        COUNT(DISTINCT nf.user_id) as followers,
        AVG(r.rating) as avg_rating
        FROM novels n
        LEFT JOIN chapters c ON n.id=c.novel_id AND c.published=1
        LEFT JOIN novel_views nv ON n.id=nv.novel_id
        LEFT JOIN novel_follows nf ON n.id=nf.novel_id
        LEFT JOIN reviews r ON n.id=r.novel_id
        WHERE n.author_id=? GROUP BY n.id ORDER BY n.updated_at DESC''',(uid,)).fetchall()
    # Analytics summary
    total_views = sum(n['total_views'] or 0 for n in novels)
    total_followers = sum(n['followers'] or 0 for n in novels)
    total_chapters = sum(n['chapter_count'] or 0 for n in novels)
    # Recent comments on author's novels
    recent_comments = db.execute('''SELECT c.*,u.username,n.title as novel_title
        FROM comments c JOIN users u ON c.user_id=u.id
        JOIN novels n ON c.novel_id=n.id
        WHERE n.author_id=? ORDER BY c.created_at DESC LIMIT 10''',(uid,)).fetchall()
    return render_template('dashboard/author.html', novels=novels,
                           total_views=total_views, total_followers=total_followers,
                           total_chapters=total_chapters, recent_comments=recent_comments)

@app.route('/author/novel/new', methods=['GET','POST'])
@login_required
@csrf_protect
def create_novel():
    if not session.get('is_author'):
        return redirect(url_for('become_author'))
    if request.method == 'POST':
        db = get_db()
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        genre  = request.form.get('genre','')
        status = request.form.get('status','ongoing')
        cover_url = save_cover_image('cover_file')
        tags = [t.strip() for t in request.form.get('tags','').split(',') if t.strip()]
        db.execute('INSERT INTO novels(author_id,title,description,genre,status,cover_url) VALUES(?,?,?,?,?,?)',
                   (session['user_id'],title,description,genre,status,cover_url))
        novel_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        for tag in tags[:10]:
            db.execute('INSERT INTO novel_tags(novel_id,tag) VALUES(?,?)',(novel_id,tag))
        db.commit()
        flash('Novel created!','success')
        return redirect(url_for('manage_novel', novel_id=novel_id))
    return render_template('novel/create.html')

@app.route('/author/novel/<int:novel_id>/manage')
@login_required
def manage_novel(novel_id):
    db = get_db()
    novel = db.execute('SELECT * FROM novels WHERE id=? AND author_id=?',(novel_id,session['user_id'])).fetchone()
    if not novel: abort(403)
    chapters = db.execute('SELECT * FROM chapters WHERE novel_id=? ORDER BY chapter_number',(novel_id,)).fetchall()
    tags = db.execute('SELECT tag FROM novel_tags WHERE novel_id=?',(novel_id,)).fetchall()
    # Analytics
    views_by_day = db.execute('''SELECT DATE(viewed_at) as day, COUNT(*) as cnt
        FROM novel_views WHERE novel_id=? GROUP BY day ORDER BY day DESC LIMIT 30''',(novel_id,)).fetchall()
    chapter_views = db.execute('SELECT title,chapter_number,views FROM chapters WHERE novel_id=? ORDER BY chapter_number',(novel_id,)).fetchall()
    total_words = sum(len((c['content'] or '').split()) for c in chapters)
    return render_template('dashboard/manage_novel.html', novel=novel, chapters=chapters,
                           tags=[t['tag'] for t in tags], views_by_day=list(reversed(views_by_day)),
                           chapter_views=chapter_views, total_words=total_words)

@app.route('/author/novel/<int:novel_id>/edit', methods=['GET','POST'])
@login_required
@csrf_protect
def edit_novel(novel_id):
    db = get_db()
    novel = db.execute('SELECT * FROM novels WHERE id=? AND author_id=?',(novel_id,session['user_id'])).fetchone()
    if not novel: abort(403)
    if request.method == 'POST':
        title=request.form['title']; description=request.form['description']
        genre=request.form.get('genre',''); status=request.form.get('status','ongoing')
        cover_url = save_cover_image('cover_file')
        # Keep existing cover if no new image provided
        if not cover_url:
            existing_novel = db.execute('SELECT cover_url FROM novels WHERE id=?',(novel_id,)).fetchone()
            cover_url = existing_novel['cover_url'] if existing_novel else ''
        tags=[t.strip() for t in request.form.get('tags','').split(',') if t.strip()]
        db.execute('UPDATE novels SET title=?,description=?,genre=?,status=?,cover_url=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                   (title,description,genre,status,cover_url,novel_id))
        db.execute('DELETE FROM novel_tags WHERE novel_id=?',(novel_id,))
        for tag in tags[:10]:
            db.execute('INSERT INTO novel_tags(novel_id,tag) VALUES(?,?)',(novel_id,tag))
        db.commit()
        flash('Novel updated!','success')
        return redirect(url_for('manage_novel',novel_id=novel_id))
    tags = db.execute('SELECT tag FROM novel_tags WHERE novel_id=?',(novel_id,)).fetchall()
    return render_template('novel/edit.html', novel=novel, tags=','.join(t['tag'] for t in tags))

@app.route('/author/novel/<int:novel_id>/chapter/new', methods=['GET','POST'])
@login_required
@csrf_protect
def new_chapter(novel_id):
    db = get_db()
    novel = db.execute('SELECT * FROM novels WHERE id=? AND author_id=?',(novel_id,session['user_id'])).fetchone()
    if not novel: abort(403)
    if request.method == 'POST':
        title   = request.form['title'].strip()
        content = request.form['content'].strip()
        author_note = request.form.get('author_note','').strip()
        published = 1 if request.form.get('published') else 0
        last_num = db.execute('SELECT MAX(chapter_number) FROM chapters WHERE novel_id=?',(novel_id,)).fetchone()[0] or 0
        db.execute('INSERT INTO chapters(novel_id,chapter_number,title,content,author_note,published) VALUES(?,?,?,?,?,?)',
                   (novel_id,last_num+1,title,content,author_note,published))
        db.execute('UPDATE novels SET updated_at=CURRENT_TIMESTAMP WHERE id=?',(novel_id,))
        db.commit()
        flash('Chapter saved!','success')
        return redirect(url_for('manage_novel',novel_id=novel_id))
    return render_template('chapter/editor.html', novel=novel, chapter=None)

@app.route('/author/novel/<int:novel_id>/chapter/<int:chapter_id>/edit', methods=['GET','POST'])
@login_required
@csrf_protect
def edit_chapter(novel_id, chapter_id):
    db = get_db()
    novel = db.execute('SELECT * FROM novels WHERE id=? AND author_id=?',(novel_id,session['user_id'])).fetchone()
    if not novel: abort(403)
    chapter = db.execute('SELECT * FROM chapters WHERE id=? AND novel_id=?',(chapter_id,novel_id)).fetchone()
    if not chapter: abort(404)
    if request.method == 'POST':
        title   = request.form['title'].strip()
        content = request.form['content'].strip()
        author_note = request.form.get('author_note','').strip()
        published = 1 if request.form.get('published') else 0
        db.execute('UPDATE chapters SET title=?,content=?,author_note=?,published=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                   (title,content,author_note,published,chapter_id))
        db.execute('UPDATE novels SET updated_at=CURRENT_TIMESTAMP WHERE id=?',(novel_id,))
        db.commit()
        flash('Chapter updated!','success')
        return redirect(url_for('manage_novel',novel_id=novel_id))
    return render_template('chapter/editor.html', novel=novel, chapter=chapter)

@app.route('/author/novel/<int:novel_id>/chapter/<int:chapter_id>/delete', methods=['POST'])
@login_required
@csrf_protect
def delete_chapter(novel_id, chapter_id):
    db = get_db()
    novel = db.execute('SELECT * FROM novels WHERE id=? AND author_id=?',(novel_id,session['user_id'])).fetchone()
    if not novel: abort(403)
    db.execute('DELETE FROM chapters WHERE id=? AND novel_id=?',(chapter_id,novel_id))
    db.commit()
    flash('Chapter deleted.','info')
    return redirect(url_for('manage_novel',novel_id=novel_id))

# ─── User Profile ─────────────────────────────────────────────────────────────
@app.route('/user/<username>')
def user_profile(username):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
    if not user: abort(404)
    novels = db.execute('''SELECT n.*,COUNT(DISTINCT c.id) as chapter_count,
        COUNT(DISTINCT nv.id) as view_count, AVG(r.rating) as avg_rating
        FROM novels n LEFT JOIN chapters c ON n.id=c.novel_id AND c.published=1
        LEFT JOIN novel_views nv ON n.id=nv.novel_id
        LEFT JOIN reviews r ON n.id=r.novel_id
        WHERE n.author_id=? AND n.status!="draft" GROUP BY n.id''',(user['id'],)).fetchall()
    following = db.execute('''SELECT n.*,u.username as author_name FROM novel_follows nf
        JOIN novels n ON nf.novel_id=n.id JOIN users u ON n.author_id=u.id
        WHERE nf.user_id=?''',(user['id'],)).fetchall()
    is_self = session.get('user_id') == user['id']
    return render_template('user/profile.html', profile=user, novels=novels,
                           following=following, is_self=is_self)

@app.route('/settings', methods=['GET','POST'])
@login_required
@csrf_protect
def settings():
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone()
    if request.method == 'POST':
        bio = request.form.get('bio','').strip()
        avatar = request.form.get('avatar_url','').strip()
        db.execute('UPDATE users SET bio=?,avatar_url=? WHERE id=?',(bio,avatar,session['user_id']))
        db.commit()
        flash('Profile updated!','success')
    return render_template('user/settings.html', user=user)

# ─── Reading List ─────────────────────────────────────────────────────────────
@app.route('/reading-list')
@login_required
def reading_list():
    db = get_db()
    uid = session['user_id']
    following = db.execute('''SELECT n.*,u.username as author_name,
        COUNT(DISTINCT c.id) as chapter_count, AVG(r.rating) as avg_rating,
        rp.chapter_id as last_read_chapter_id
        FROM novel_follows nf JOIN novels n ON nf.novel_id=n.id
        JOIN users u ON n.author_id=u.id
        LEFT JOIN chapters c ON n.id=c.novel_id AND c.published=1
        LEFT JOIN reviews r ON n.id=r.novel_id
        LEFT JOIN reading_progress rp ON rp.novel_id=n.id AND rp.user_id=?
        WHERE nf.user_id=? GROUP BY n.id ORDER BY n.updated_at DESC''',(uid,uid)).fetchall()
    return render_template('user/reading_list.html', following=following)

# ─── API Endpoints ────────────────────────────────────────────────────────────
@app.route('/api/follow/<int:novel_id>', methods=['POST'])
@login_required
@csrf_protect
def api_follow(novel_id):
    db  = get_db()
    uid = session['user_id']
    existing = db.execute('SELECT 1 FROM novel_follows WHERE novel_id=? AND user_id=?',(novel_id,uid)).fetchone()
    if existing:
        db.execute('DELETE FROM novel_follows WHERE novel_id=? AND user_id=?',(novel_id,uid))
        following = False
    else:
        db.execute('INSERT INTO novel_follows(novel_id,user_id) VALUES(?,?)',(novel_id,uid))
        following = True
    db.commit()
    count = db.execute('SELECT COUNT(*) FROM novel_follows WHERE novel_id=?',(novel_id,)).fetchone()[0]
    return jsonify({'following':following,'count':count})

@app.route('/api/review', methods=['POST'])
@login_required
@csrf_protect
def api_review():
    db   = get_db()
    uid  = session['user_id']
    data = request.get_json()
    novel_id = data['novel_id']
    rating   = int(data['rating'])
    body     = data.get('body','').strip()
    if not 1 <= rating <= 5: return jsonify({'error':'Invalid rating'}),400
    existing = db.execute('SELECT id FROM reviews WHERE novel_id=? AND user_id=?',(novel_id,uid)).fetchone()
    if existing:
        db.execute('UPDATE reviews SET rating=?,body=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(rating,body,existing['id']))
    else:
        db.execute('INSERT INTO reviews(novel_id,user_id,rating,body) VALUES(?,?,?,?)',(novel_id,uid,rating,body))
    db.commit()
    avg = db.execute('SELECT AVG(rating) FROM reviews WHERE novel_id=?',(novel_id,)).fetchone()[0]
    return jsonify({'success':True,'avg_rating':round(avg,2)})

@app.route('/api/comment', methods=['POST'])
@login_required
@csrf_protect
def api_comment():
    db   = get_db()
    uid  = session['user_id']
    data = request.get_json()
    novel_id   = data.get('novel_id')
    chapter_id = data.get('chapter_id')
    body       = data.get('body','').strip()
    if not body: return jsonify({'error':'Empty comment'}),400
    db.execute('INSERT INTO comments(user_id,novel_id,chapter_id,body) VALUES(?,?,?,?)',(uid,novel_id,chapter_id,body))
    db.commit()
    username = session['username']
    return jsonify({'success':True,'username':username,'body':body,'time':'just now'})

@app.route('/api/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
@csrf_protect
def delete_comment(comment_id):
    db = get_db()
    comment = db.execute('SELECT * FROM comments WHERE id=?',(comment_id,)).fetchone()
    if not comment: return jsonify({'error':'Not found'}),404
    if comment['user_id'] != session['user_id']:
        # Check if novel author
        novel = db.execute('SELECT author_id FROM novels WHERE id=?',(comment['novel_id'],)).fetchone()
        if not novel or novel['author_id'] != session['user_id']:
            return jsonify({'error':'Forbidden'}),403
    db.execute('DELETE FROM comments WHERE id=?',(comment_id,))
    db.commit()
    return jsonify({'success':True})

@app.route('/api/like/comment/<int:comment_id>', methods=['POST'])
@login_required
@csrf_protect
def like_comment(comment_id):
    db  = get_db()
    uid = session['user_id']
    existing = db.execute('SELECT 1 FROM comment_likes WHERE comment_id=? AND user_id=?',(comment_id,uid)).fetchone()
    if existing:
        db.execute('DELETE FROM comment_likes WHERE comment_id=? AND user_id=?',(comment_id,uid))
        liked = False
    else:
        db.execute('INSERT INTO comment_likes(comment_id,user_id) VALUES(?,?)',(comment_id,uid))
        liked = True
    db.commit()
    count = db.execute('SELECT COUNT(*) FROM comment_likes WHERE comment_id=?',(comment_id,)).fetchone()[0]
    return jsonify({'liked':liked,'count':count})

@app.route('/api/analytics/<int:novel_id>')
@login_required
def api_analytics(novel_id):
    db = get_db()
    novel = db.execute('SELECT * FROM novels WHERE id=? AND author_id=?',(novel_id,session['user_id'])).fetchone()
    if not novel: abort(403)
    views_by_day = db.execute('''SELECT DATE(viewed_at) as day, COUNT(*) as cnt
        FROM novel_views WHERE novel_id=? GROUP BY day ORDER BY day DESC LIMIT 30''',(novel_id,)).fetchall()
    chapter_stats = db.execute('''SELECT chapter_number,title,views,
        LENGTH(content)-LENGTH(REPLACE(content,' ',''))+1 as word_count
        FROM chapters WHERE novel_id=? ORDER BY chapter_number''',(novel_id,)).fetchall()
    ratings_dist = db.execute('''SELECT rating, COUNT(*) as cnt FROM reviews WHERE novel_id=? GROUP BY rating''',(novel_id,)).fetchall()
    return jsonify({
        'views_by_day': [{'day':r['day'],'cnt':r['cnt']} for r in views_by_day],
        'chapter_stats': [{'num':r['chapter_number'],'title':r['title'],'views':r['views'],'words':r['word_count']} for r in chapter_stats],
        'ratings_dist':  [{'rating':r['rating'],'cnt':r['cnt']} for r in ratings_dist]
    })

@app.route('/api/ai/writing-assist', methods=['POST'])
@login_required
@csrf_protect
def ai_writing_assist():
    data = request.get_json()
    action  = data.get('action','continue')
    content = data.get('content','')
    context = data.get('context','')
    # Anthropic API call
    import requests as req
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "messages": [{"role":"user","content": build_writing_prompt(action, content, context)}]
    }
    resp = req.post('https://api.anthropic.com/v1/messages',
                    headers={"Content-Type":"application/json"},
                    json=payload, timeout=30)
    if resp.status_code == 200:
        text = resp.json()['content'][0]['text']
        return jsonify({'result': text})
    return jsonify({'error':'AI service error'}), 500

@app.route('/api/ai/recommend')
@login_required
def api_recommend():
    db = get_db()
    recs = get_recommendations(db, session['user_id'])
    return jsonify([dict(r) for r in recs])

# ─── Recommendations ──────────────────────────────────────────────────────────
def get_recommendations(db, user_id):
    """Collaborative + content-based hybrid recommendation."""
    # Genres the user reads
    liked_genres = db.execute('''SELECT n.genre, COUNT(*) as cnt FROM reading_progress rp
        JOIN novels n ON rp.novel_id=n.id
        WHERE rp.user_id=? AND n.genre IS NOT NULL
        GROUP BY n.genre ORDER BY cnt DESC LIMIT 3''',(user_id,)).fetchall()
    read_ids = [r['novel_id'] for r in db.execute('SELECT DISTINCT novel_id FROM reading_progress WHERE user_id=?',(user_id,)).fetchall()]
    if liked_genres:
        genres = [g['genre'] for g in liked_genres]
        placeholders = ','.join('?' * len(genres))
        exclude = ','.join('?' * len(read_ids)) if read_ids else '0'
        recs = db.execute(f'''SELECT n.*,u.username as author_name,
            COUNT(DISTINCT nv.id) as view_count, AVG(r.rating) as avg_rating
            FROM novels n JOIN users u ON n.author_id=u.id
            LEFT JOIN novel_views nv ON n.id=nv.novel_id
            LEFT JOIN reviews r ON n.id=r.novel_id
            WHERE n.genre IN ({placeholders}) AND n.id NOT IN ({exclude}) AND n.status!="draft"
            GROUP BY n.id ORDER BY avg_rating DESC, view_count DESC LIMIT 6''',
            genres + (read_ids if read_ids else [])).fetchall()
    else:
        recs = db.execute('''SELECT n.*,u.username as author_name,
            COUNT(DISTINCT nv.id) as view_count, AVG(r.rating) as avg_rating
            FROM novels n JOIN users u ON n.author_id=u.id
            LEFT JOIN novel_views nv ON n.id=nv.novel_id
            LEFT JOIN reviews r ON n.id=r.novel_id
            WHERE n.status!="draft" GROUP BY n.id
            ORDER BY avg_rating DESC, view_count DESC LIMIT 6''').fetchall()
    return recs

def build_writing_prompt(action, content, context):
    prompts = {
        'continue': f"You are a creative writing assistant. Continue the following story passage naturally, matching the style and tone. Write approximately 200-300 words.\n\nContext: {context}\n\nPassage to continue:\n{content}\n\nContinuation:",
        'improve': f"You are a creative writing editor. Improve the following passage for better prose quality, pacing, and engagement. Keep the same events and meaning.\n\nPassage:\n{content}\n\nImproved version:",
        'summarize': f"Summarize the following chapter content in 2-3 sentences for use as a chapter synopsis:\n\n{content}",
        'brainstorm': f"You are a creative writing assistant. Given this story context, suggest 5 interesting plot developments or scene ideas:\n\nContext: {context}\n\nContent: {content}",
        'dialogue': f"Improve or generate dialogue for this scene. Make it feel natural and character-appropriate:\n\nContext: {context}\n\nScene:\n{content}",
    }
    return prompts.get(action, prompts['continue'])

# ─── Search ───────────────────────────────────────────────────────────────────
@app.route('/search')
def search():
    q = request.args.get('q','').strip()
    if not q: return redirect(url_for('browse'))
    db = get_db()
    novels = db.execute('''SELECT n.*,u.username as author_name, AVG(r.rating) as avg_rating,
        COUNT(DISTINCT nv.id) as view_count
        FROM novels n JOIN users u ON n.author_id=u.id
        LEFT JOIN reviews r ON n.id=r.novel_id
        LEFT JOIN novel_views nv ON n.id=nv.novel_id
        WHERE (n.title LIKE ? OR n.description LIKE ?) AND n.status!="draft"
        GROUP BY n.id LIMIT 20''',(f'%{q}%',f'%{q}%')).fetchall()
    authors = db.execute("SELECT * FROM users WHERE username LIKE ? AND is_author=1 LIMIT 10",(f'%{q}%',)).fetchall()
    return render_template('search.html', novels=novels, authors=authors, query=q)

# ─── Error Handlers ───────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e): return render_template('errors/404.html'),404
@app.errorhandler(403)
def forbidden(e): return render_template('errors/403.html'),403
@app.errorhandler(500)
def server_error(e): return render_template('errors/500.html'),500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
