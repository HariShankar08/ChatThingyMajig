import os

from flask import Flask, render_template, request, flash, redirect, session, jsonify
import sqlite3 as sql
from datetime import datetime

from flask.templating import render_template_string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'Secret'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/p/login', methods=['POST'])
def login():
    out = request.form
    with sql.connect('db.sqlite3') as cnx:
        cur = cnx.cursor()
        r = cur.execute('SELECT user_id, password FROM users WHERE username=?', (out['username'],))
        if not (results := r.fetchall()):
            flash('User not found')
            return redirect('/')
    user_id, password = results[0]
    if password != out['password']:
        flash('Incorrect Password')
        return redirect('/')
    session['user_id'] = user_id

    # Logged In, redirect this user.
    return redirect('/chats')


@app.route('/signup')
def show_signup():
    return render_template('signup.html')


@app.route('/chats')
def show_chats():
    if not session.get('user_id'):
        return redirect('/')

    with sql.connect('db.sqlite3') as cnx:
        cur = cnx.cursor()
        r = cur.execute('SELECT chat_id, name FROM chats WHERE chat_id=(SELECT chat_id FROM messages WHERE user_id=?)',
                        (session['user_id'], ))
        chats = [{'chat_id': row[0], 'name': row[1]} for row in r.fetchall()]
    return render_template('chats.html', chats=chats)


@app.route('/create_chat', methods=['GET', 'POST'])
def create_chat():
    if request.method.lower() == 'get':
        if not session.get('user_id'):
            return redirect('/')
        return render_template('create_chat.html')
    else:
        name = request.form['name'].strip().lower()
        with sql.connect('db.sqlite3') as cnx:
            cur = cnx.cursor()
            cur.execute('INSERT INTO chats (name) VALUES (?)', (name, ))
            chat_id = cur.lastrowid

            cur.execute('INSERT INTO messages (chat_id, user_id, content, announcement, sent_time) VALUES (?, ?, ?, ?, ?)',
                        (chat_id, session['user_id'], 'Welcome to the Chat!', 1, str(datetime.now())))
            cnx.commit()
        return redirect(f'/chat/{chat_id}')


@app.route('/join_chat', methods=['GET', 'POST'])
def join_chat():
    if request.method.lower() == 'get':
        if not session.get('user_id'):
            return redirect('/')
        return render_template('join_chat.html')

    else:
        name, chat_id = request.form['code'].strip().split('#')
        try:
            name = name.strip().lower()
            chat_id = int(chat_id)
        except ValueError:
            flash('Invalid Chat ID')
            return redirect('/join_chat')
        
        with sql.connect('db.sqlite3') as cnx:
            cur = cnx.cursor()
            r = cur.execute('SELECT name, chat_id FROM chats WHERE name=? AND chat_id=?', (name, chat_id))
            
            if not (res := r.fetchall()):
                flash('Did not Find Chat.')
                return redirect('/join_chat')
            


            cur.execute('INSERT INTO messages (chat_id, user_id, content, announcement, sent_time) VALUES (?, ?, ?, ?, ?)',
                        (chat_id, session['user_id'], 'Someone Joined! Say Hi!', 1, str(datetime.now())))
            cnx.commit()
        return redirect(f'/chat/{chat_id}')


@app.before_first_request
def setup_db():
    if os.path.exists('db.sqlite3'):
        return
    with sql.connect('db.sqlite3') as cnx:
        cur = cnx.cursor()
        cur.execute('''CREATE TABLE users (
user_id INTEGER PRIMARY KEY AUTOINCREMENT,
username VARCHAR(25) UNIQUE NOT NULL,
password VARCHAR(25) NOT NULL)''')

        cur.execute('''CREATE TABLE chats (
chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
name VARCHAR(25) NOT NULL)''')

        cur.execute('''CREATE TABLE messages (
chat_id INTEGER NOT NULL,
user_id INTEGER NOT NULL,
content VARCHAR(255) NOT NULL,
announcement BOOL NOT NULL DEFAULT 0,
sent_time DATETIME NOT NULL,
FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE)''')

        cnx.commit()


@app.route('/p/signup', methods=['POST'])
def signup():
    out = request.form
    with sql.connect('db.sqlite3') as cnx:
        cur = cnx.cursor()
        r = cur.execute('SELECT user_id FROM users WHERE username=?', (out['username'], ))
        if r.fetchall():
            flash('User already exists')
            return redirect('/')
        cur.execute('INSERT INTO users (username, password) VALUES (?, ?)', (out['username'], out['password']))
        user_id = cur.lastrowid
        cnx.commit()
    # Created User, log in
    session['user_id'] = user_id
    return redirect('/chats')


@app.route('/chat/<int:chat_id>')
def chat(chat_id):
    if not session.get('user_id'):
        return redirect('/')

    with sql.connect('db.sqlite3') as cnx:
        cur = cnx.cursor()

        # Has the person already posted to the Group?
        # Group -> chat_id
        r = cur.execute('SELECT chat_id FROM messages WHERE user_id=?', (session['user_id'], ))
        if chat_id not in [row[0] for row in r.fetchall()]:
            return redirect('/chats')  # Person not in Chat

        r = cur.execute('SELECT username, content, announcement FROM messages NATURAL JOIN users WHERE chat_id=? '
                        'ORDER BY sent_time ASC', (chat_id, ))
        messages = [{'username': row[0], 'content': row[1], 'announcement': row[2]} for row in r.fetchall()]
        message_html = render_template("chat_message_template.html", msg=messages)

        r = cur.execute('SELECT name FROM chats WHERE chat_id = ?', (chat_id, ))
        chat_name = r.fetchone()[0]

        return render_template('chat_messages.html', message_html=message_html, chat_id=chat_id, chat_name=chat_name)


@app.route('/p/get_messages', methods=['GET'])
def get_messages():
    chat_id = request.args['chat_id']
    with sql.connect('db.sqlite3') as cnx:
        cur = cnx.cursor()
        r = cur.execute('SELECT username, content, announcement FROM messages NATURAL JOIN users WHERE chat_id=? '
                        'ORDER BY sent_time ASC', (chat_id,))
        messages = [{'username': row[0], 'content': row[1], 'announcement': row[2]} for row in r.fetchall()]
        message_html = render_template("chat_message_template.html", msg=messages)
    return jsonify({'window_html': message_html})


@app.route('/p/post_message', methods=['POST'])
def post_message():
    chat_id = request.args['chat_id']
    user_id = request.args['user_id']
    msg = request.args['message']

    with sql.connect('db.sqlite3') as cnx:
        cur = cnx.cursor()
        r = cur.execute('INSERT INTO messages (chat_id, user_id, content, sent_time) VALUES (?,?,?,?)',
                        (chat_id, user_id, msg, str(datetime.now())))
        cnx.commit()

    return '', 201


if __name__ == '__main__':
    app.run()
