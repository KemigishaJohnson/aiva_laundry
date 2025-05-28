from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
import mysql.connector
import bcrypt
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import session
import hashlib

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.secret_key = 'aiva_laundry'
CORS(app)

# MySQL Configuration
db_config = {
    'user': 'root',
    'password': '@aine',
    'host': 'localhost',
    'database': 'aiva_laundry'
}

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'user_login'

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user[0], user[1], user[2])
    return None

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/categories')
def categories():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, picture FROM categories")
    categories = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('categories.html', items=categories)

@app.route('/order', methods=['GET', 'POST'])
def order():
    if request.method == 'POST':
        service = request.form['service'].split(' (')[0]
        detergent = request.form['detergent'].split(' (')[0]
        user_name = request.form['user_name']
        telephone = request.form['telephone']
        region = request.form['region']
        email = request.form['email']
        payment_method = request.form['payment_method']
        delivery_method = 'Not Set'
        user_id = current_user.id if current_user.is_authenticated else None

        # Insert order into database first to get the order ID
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO orders (user_id, service, detergent, user_name, telephone, region, email, payment_method, status, delivery_method)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, service, detergent, user_name, telephone, region, email, payment_method, 'Pending', delivery_method)
        )
        order_id = cursor.lastrowid  # Get the ID of the newly inserted order
        print(f"Inserted order with ID: {order_id}")  # Debug log
        conn.commit()
        cursor.close()
        conn.close()

        if not order_id:
            flash('Failed to create order. Please try again.', 'error')
            return redirect(url_for('order'))

        # Generate receipt filename using order ID
        receipt_filename = f"receipt_{order_id}.pdf"
        receipt_path = os.path.join('static/receipts', receipt_filename)

        # Create PDF receipt
        try:
            os.makedirs(os.path.dirname(receipt_path), exist_ok=True)
            pdf = canvas.Canvas(receipt_path, pagesize=letter)
            pdf.drawString(100, 750, "AIVA Laundry Receipt")
            pdf.drawString(100, 735, f"Order Date: {datetime.now()}")
            pdf.drawString(100, 720, f"Service: {service}")
            pdf.drawString(100, 705, f"Detergent: {detergent}")
            pdf.drawString(100, 690, f"Full Name: {user_name}")
            pdf.drawString(100, 675, f"Telephone: {telephone}")
            pdf.drawString(100, 660, f"Region: {region}")
            pdf.drawString(100, 645, f"Email: {email}")
            pdf.drawString(100, 630, f"Payment Method: {payment_method}")
            pdf.drawString(100, 615, f"Delivery Method: {delivery_method}")
            pdf.save()
            print(f"Receipt created at: {receipt_path}")  # Debug log
        except Exception as e:
            print(f"Error creating receipt: {e}")
            flash('Order placed, but failed to generate receipt. Contact support.', 'error')

        # Send email confirmation
        msg = MIMEMultipart()
        msg['From'] = 'your_actual_email@gmail.com'
        msg['To'] = email
        msg['Subject'] = 'Order Confirmation - AIVA Laundry'
        body = f"""
        Dear {user_name},
        Your order has been placed successfully!
        Service: {service}
        Detergent: {detergent}
        Full Name: {user_name}
        Telephone: {telephone}
        Region: {region}
        Email: {email}
        Payment Method: {payment_method}
        Delivery Method: {delivery_method}
        Order Date: {datetime.now()}
        Download your receipt: {url_for('download_receipt', filename=receipt_filename, _external=True)}
        Thank you for choosing AIVA Laundry!
        """
        msg.attach(MIMEText(body, 'plain'))
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login('your_actual_email@gmail.com', 'your_app_password')
            server.sendmail('your_actual_email@gmail.com', email, msg.as_string())
            server.quit()
            flash('Order placed successfully! A confirmation email and receipt have been sent.', 'success')
        except smtplib.SMTPAuthenticationError as e:
            print(f"Email sending error: {e}")
            flash('Order placed, but failed to send email. Please check your SMTP credentials.', 'error')
            return redirect(url_for('order'))

        return redirect(url_for('index'))

    return render_template('order.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        email = request.form['email']
        message = request.form['message']

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO contacts (email, message) VALUES (%s, %s)", (email, message))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Message sent successfully!', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html')

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Access denied. Only admins can access this page.', 'error')
        return redirect(url_for('index'))

    conn = mysql.connector.connect(**db_config)
    # Fetch orders as dictionaries
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            o.id,
            o.user_name,
            c.name AS category_name,
            o.service,
            o.detergent,
            o.payment_method,
            o.status,
            o.delivery_method
        FROM orders o
        LEFT JOIN categories c ON o.category_id = c.id
        ORDER BY o.id DESC
    """)
    orders = cursor.fetchall()

    # Fetch categories as dictionaries
    cursor.execute("SELECT id, name, price, picture FROM categories")
    categories = cursor.fetchall()

    # Fetch admins as dictionaries
    cursor.execute("SELECT id, username FROM users WHERE role = 'admin'")
    admins = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin.html', orders=orders, categories=categories, admins=admins)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print(f"Attempting login for username: {username}")
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = %s AND role = 'admin'", (username,))
        user = cursor.fetchone()
        print(f"User found: {user}")
        cursor.close()
        conn.close()
        if user:
            stored_hash = user[2].encode('utf-8')  # Convert stored hash to bytes
            password_bytes = password.encode('utf-8')  # Convert password to bytes
            print(f"Stored hash: {stored_hash}")
            # Verify using bcrypt
            try:
                password_match = bcrypt.checkpw(password_bytes, stored_hash)
                print(f"Password check result: {password_match}")
                if password_match:
                    user_obj = User(user[0], user[1], user[3])
                    login_user(user_obj)
                    flash('Logged in successfully.', 'success')
                    return redirect(url_for('admin'))
                else:
                    flash('Invalid password.', 'error')
            except ValueError as e:
                print(f"Error verifying password: {e}")
                flash('Invalid password hash format.', 'error')
        else:
            flash('Invalid username or admin access required.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/add_admin', methods=['POST'])
@login_required
def add_admin():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    username = request.form['username']
    password = request.form['password']
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        flash('Username already exists.', 'error')
    else:
        # Hash password using bcrypt
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'admin')", (username, hashed_password))
        conn.commit()
        flash('Admin added successfully.', 'success')
    cursor.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/add_category', methods=['POST'])
@login_required
def add_category():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    name = request.form['name']
    price = float(request.form['price'])
    picture = request.form.get('picture', '')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (name, price, picture) VALUES (%s, %s, %s)", (name, price, picture))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Category added successfully.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/update_price/<int:category_id>', methods=['POST'])
@login_required
def update_price(category_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    price = float(request.form['price'])
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE categories SET price = %s WHERE id = %s", (price, category_id))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Price updated successfully.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/remove_category/<int:category_id>', methods=['POST'])
@login_required
def remove_category(category_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Category removed successfully.', 'success')
    return redirect(url_for('admin'))

@app.route('/user/orders')
@login_required
def user_orders():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT id, service, detergent, user_name, telephone, region, email, payment_method, status, delivery_method 
           FROM orders 
           WHERE user_id = %s""",
        (current_user.id,)
    )
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('user_orders.html', orders=orders)

