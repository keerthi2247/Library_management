from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret123'

# Database setup
def init_db():
    conn = sqlite3.connect('library.db')
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    enrollment_number TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)""")


    cur.execute("""CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT,
        genre TEXT,
        total_quantity INTEGER,
        available_quantity INTEGER
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        book_id INTEGER,
        issue_date TEXT,
        return_date TEXT,
        status TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id),
        FOREIGN KEY(book_id) REFERENCES books(id)
    )""")
    

    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        enrollment_number = request.form['enrollment_number']
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('library.db')
        cur = conn.cursor()
        cur.execute("INSERT INTO students (name, enrollment_number, email, password) VALUES (?, ?, ?, ?)", 
                    (name, enrollment_number, email, password))
        conn.commit()
        conn.close()
        return redirect('/login')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        enrollment_number = request.form['enrollment_number']
        password = request.form['password']

        conn = sqlite3.connect('library.db')
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE enrollment_number=? AND password=?", (enrollment_number, password))
        student = cur.fetchone()
        conn.close()

        if student:
            session['student_id'] = student[0]
            return redirect('/student/dashboard')
    return render_template('student_login.html')


@app.route('/student/dashboard')
def student_dashboard():
    if 'student_id' not in session:
        return redirect('/student/login')

    conn = sqlite3.connect('library.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    student_id = session['student_id']
    student = cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()

    transactions = cursor.execute("""
        SELECT transactions.*, books.title as book_title 
        FROM transactions 
        JOIN books ON transactions.book_id = books.id 
        WHERE transactions.student_id = ?
    """, (student_id,)).fetchall()

    conn.close()
    return render_template('student_dashboard.html', student=student, transactions=transactions)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'admin' and password == 'admin':
            session['admin'] = True
            return redirect('/admin/dashboard')
    return render_template('admin_login.html')

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin/login')

    conn = sqlite3.connect('library.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == 'POST' and 'title' in request.form:
        title = request.form['title']
        author = request.form['author']
        genre = request.form['genre']
        quantity = int(request.form['quantity'])

        cur.execute("SELECT * FROM books WHERE title = ? AND author = ?", (title, author))
        existing = cur.fetchone()
        if existing:
            cur.execute("""
                UPDATE books 
                SET total_quantity = total_quantity + ?, available_quantity = available_quantity + ?
                WHERE title = ? AND author = ?
            """, (quantity, quantity, title, author))
        else:
            cur.execute("""
                INSERT INTO books (title, author, genre, total_quantity, available_quantity)
                VALUES (?, ?, ?, ?, ?)""",
                (title, author, genre, quantity, quantity))

        conn.commit()

    # Book search + sort
    search = request.args.get('search', '')
    cur.execute("SELECT * FROM books WHERE title LIKE ? ORDER BY title ASC", ('%' + search + '%',))
    books = cur.fetchall()

    # Student transaction search
    transactions = []
    roll_search = request.args.get('roll_number')
    if roll_search:
        cur.execute("SELECT id FROM students WHERE enrollment = ?", (roll_search,))
        student = cur.fetchone()
        if student:
            cur.execute("""
                SELECT transactions.*, books.title as book_title FROM transactions 
                JOIN books ON books.id = transactions.book_id
                WHERE transactions.student_id = ?""", (student['id'],))
            transactions = cur.fetchall()

    conn.close()
    return render_template('admin_dashboard.html', books=books, transactions=transactions)

@app.route('/admin/issue', methods=['POST'])
def admin_issue_book():
    student_name = request.form['student_name']
    enrollment_number = request.form['enrollment_number']
    book_id = request.form['book_id']

    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    student = cursor.execute(
        "SELECT id FROM students WHERE name=? AND enrollment_number=?", 
        (student_name, enrollment_number)
    ).fetchone()

    if student:
        student_id = student[0]

        cursor.execute("""
            INSERT INTO transactions (student_id, book_id, status, issue_date)
            VALUES (?, ?, 'Issued', DATE('now'))
        """, (student_id, book_id))

        cursor.execute("""
            UPDATE books SET available_quantity = available_quantity - 1 WHERE id = ?
        """, (book_id,))

        conn.commit()
        conn.close()
        return redirect('/admin/dashboard')
    else:
        conn.close()
        return "Student not found", 404


@app.route('/admin/return', methods=['POST'])
def admin_return_book():
    student_name = request.form['student_name']
    enrollment_number = request.form['enrollment_number']
    book_id = request.form['book_id']

    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    student = cursor.execute(
        "SELECT id FROM students WHERE name=? AND enrollment_number=?", 
        (student_name, enrollment_number)
    ).fetchone()

    if student:
        student_id = student[0]

        cursor.execute("""
            UPDATE transactions
            SET status = 'Returned', return_date = DATE('now')
            WHERE student_id = ? AND book_id = ? AND status = 'Issued'
        """, (student_id, book_id))

        cursor.execute("""
            UPDATE books SET available_quantity = available_quantity + 1 WHERE id = ?
        """, (book_id,))

        conn.commit()
        conn.close()
        return redirect('/admin/dashboard')
    else:
        conn.close()
        return "Student not found", 404
@app.route('/admin/transactions', methods=['POST'])
def admin_transactions():
    enrollment_number = request.form.get('enrollment_number')

    
    conn = sqlite3.connect('library.db')
    cur = conn.cursor()

    # Fetch the student ID using enrollment number
    cur.execute("SELECT id, name FROM students WHERE enrollment_number = ?", (enrollment_number,))
    student = cur.fetchone()

    if not student:
        conn.close()
        return "Student not found."

    student_id, student_name = student

    # Fetch transactions for this student
    cur.execute('''
        SELECT books.title, transactions.issue_date, transactions.return_date, transactions.status
        FROM transactions
        JOIN books ON transactions.book_id = books.id
        WHERE transactions.student_id = ?
    ''', (student_id,))
    transactions = cur.fetchall()

    conn.close()

    return render_template('admin_transactions.html', student_name=student_name, transactions=transactions)


if __name__ == '__main__':
    app.run(debug=True)
