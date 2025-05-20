from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql.connector
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import os
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'aiva_laundry'
CORS(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="@aine",
    database="aiva_laundry"
)
cursor = db.cursor()

EMAIL_ADDRESS = "info@aivalaundry.com"
EMAIL_PASSWORD = "your-email-password"

class Admin(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    cursor.execute("SELECT id, username FROM admins WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if user:
        return Admin(user[0], user[1])
    # Check regular users
    cursor.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if user:
        return RegularUser(user[0], user[1])
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not hasattr(current_user, 'username'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute("SELECT id FROM admins WHERE username = %s", (username,))
        if cursor.fetchone():
            flash("Username already exists", "error")
            return redirect(url_for('register'))
        password_hash = generate_password_hash(password)
        try:
            cursor.execute("INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
                          (username, password_hash))
            db.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Registration failed: {e}", "error")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute("SELECT id, username, password_hash FROM admins WHERE username = %s", (username,))
        admin = cursor.fetchone()
        if not admin or not check_password_hash(admin[2], password):
            flash("Invalid credentials", "error")
            return redirect(url_for('login'))
        user = Admin(admin[0], admin[1])
        login_user(user)
        return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/order', methods=['GET', 'POST'])
def order():
    if request.method == 'POST':
        service = request.form['service']
        detergent = request.form['detergent']
        payment_method = request.form['payment_method']
        email = request.form['email']
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user:
            user_id = user[0]
        else:
            cursor.execute("INSERT INTO users (email) VALUES (%s)", (email,))
            db.commit()
            user_id = cursor.lastrowid
        cursor.execute("INSERT INTO orders (item_id, user_id, payment_method, status) VALUES ((SELECT id FROM items WHERE name = %s LIMIT 1), %s, %s, 'Pending')", (detergent or service, user_id, payment_method))
        db.commit()
        order_id = cursor.lastrowid
        receipt_file = generate_receipt(order_id, f"{service} with {detergent}" if service and detergent else service or detergent, payment_method)
        flash("Order placed successfully! Download your receipt below.", "success")
        return render_template('order.html', receipt_file=receipt_file)
    return render_template('order.html')

@app.route('/download_receipt/<path:filename>')
def download_receipt(filename):
    return send_file(filename, as_attachment=True)

@app.route('/api/admin/update_status/<int:order_id>', methods=['POST'])
@admin_required
def update_status(order_id):
    data = request.json
    cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (data['status'], order_id))
    db.commit()
    return jsonify({"success": True})

@app.route('/api/admin/order_history/<int:user_id>', methods=['GET'])
@admin_required
def order_history(user_id):
    cursor.execute("""
        SELECT o.id, i.name, o.payment_method, o.status, d.method
        FROM orders o
        JOIN items i ON o.item_id = i.id
        LEFT JOIN delivery_methods d ON o.delivery_method_id = d.id
        WHERE o.user_id = %s
    """, (user_id,))
    orders = [{"id": row[0], "item": row[1], "payment_method": row[2], "status": row[3], "delivery_method": row[4]} for row in cursor.fetchall()]
    return jsonify(orders)

@app.route('/categories')
def categories():
    cursor.execute("SELECT name, description FROM items")
    items = cursor.fetchall()
    return render_template('categories.html', items=items)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        email = request.form['email']
        message = request.form['message']
        send_email(EMAIL_ADDRESS, "New Contact", f"From: {email}\nMessage: {message}")
        flash("Message sent!", "success")
    return render_template('contact.html')

def generate_receipt(order_id, item, payment_method):
    filename = f"receipt_{order_id}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    elements.append(Paragraph("AIVA Laundry and Detergent Services", styles['Title']))
    elements.append(Paragraph("123 Laundry Lane, Kampala, Uganda", styles['Normal']))
    elements.append(Paragraph("Email: info@aivalaundry.com | Phone: +256 123 456 789", styles['Normal']))
    elements.append(Spacer(1, 0.2 * inch))

    # Logo
    logo_path = "logo.png"
    try:
        if os.path.exists(logo_path):
            elements.append(Image(logo_path, width=1*inch, height=1*inch))
        else:
            elements.append(Paragraph("[Logo Missing - Add logo.png to project directory]", styles['Normal']))
    except Exception as e:
        elements.append(Paragraph(f"[Logo Error: {e}]", styles['Normal']))
    elements.append(Spacer(1, 0.2 * inch))

    # Receipt Details
    elements.append(Paragraph(f"Receipt for Order #{order_id}", styles['Heading2']))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph(f"Item: {item}", styles['Normal']))
    elements.append(Paragraph(f"Payment Method: {payment_method}", styles['Normal']))
    elements.append(Paragraph(f"Date: {datetime.datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    elements.append(Spacer(1, 0.2 * inch))

    # Footer
    elements.append(Paragraph("Thank you for choosing AIVA Laundry!", styles['Normal']))
    elements.append(Paragraph("For inquiries, contact us at info@aivalaundry.com", styles['Normal']))

    doc.build(elements)
    return filename

def send_email(to_email, subject, body, attachment=None):
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg.attach(MIMEText(body))
    if attachment:
        with open(attachment, 'rb') as f:
            part = MIMEApplication(f.read(), Name=attachment)
            part['Content-Disposition'] = f'attachment; filename={attachment}'
            msg.attach(part)
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/api/admin/orders', methods=['GET'])
@admin_required
def get_orders():
    cursor.execute("""
        SELECT o.id, i.name, u.email, o.payment_method, o.status, d.method
        FROM orders o
        JOIN items i ON o.item_id = i.id
        JOIN users u ON o.user_id = u.id
        LEFT JOIN delivery_methods d ON o.delivery_method_id = d.id
    """)
    orders = [{"id": row[0], "item": row[1], "email": row[2], "payment_method": row[3], "status": row[4], "delivery_method": row[5]} for row in cursor.fetchall()]
    return jsonify(orders)

@app.route('/api/admin/add_item', methods=['POST'])
@admin_required
def add_item():
    data = request.json
    cursor.execute("INSERT INTO items (name, description, category, stock) VALUES (%s, %s, %s, %s)",
                  (data['name'], data['description'], data['category'], data['stock']))
    db.commit()
    return jsonify({"success": True})

@app.route('/api/admin/remove_item/<int:item_id>', methods=['DELETE'])
@admin_required
def remove_item(item_id):
    cursor.execute("DELETE FROM items WHERE id = %s", (item_id,))
    db.commit()
    return jsonify({"success": True})

@app.route('/api/admin/set_delivery/<int:order_id>', methods=['POST'])
@admin_required
def set_delivery(order_id):
    data = request.json
    cursor.execute("UPDATE orders SET delivery_method_id = (SELECT id FROM delivery_methods WHERE method = %s LIMIT 1) WHERE id = %s",
                  (data['method'], order_id))
    db.commit()
    return jsonify({"success": True})

class RegularUser(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email

@app.route('/user/register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("Email already registered", "error")
            return redirect(url_for('user_register'))
        password_hash = generate_password_hash(password)
        cursor.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)", (email, password_hash))
        db.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('user_login'))
    return render_template('user_register.html')

@app.route('/user/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user or not check_password_hash(user[2], password):
            flash("Invalid credentials", "error")
            return redirect(url_for('user_login'))
        user_obj = RegularUser(user[0], user[1])
        login_user(user_obj)
        return redirect(url_for('user_orders'))
    return render_template('user_login.html')

@app.route('/user/orders')
@login_required
def user_orders():
    cursor.execute("""
        SELECT o.id, i.name, o.payment_method, o.status, d.method
        FROM orders o
        JOIN items i ON o.item_id = i.id
        LEFT JOIN delivery_methods d ON o.delivery_method_id = d.id
        WHERE o.user_id = %s
    """, (current_user.id,))
    orders = cursor.fetchall()
    return render_template('user_orders.html', orders=orders)

if __name__ == '__main__':
    app.run(debug=True)