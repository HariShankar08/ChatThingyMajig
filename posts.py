from flask import Blueprint, session, redirect, render_template

app = Blueprint(__name__, 'posts', static_folder='static', template_folder='templates')

@app.route('/')
def posts_index():
  if session.get('user_id') is not None:
    return render_template('view_posts.html', posts=[])
  return redirect('/')