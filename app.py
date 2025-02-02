from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
import boto3
import random
import os
from dotenv import load_dotenv
import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gizli_anahtar_buraya'  # Güvenli bir secret key kullanın
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kelime_ogrenme.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Veritabanı Modelleri
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    current_day = db.Column(db.Integer, default=1)
    progress = db.relationship('UserProgress', backref='user', lazy=True)

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    words = db.Column(db.String(500), nullable=False)  # JSON string olarak saklayacağız
    completed = db.Column(db.Boolean, default=False)
    date_completed = db.Column(db.DateTime)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# AWS credentials
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_region = os.getenv('AWS_REGION', 'us-east-1')

# AWS clients
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=aws_region,
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key
)

def get_random_words(num_words=2):
    with open('a1-words.txt', 'r', encoding='utf-8') as file:
        words = file.read().splitlines()
    return random.sample(words, num_words)

def generate_text(prompt):
    body = json.dumps({
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 3000,
            "temperature": 0.7,
            "topP": 0.9,
        }
    })
    
    response = bedrock.invoke_model(
        modelId="amazon.titan-text-premier-v1:0",
        body=body
    )
    response_body = json.loads(response.get('body').read())
    return response_body.get('results')[0].get('outputText')

def generate_image(prompt):
    body = json.dumps({
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {
            "text": prompt,
            "negativeText": "blurry, bad quality, distorted",
        },
        "imageGenerationConfig": {
            "numberOfImages": 1,
            "quality": "standard",
            "cfgScale": 8.0,
            "height": 512,
            "width": 512,
        }
    })
    
    response = bedrock.invoke_model(
        modelId="amazon.titan-image-generator-v2:0",
        body=body
    )
    response_body = json.loads(response.get('body').read())
    return response_body.get('images')[0]