@app.route('/user/login', methods=['GET', 'POST'])
def user_login():
    session['from_login'] = True
    if request.method == 'POST':
        username = request.form['email']
        password = request.form['password']
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            stored_hash = user[2].encode('utf-8')
            password_bytes = password.encode('utf-8')
            try:
                password_match = bcrypt.checkpw(password_bytes, stored_hash)
                if password_match:
                    user_obj = User(user[0], user[1], user[3])
                    login_user(user_obj)
                    flash('Logged in successfully.', 'success')
                    return redirect(url_for('index'))
                else:
                    flash('Invalid email or password.', 'error')
            except ValueError as e:
                flash('Invalid password hash format.', 'error')
        else:
            flash('Invalid email or password.', 'error')
    return render_template('user_login.html')

@app.route('/user/register', methods=['GET', 'POST'])
def user_register():
    if not session.get('from_login'):
        flash('Please visit the login page first.', 'error')
        return redirect(url_for('user_login'))
    if request.method == 'POST':
        username = request.form['email']
        password = request.form['password']
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash('Email already exists.', 'error')
        else:
            # Hash password using bcrypt
            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
            cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'user')", (username, hashed_password))
            conn.commit()
            flash('Registration successful. Please log in.', 'success')
            session.pop('from_login', None)
            return redirect(url_for('user_login'))
        cursor.close()
        conn.close()
    return render_template('user_register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

# API Endpoints for Admin
@app.route('/api/admin/orders', methods=['GET'])
@login_required
def api_admin_orders():
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied.'}), 403
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, user_name, category_name, quantity, total_amount, order_date, status, service, detergent, delivery_method FROM orders")
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(orders)

@app.route('/api/admin/add_item', methods=['POST'])
@login_required
def api_add_item():
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied.'}), 403
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')
    category = data.get('category')
    stock = data.get('stock')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (name, price, picture) VALUES (%s, 0.00, '')", (name,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/set_delivery/<int:order_id>', methods=['POST'])
@login_required
def api_set_delivery(order_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied.'}), 403
    data = request.get_json()
    method = data.get('method')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET delivery_method = %s WHERE id = %s", (method, order_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/update_status/<int:order_id>', methods=['POST'])
@login_required
def api_update_status(order_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied.'}), 403
    data = request.get_json()
    status = data.get('status')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

@app.route('/download_receipt/<filename>')
def download_receipt(filename):
    file_path = os.path.join('static/receipts', filename)
    print(f"Attempting to download: {file_path}")  # Debug log
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash('Receipt not found. Please contact support.', 'error')
        return redirect(url_for('user_orders'))

@app.route('/set_delivery/<int:order_id>', methods=['POST'])
@login_required
def set_delivery(order_id):
    if current_user.role != 'admin':
        flash('Access denied. Only admins can set delivery methods.', 'error')
        return redirect(url_for('admin'))
    
    delivery_method = request.form['delivery_method']
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE orders SET delivery_method = %s WHERE id = %s""",
        (delivery_method, order_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    flash('Delivery method updated successfully.', 'success')
    return redirect(url_for('admin'))

@app.route('/update_status/<int:order_id>', methods=['POST'])
@login_required
def update_status(order_id):
    if current_user.role != 'admin':
        flash('Access denied. Only admins can update status.', 'error')
        return redirect(url_for('admin'))
    
    status = request.form['status']
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE orders SET status = %s WHERE id = %s""",
        (status, order_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    flash('Status updated successfully.', 'success')
    return redirect(url_for('admin'))

@app.route('/view_history/<int:order_id>')
@login_required
def view_history(order_id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT * FROM orders WHERE id = %s""",
        (order_id,)
    )
    order = cursor.fetchone()
    cursor.close()
    conn.close()
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('admin' if current_user.role == 'admin' else 'user_orders'))
    return render_template('order_history.html', order=order)

if __name__ == '__main__':
    app.run(debug=True)