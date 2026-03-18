import os
from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from markupsafe import escape
from models import db, User, Post, Message
from datetime import timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.getenv('DB_PATH')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SESSION_COOKIE_DOMAIN'] = '.moodspace.local'
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

ALLOWED_ORIGINS = ['http://test.moodspace.local:5000']

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin')
    if origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

def get_subdomain():
    host = request.host.split(':')[0]
    parts = host.split('.')
    if len(parts) >= 2:
        return parts[0]
    return None

@app.route('/api/user/<username>', methods=['GET', 'OPTIONS'])
def api_get_user(username):
    if request.method == 'OPTIONS':
        return '', 200
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'bio': user.bio,
        'is_bot': user.is_bot
    })

@app.route('/api/post/create', methods=['POST', 'OPTIONS'])
def api_create_post():
    if request.method == 'OPTIONS':
        return '', 200
    
    data = request.json
    content = data.get('content')
    
    if not content:
        return jsonify({'error': 'Content required'}), 400
    
    username = data.get('username')
    if username:
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
    else:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Not authenticated'}), 401
        user = current_user
    
    if user.username == 'emma':
        return jsonify({'error': 'Cannot create posts as Emma'}), 403
    
    post = Post(
        author_id=user.id,
        content=content,
        title=data.get('title', ''),
        is_private=True
    )
    db.session.add(post)
    db.session.commit()
    
    return jsonify({'status': 'ok', 'post_id': post.id})

@app.route('/api/send_message', methods=['POST'])
@login_required
def send_message():
    data = request.json
    message_text = data.get('message', '')
    
    if current_user.username == 'emma':
        return jsonify({'error': 'Emma cannot send messages'}), 403
    
    user_msg = Message(
        user_id=current_user.id,
        content=message_text,
        from_bot=False
    )
    db.session.add(user_msg)
    
    try:
        with open('/tmp/messages.txt', 'a') as f:
            f.write(f"{current_user.username}: {message_text}\n")
    except Exception as e:
        print(f"Ошибка сохранения сообщения: {e}")
    
    import re
    has_url = re.search(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+])+', message_text)
    
    if has_url:
        reply = "Ого, как интересно! Спасибо, обязательно почитаю ♥"
    elif 'грустно' in message_text.lower():
        reply = "Прочитай это: http://moodspace.local:5000/emma/blog/1"
    elif 'тревожно' in message_text.lower():
        reply = "Прочитай это: http://moodspace.local:5000/emma/blog/2"
    elif 'нет сил' in message_text.lower():
        reply = "Прочитай это: http://moodspace.local:5000/emma/blog/3"
    else:
        reply = "Я здесь, чтобы поддержать тебя ♥"
    
    bot_msg = Message(
        user_id=current_user.id,
        content=reply,
        from_bot=True
    )
    db.session.add(bot_msg)
    db.session.commit()
    
    return jsonify({'status': 'ok', 'reply': reply})

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    subdomain = get_subdomain()
    
    if subdomain == 'test':
        vuln_param = request.args.get('vuln_param', '')
        posts = Post.query.filter_by(author_id=current_user.id).order_by(Post.created_at.desc()).all()
        return render_template('test/index.html', vuln_param=vuln_param, posts=posts)
    
    posts = Post.query.filter_by(author_id=current_user.id).order_by(Post.created_at.desc()).all()
    return render_template('blog/index.html', posts=posts)

@app.route('/messages')
@login_required
def messages():
    if current_user.username == 'emma':
        return redirect(url_for('login'))
    
    messages_list = Message.query.filter_by(user_id=current_user.id).order_by(Message.created_at.asc()).all()
    return render_template('messages/dialog.html', messages=messages_list)

@app.route('/emma/blog')
def emma_blog():
    emma = User.query.filter_by(username='emma').first()
    posts = Post.query.filter_by(author_id=emma.id).order_by(Post.created_at.desc()).all()
    return render_template('blog/emma_blog.html', posts=posts, bio=emma.bio)

@app.route('/emma/blog/<int:post_id>')
def view_post(post_id):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    post = Post.query.get_or_404(post_id)
    return render_template('blog/post.html', post=post)

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if current_user.username == 'emma':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        content = request.form.get('content')
        safe_content = escape(content)
        
        post = Post(
            author_id=current_user.id,
            content=safe_content,
            is_private=True
        )
        db.session.add(post)
        db.session.commit()
        
        subdomain = get_subdomain()
        if subdomain == 'test':
            return redirect('http://test.moodspace.local:5000/')
        return redirect('http://blog.moodspace.local:5000/')
    
    return render_template('blog/create_post.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        subdomain = get_subdomain()
        if subdomain == 'test':
            return redirect('http://test.moodspace.local:5000/')
        return redirect('http://blog.moodspace.local:5000/')
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            subdomain = get_subdomain()
            if subdomain == 'test':
                return redirect('http://test.moodspace.local:5000/')
            return redirect('http://blog.moodspace.local:5000/')
        
        return render_template('auth/login.html', error='Неверный логин или пароль')
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        subdomain = get_subdomain()
        if subdomain == 'test':
            return redirect('http://test.moodspace.local:5000/')
        return redirect('http://blog.moodspace.local:5000/')
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            return render_template('auth/register.html', error='Пользователь уже существует')
        
        user = User(username=username)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        welcome_msg = Message(
            user_id=user.id,
            content='Приветствую, ' + username + '! Добро пожаловать в MoodSpace. Ты всегда можешь обратиться ко мне за помощью ♥',
            from_bot=True
        )
        db.session.add(welcome_msg)
        db.session.commit()
        
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    
    resp = redirect('http://moodspace.local:5000/login')
    resp.set_cookie('session', '', expires=0)
    resp.set_cookie('remember_token', '', expires=0)
    
    return resp

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(days=1)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