def generate_quiz_questions(words):
    quiz_prompt = f"""Create 4 multiple choice questions to test the knowledge of these words: {', '.join(words)}
Each question should be in this exact format:
Q: [Question text]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
Correct: [A/B/C/D]
Explanation: [Brief explanation why this is correct]
---
Make sure each question tests different aspects (meaning, usage, context) and each word is used at least once."""

    response = generate_text(quiz_prompt)
    
    # Parse the response into structured questions
    questions = []
    current_question = {}
    
    for line in response.split('\n'):
        line = line.strip()
        if not line or line == '---':
            if current_question:
                questions.append(current_question)
                current_question = {}
            continue
            
        if line.startswith('Q:'):
            if current_question:
                questions.append(current_question)
            current_question = {'question': line[2:].strip()}
        elif line.startswith('A)'):
            current_question['A'] = line[2:].strip()
        elif line.startswith('B)'):
            current_question['B'] = line[2:].strip()
        elif line.startswith('C)'):
            current_question['C'] = line[2:].strip()
        elif line.startswith('D)'):
            current_question['D'] = line[2:].strip()
        elif line.startswith('Correct:'):
            current_question['correct'] = line[8:].strip()
        elif line.startswith('Explanation:'):
            current_question['explanation'] = line[12:].strip()
    
    if current_question:
        questions.append(current_question)
    
    return questions

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten kullanılıyor.')
            return redirect(url_for('signup'))
        
        user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        return redirect(url_for('home'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('home'))
        
        flash('Geçersiz kullanıcı adı veya şifre.')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    # Kullanıcının mevcut gününe ait kelimeleri kontrol et
    progress = UserProgress.query.filter_by(
        user_id=current_user.id,
        day=current_user.current_day,
        completed=False
    ).first()
    
    if not progress:
        # Yeni kelimeler seç ve kaydet
        words = get_random_words()
        progress = UserProgress(
            user_id=current_user.id,
            day=current_user.current_day,
            words=json.dumps(words)
        )
        db.session.add(progress)
        db.session.commit()
    else:
        words = json.loads(progress.words)
    
    return render_template('day.html', words=words)

@app.route('/learn')
@login_required
def learn():
    words = request.args.getlist('words')
    word_details = []
    
    for word in words:
        # Kelime tanımını ve örnekleri al
        definition_prompt = f"""For the word '{word}', provide ONLY its top 3 most commonly used meanings (if it has less than 3 meanings, provide only the existing ones). Use this format:

1st Most Common Meaning:
[Definition]
Example: [A clear example sentence showing this meaning]

2nd Most Common Meaning (if exists):
[Definition]
Example: [A clear example sentence showing this meaning]

3rd Most Common Meaning (if exists):
[Definition]
Example: [A clear example sentence showing this meaning]

Note: Only provide real, commonly used meanings. If the word has less than 3 meanings, only provide the existing ones."""

        text_response = generate_text(definition_prompt)
        
        # Yanıtı parse et
        meanings = []
        current_meaning = None
        
        for line in text_response.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if "Most Common Meaning" in line:
                if current_meaning:
                    meanings.append(current_meaning)
                if len(meanings) >= 3:  # En fazla 3 anlam
                    break
                order = len(meanings) + 1
                current_meaning = {'order': order}
            elif line.startswith('Example:'):
                if current_meaning:
                    current_meaning['example'] = line.replace('Example:', '').strip()
            elif line and current_meaning and 'definition' not in current_meaning:
                current_meaning['definition'] = line
        
        if current_meaning and len(meanings) < 3:
            meanings.append(current_meaning)
        
        # Her anlam için görsel oluştur
        for meaning in meanings:
            image_prompt = f"""Describe visually the meaning of word '{word}' in this sentence: {meaning['example']}

Requirements:
- Natural and realistic scene
- No text in the image
- Simple background
- Clear focus on the action or object being described"""
            
            meaning['image'] = generate_image(image_prompt)
        
        word_details.append({
            'word': word,
            'meanings': meanings
        })
    
    return render_template('learn.html', word_details=word_details)

@app.route('/story')
@login_required
def story():
    words = request.args.getlist('words')
    prompt = f"Write a simple, short story using these words: {', '.join(words)}. The story should be easy to understand and help in learning these words."
    story_text = generate_text(prompt)
    return render_template('story.html', story=story_text, words=words)

@app.route('/summary')
@login_required
def summary():
    words = request.args.getlist('words')
    
    # Günü tamamla ve bir sonraki güne geç
    progress = UserProgress.query.filter_by(
        user_id=current_user.id,
        day=current_user.current_day
    ).first()
    
    if progress and not progress.completed:
        progress.completed = True
        progress.date_completed = datetime.utcnow()
        current_user.current_day += 1
        db.session.commit()
    
    # Quiz sorularını oluştur
    questions = generate_quiz_questions(words)
    
    # Quiz sorularını session'da sakla
    session['quiz_questions'] = questions
    session['quiz_words'] = words
    
    return render_template('summary.html', words=words)

@app.route('/quiz')
@login_required
def quiz():
    questions = session.get('quiz_questions')
    words = session.get('quiz_words')
    
    if not questions or not words:
        return redirect(url_for('home'))
    
    return render_template('quiz.html', questions=questions, words=words)

@app.route('/quiz_result', methods=['POST'])
@login_required
def quiz_result():
    questions = session.get('quiz_questions')
    user_answers = request.form
    
    results = []
    total_correct = 0
    
    for i, q in enumerate(questions):
        answer_key = f'q{i}'
        is_correct = user_answers.get(answer_key) == q['correct']
        if is_correct:
            total_correct += 1
            
        results.append({
            'question': q['question'],
            'user_answer': user_answers.get(answer_key),
            'correct_answer': q['correct'],
            'is_correct': is_correct,
            'explanation': q['explanation'],
            'options': {
                'A': q['A'],
                'B': q['B'],
                'C': q['C'],
                'D': q['D']
            }
        })
    
    score_percentage = (total_correct / len(questions)) * 100
    
    return render_template('quiz_result.html', 
                         results=results, 
                         total_correct=total_correct, 
                         total_questions=len(questions),
                         score_percentage=score_percentage)

@app.route('/dashboard')
@login_required
def dashboard():
    # Kullanıcının tüm ilerlemesini al
    progress_list = UserProgress.query.filter_by(
        user_id=current_user.id
    ).order_by(UserProgress.day.desc()).all()
    
    # Her ilerleme için kelime listesini JSON'dan parse et
    for progress in progress_list:
        progress.word_list = json.loads(progress.words)
    
    return render_template('dashboard.html', progress_list=progress_list)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 