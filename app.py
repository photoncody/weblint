import os
import uuid
import json
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'weblint_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/snippets.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Snippet(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)

with app.app_context():
    db.create_all()

    # Migration: Import existing JSON snippets if DB is empty
    json_file = '/data/snippets.json'
    if os.path.exists(json_file) and Snippet.query.count() == 0:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        snippet = Snippet(
                            id=item.get('id', str(uuid.uuid4())),
                            title=item.get('title', 'Untitled'),
                            content=item.get('content', ''),
                            type=item.get('type', 'plain')
                        )
                        db.session.add(snippet)
                    db.session.commit()
                    print(f"Successfully migrated {len(data)} snippets from JSON to SQLite.")
                    # Rename old file to avoid confusion, or keep as backup
                    os.rename(json_file, json_file + '.bak')
        except Exception as e:
            print(f"Error migrating JSON data: {e}")

@app.route('/')
def index():
    query = request.args.get('q', '').lower()
    
    if query:
        snippets = Snippet.query.filter(
            (Snippet.title.ilike(f'%{query}%')) | 
            (Snippet.content.ilike(f'%{query}%'))
        ).order_by(Snippet.title).all()
    else:
        snippets = Snippet.query.order_by(Snippet.title).all()
    
    return render_template('index.html', snippets=snippets, query=query)

@app.route('/new', methods=['GET', 'POST'])
def new_snippet():
    if request.method == 'POST':
        new_snippet = Snippet(
            title=request.form['title'],
            content=request.form['content'],
            type=request.form['type']
        )
        db.session.add(new_snippet)
        db.session.commit()
        return redirect(url_for('view_snippet', s_id=new_snippet.id))
    return render_template('editor.html', snippet=None)

@app.route('/edit/<s_id>', methods=['GET', 'POST'])
def edit_snippet(s_id):
    snippet = Snippet.query.get_or_404(s_id)
    
    if request.method == 'POST':
        snippet.title = request.form['title']
        snippet.content = request.form['content']
        snippet.type = request.form['type']
        db.session.commit()
        return redirect(url_for('view_snippet', s_id=s_id))
        
    return render_template('editor.html', snippet=snippet)

@app.route('/view/<s_id>')
def view_snippet(s_id):
    snippet = Snippet.query.get_or_404(s_id)
    return render_template('view.html', snippet=snippet)

@app.route('/delete/<s_id>')
def delete_snippet(s_id):
    snippet = Snippet.query.get_or_404(s_id)
    db.session.delete(snippet)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)