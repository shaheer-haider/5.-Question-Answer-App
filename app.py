from flask import Flask, render_template, g, request, session, redirect, url_for
from database_helpers import connect_db, get_db
from werkzeug.security import generate_password_hash, check_password_hash
from os import urandom

app = Flask(__name__)
app.config['SECRET_KEY'] = urandom(24)


def login_check():
    user_result = None
    if 'user' in session:
        user = session['user']

        db = get_db()
        user_cur = db.execute('select * from users where name=?', [user])
        user_result = user_cur.fetchone()
        if user_result is not None:
            return user_result


@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


@app.route('/')
def index():
    # this user is different variable and user in session is different
    # user remains None until it is not in session(login)
    user = login_check()
    db = get_db()
    if not user:
        hide_it = True
    else:
        hide_it = False

    questions_cur = db.execute('''select 
    questions.question_text,
    questions.id as question_id,
    test_user.name as test_user_name, 
    expert.name as expert_name from questions 
    
    join users as test_user on test_user.id = questions.asked_by_id 
    join users as expert on expert.id = questions.expert_id 
    
    where questions.answer_text is not null''')

    questions_result = questions_cur.fetchall()

    return render_template('home.html', user=user, all_answered_questions=questions_result)


@app.route('/register', methods=['GET', 'POST'])
def register():
    user = login_check()
    if user is not None:
        return redirect(url_for('index'))
    warn = ""
    if request.method == "POST":
        db = get_db()
        name = request.form['name']
        password = request.form['password']

        cur = db.execute('select name as nm from users where name = ?', [name])
        cur = cur.fetchone()

        if cur:
            warn = "This Username is already used"
        else:
            hashed_password = generate_password_hash(password, method='sha256')
            db.execute('insert into users (name, password, expert, admin) values (?, ?, ?, ?)',
                        [name, hashed_password, 0, 0])
            db.commit()
            warn = "User has been registered"
    return render_template('register.html', warn=warn)


@app.route('/login', methods=['GET', 'POST'])
def login():
    user = login_check()
    if user is not None:
        return redirect(url_for('index'))

    warning = ''
    if request.method == 'POST':
        db = get_db()
        name = request.form['name']
        password = request.form['password']

        user_cur = db.execute('select id, name, password from users where name=?', [name])
        user_result = user_cur.fetchone()
        if user_result is None:
            warning = 'Warning: User name not found...!'
        elif check_password_hash(user_result['password'], password):
            # session is really like dictionary but it can use with flask secret key
            session['user'] = user_result['name']
            return redirect(url_for('index'))

        else:
            warning = "Warning: Password is incorrect...!"
    return render_template('login.html', user=login_check(), warning=warning)


@app.route('/question/<question_id>')
def question(question_id):
    user = login_check()
    if user is None:
        return redirect(url_for('login'))
    db = get_db()
    cur = db.execute('''select 
    questions.question_text,
    questions.answer_text,
    asked_by.name as asked_by,
    answered_by.name as answered_by
    
    from questions join users as asked_by
    on asked_by.id = questions.asked_by_id 

    join users as answered_by
    on answered_by.id = questions.expert_id 
    
    where questions.id = ? ''', [question_id])

    question_all_data = cur.fetchone()

    return render_template('question.html', user=user, qad=question_all_data)


@app.route('/unanswered')
def unanswered():
    user = login_check()
    if user is None or user['expert'] == 0:
        return redirect(url_for('index'))

    db = get_db()
    # here user id will id of expert from whom test user was asked questions
    expert_id = user['id']

    questions_cur = db.execute('''select 
    questions.question_text as question_text,
    questions.id as question_id,
    users.name as name
    
    from questions join users
    on users.id = questions.asked_by_id
    
    where questions.answer_text is null 
    and questions.expert_id = ?''',
                               [expert_id])

    question_data = questions_cur.fetchall()

    return render_template('unanswered.html', user=user, question_data=question_data)


# answer others on this page it has a text box
@app.route('/answer/<id_of_question>', methods=["GET", "POST"])
def answer(id_of_question):
    user = login_check()

    if not user:
        return redirect(url_for('index'))

    db = get_db()
    cur = db.execute("select expert_id ,question_text from questions where id = ? and answer_text is not null",
                     [id_of_question])
    question_result = cur.fetchone()

    if question_result:
        question_found = 'Yes'
        question_text = question_result['question_text']

        if question_result['expert_id'] != user['id']:
            return redirect(url_for('login'))

    else:
        question_found = None
        question_text = "Question has been answered."

    if request.method == "POST":
        answer_by_expert = request.form['answer_by_expert']

        db.execute(""" update questions set answer_text = ? where id = ? """, [answer_by_expert, id_of_question])
        db.commit()
        return redirect(url_for('index'))
    return render_template('answer.html', user=login_check(), question_text=question_text,
                           id_of_question=id_of_question, question_found=question_found)


@app.route('/ask', methods=['GET', 'POST'])
def ask():
    user = login_check()

    if not user:
        return redirect(url_for('index'))
    elif user['expert'] != 0:
        return redirect(url_for('index'))

    db = get_db()
    cur = db.execute('select name, expert, id from users')
    user_names = cur.fetchall()

    if request.method == 'POST':
        expert_id, user_ques, user_id = request.form['selection'], request.form['question'], user['id']

        db.execute('''
        insert into questions 
        (question_text, asked_by_id, expert_id)
        values (?, ?, ?)''',
                   [user_ques, user_id, expert_id])
        db.commit()

    return render_template('ask.html', user_names=user_names, user=user)


@app.route('/users')
def users():
    user = login_check()
    if user is None or user['admin'] == 0:
        return redirect(url_for('index'))
    db = get_db()
    # get data of all users
    user_cur = db.execute('select id, name, expert, admin from users')
    user_result = user_cur.fetchall()
    return render_template('users.html', user=user, user_result=user_result)


@app.route('/promoted/<user_id>')
def promoted(user_id):
    db = get_db()
    cur = db.execute("select expert from users where id = ?", [user_id])
    exp = cur.fetchone()
    exp = exp['expert']
    if exp == 0:
        db.execute("update users set expert = 1 where id = ?", [user_id])
    elif exp == 1:
        db.execute("update users set expert = 0 where id = ?", [user_id])
    db.commit()
    return redirect(url_for('users'))


@app.route('/logout')
def logout():
    user = login_check()
    if user:
        session.pop('user', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
