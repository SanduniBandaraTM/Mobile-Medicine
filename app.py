from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask import jsonify
import base64
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import sqlite3
import os
from decimal import Decimal
from werkzeug.utils import secure_filename
from flask_mail import Mail
from datetime import datetime
from werkzeug.utils import secure_filename
from geopy.distance import geodesic


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for flash messages

@app.template_filter('b64encode')
def b64encode_filter(data):
    return base64.b64encode(data).decode('utf-8')

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Use your mail server (Gmail, Outlook, etc.)
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sandunibandara521@gmail.com'
app.config['MAIL_PASSWORD'] = 'cjqn ssjz dzbe mdkf'
mail = Mail(app)

    
# Initialize URL serializer for generating secure tokens
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

def get_db_connection():
    conn = sqlite3.connect('mobile_medicine.db', timeout=30, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')  # Enable Write-Ahead Logging
    conn.row_factory = sqlite3.Row
    return conn



# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Set the upload folder path
app.config['UPLOAD_FOLDER'] = 'uploads'  # Set the path to store temporary uploaded files

# Ensure the folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
    
# Check if uploaded file is an allowed image type
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Convert image to binary data
def convert_to_binary(file):
    with open(file, 'rb') as file:
        blob_data = file.read()
    return blob_data

def send_reset_email(user_email, reset_url):
    msg = Message('Password Reset Request', sender='noreply@demo.com', recipients=[user_email])
    msg.body = f'''To reset your password, visit the following link:
{reset_url}
If you did not make this request, simply ignore this email.
'''
    mail.send(msg)

def create_inventory_table():
    try:
        # Establish a connection with a longer timeout
        conn = sqlite3.connect('mobile_medicine.db', timeout=10)
        cursor = conn.cursor()
        
        # Create the inventory table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pharmacy_email TEXT NOT NULL,
            medicine_name TEXT NOT NULL,
            brand_name TEXT NOT NULL,
            category TEXT NOT NULL,
            form TEXT NOT NULL,
            dosage TEXT NOT NULL,
            medicine_code TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            availability TEXT NOT NULL,
            FOREIGN KEY (pharmacy_email) REFERENCES users(pharmacy_email)
        )
        ''')
        conn.commit()  # Commit changes
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()  # Ensure the connection is always closed



# Call the function to create the inventory table
create_inventory_table()

def get_pharmacies_with_medicine(medicine_name, customer_lat, customer_lon):
    conn = sqlite3.connect('mobile_medicine.db')
    cursor = conn.cursor()
    
    # Fetch pharmacies with the requested medicine in stock
    cursor.execute('''
        SELECT u.pharmacy_name, u.pharmacy_email, u.pharmacy_mobile_number, u.pharmacy_location_latitude, u.pharmacy_location_longitude, i.medicine_name
        FROM inventory i
        JOIN users u ON i.pharmacy_email = u.pharmacy_email
        WHERE i.medicine_name LIKE ? AND i.availability = "In Stock"
    ''', ('%' + medicine_name + '%',))
    
    pharmacies = cursor.fetchall()
    conn.close()

    # Calculate distance from the customer to each pharmacy
    result = []
    for pharmacy in pharmacies:
        pharmacy_name, pharmacy_email, pharmacy_mobile_number, pharmacy_lat, pharmacy_lon, med_name = pharmacy
        pharmacy_location = (pharmacy_lat, pharmacy_lon)
        customer_location = (customer_lat, customer_lon)
        distance = geodesic(customer_location, pharmacy_location).km
        result.append((pharmacy_name, pharmacy_email, pharmacy_mobile_number, round(distance, 3), med_name))

    # Sort pharmacies by distance
    result.sort(key=lambda x: x[3])
    return result

@app.route('/')
def index():
    return render_template('index.html')  # This will render the homepage

@app.route('/search_medicine', methods=['GET'])
def search_medicine():
    medicine_name = request.args.get('medicine_name')
    print(medicine_name)  # Debug the value in the console
    customer_lat = request.args.get('latitude', 0.0)  # Get latitude from the customer’s current location
    customer_lon = request.args.get('longitude', 0.0)  # Get longitude from the customer’s current location

    pharmacies = get_pharmacies_with_medicine(medicine_name, customer_lat, customer_lon)

    return render_template('pharmacy_lists.html', pharmacies=pharmacies)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form['role']
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            email = None

            if role == 'customer':
                customer_name = request.form['customer_name']
                customer_mobile_number = request.form['customer_mobile_number']
                customer_email = request.form['customer_email']
                customer_password = request.form['customer_password']
                email = customer_email

            elif role == 'pharmacy-owner':
                pharmacy_name = request.form['pharmacy_name']
                pharmacy_owner_name = request.form['pharmacy_owner_name']
                pharmacy_email = request.form['pharmacy_email']
                pharmacy_mobile_number = request.form['pharmacy_mobile_number']
                license_number = request.form['license_number']
                pharmacy_location_latitude = request.form['latitude']
                pharmacy_location_longitude = request.form['longitude']
                pharmacy_password = request.form['pharmacy_password']
                email = pharmacy_email
                
            # Check if the email already exists in either customer_email or pharmacy_email
            cursor.execute('''
                SELECT * FROM users WHERE customer_email = ? OR pharmacy_email = ?
            ''', (email, email))
            existing_user = cursor.fetchone()

            if existing_user:
                flash('Email is already registered')
                return redirect(url_for('register'))

            # Insert the user data into the table based on role
            if role == 'customer':
                cursor.execute('''
                    INSERT INTO users (role, customer_name, customer_mobile_number, customer_email, customer_password)
                    VALUES (?, ?, ?, ?, ?)
                ''', (role, customer_name, customer_mobile_number, customer_email, customer_password))

            elif role == 'pharmacy-owner':
                cursor.execute('''
                    INSERT INTO users (role, pharmacy_name, pharmacy_owner_name, pharmacy_email, pharmacy_mobile_number, 
                                    license_number, pharmacy_location_latitude, pharmacy_location_longitude, pharmacy_password)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (role, pharmacy_name, pharmacy_owner_name, pharmacy_email, pharmacy_mobile_number, license_number, 
                    pharmacy_location_latitude, pharmacy_location_longitude, pharmacy_password))

            conn.commit()
            flash('Registration successful!')
            return redirect(url_for('login'))

        except Exception as e:
            conn.rollback()  # Rollback in case of error
            flash(f'Error during registration: {e}')
    

        finally:
            conn.close()  # Ensure connection is closed properly

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT admin_password FROM admin WHERE admin_email = ?
        ''', (email,))
        admin = cursor.fetchone()

        # Check if the email exists for a customer
        cursor.execute('''
            SELECT customer_password FROM users WHERE customer_email = ?
        ''', (email,))
        customer = cursor.fetchone()

        # Check if the email exists for a pharmacy owner
        cursor.execute('''
            SELECT pharmacy_password FROM users WHERE pharmacy_email = ?
        ''', (email,))
        pharmacy_owner = cursor.fetchone()

        conn.close()
        
        # Admin login validation
        if admin:  # If email exists for admin
            if password == admin['admin_password']:
                session['admin_email'] = email
                flash('Admin login successful!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                print("Invalid password!")  # Debugging print
                flash("Invalid password for Admin! Try Again.", 'danger')
                return redirect(url_for('login'))

        if customer:  # If email exists for customer
            if password == customer['customer_password']:
                session['customer_email'] = email
                flash('customer login successful!', 'success')
                return redirect(url_for('customer_dashboard'))
            else:
                print("Invalid password!")  # Debugging print
                flash("Invalid password! Try Again.", 'danger')
                return redirect(url_for('login'))

        elif pharmacy_owner:  # If email exists for pharmacy owner
            if password == pharmacy_owner['pharmacy_password']:
                session['pharmacy_email'] = email
                flash('pharmacy owner login successful!', 'success')
                return redirect(url_for('pharmacy_owner_dashboard'))
            else:
                print("Invalid password!")  # Debugging print
                flash("Invalid password! Try Again.", 'danger')
                return redirect(url_for('login'))

        else:
            print("Invalid email!")  # Debugging print
            flash("Invalid Email! Try Again.", 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    conn = get_db_connection()
    pharmacy_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'pharmacy-owner'").fetchone()[0]
    customer_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'customer'").fetchone()[0]
    inquiry_count = conn.execute("SELECT COUNT(*) FROM inquiries").fetchone()[0]
    print(f"Pharmacy count: {pharmacy_count}")  # Debug statement
    conn.close()
    return render_template('admin_dashboard.html', pharmacy_count=pharmacy_count, customer_count=customer_count, inquiry_count=inquiry_count, active_page = 'home')

@app.route('/manage_pharmacies')
def manage_pharmacies():
    conn = get_db_connection()
    # Fetch all pharmacies from the database where the role is 'pharmacy-owner'
    pharmacies = conn.execute("SELECT * FROM users WHERE role = 'pharmacy-owner'").fetchall()
    conn.close()
    return render_template('manage_pharmacies.html', pharmacies=pharmacies)

@app.route('/delete_pharmacy/<int:user_id>', methods=['POST'])
def delete_pharmacy(user_id):
    conn = get_db_connection()
    # Delete the pharmacy by user_id
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_pharmacies'))

@app.route('/admin_profile')
def admin_profile():
    if 'admin_email' not in session:
        flash("Please log in to view your profile.", "warning")
        return redirect(url_for('login'))
    
    admin_email = session['admin_email']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT admin_name, admin_email, admin_mobile, admin_nic FROM admin WHERE admin_email = ?', (admin_email,))
    admin = cursor.fetchone()
    conn.close()

    print(admin)
    if admin:
        return render_template('admin_profile.html', admin=admin)
    else:
        flash('Admin details not found!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
@app.route('/delete_admin/<admin_email>', methods=['GET'])
def delete_admin(admin_email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM admin WHERE admin_email = ?', (admin_email,))
    conn.commit()
    conn.close()
    
    flash('Admin profile deleted successfully!', 'success')
    return redirect(url_for('login'))  # Redirect to login or a confirmation page
    
@app.route('/update_admin', methods=['POST'])
def update_admin():
    admin_name = request.form['admin_name']
    admin_mobile = request.form['admin_mobile']
    admin_nic = request.form['admin_nic']
    admin_email = request.form['admin_email']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE admin SET admin_name = ?, admin_mobile = ?, admin_nic = ?
        WHERE admin_email = ?
    ''', (admin_name, admin_mobile, admin_nic, admin_email))
    conn.commit()
    conn.close()

    flash('Admin profile updated successfully!', 'success')
    return redirect(url_for('admin_profile'))

@app.route('/customer_dashboard')
def customer_dashboard():
    return render_template('customer_dashboard.html',active_page='home')

@app.route('/manage_customers')
def manage_customers():
    # Get all customers from the database
    conn = get_db_connection()
    customers = conn.execute("SELECT user_id, customer_name, customer_email, customer_mobile_number FROM users WHERE role='customer'").fetchall()
    conn.close()

    return render_template('manage_customers.html', customers=customers)

@app.route('/remove_customer/<int:customer_id>', methods=['POST'])
def remove_customer(customer_id):
    # Connect to the database and remove the customer
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE user_id = ?", (customer_id,))
    conn.commit()
    conn.close()

    # Redirect back to the manage customers page after removal
    return redirect(url_for('manage_customers'))

@app.route('/inquiries', methods=['GET', 'POST'])
def inquiries():
    if request.method == 'POST':
        # Get form data
        customer_name = request.form['customer_name']
        customer_email = request.form['customer_email']
        inquiry_message = request.form['inquiry_message']

        # Save the inquiry in the database
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO inquiries (customer_name, customer_email, inquiry_message) VALUES (?, ?, ?)",
            (customer_name, customer_email, inquiry_message)
        )
        conn.commit()
        conn.close()

        # Redirect or show a success message
        return render_template('inquiry_success.html')  # Create a success page
    return render_template('inquiry_form.html', active_page = 'contact')  # Create the form page

@app.route('/inquiries_list')
def inquiries_list():
    # Fetch inquiries from the database
    conn = get_db_connection()
    inquiries = conn.execute('SELECT * FROM inquiries').fetchall()
    conn.close()

    # Pass the inquiries to the template
    return render_template('inquiries_list.html', inquiries=inquiries, active_page = 'contact')

@app.route('/customer_profile')
def customer_profile():
    if 'customer_email' not in session:
        flash("Please log in to view your profile.", "warning")
        return redirect(url_for('login'))

    customer_email = session['customer_email']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT customer_name, customer_mobile_number,  customer_email, customer_password FROM users WHERE customer_email = ?', (customer_email,))
    customer = cursor.fetchone()
    conn.close()

    if customer:
        return render_template('customer_profile.html', customer=customer)
    else:
        flash('Customer details not found!', 'danger')
        return redirect(url_for('customer_dashboard'))

@app.route('/edit_customer_profile', methods=['GET', 'POST'])
def edit_customer_profile():
    if 'customer_email' not in session:
        flash("Please log in to edit your profile.", "warning")
        return redirect(url_for('login'))

    customer_email = session['customer_email']
    
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        customer_name = request.form['customer_name']
        customer_mobile_number = request.form['customer_mobile_number']
        customer_password = request.form['customer_password']

        cursor.execute('UPDATE users SET customer_name = ?, customer_mobile_number = ?, customer_password = ? WHERE customer_email = ?',
                    (customer_name, customer_mobile_number, customer_password, customer_email))
        conn.commit()
        conn.close()

        flash("Profile updated successfully!", "success")
        return redirect(url_for('customer_profile'))

    cursor.execute('SELECT customer_name, customer_mobile_number, customer_email, customer_password FROM users WHERE customer_email = ?', (customer_email,))
    customer = cursor.fetchone()
    conn.close()

    return render_template('edit_customer_profile.html', customer=customer)

@app.route('/delete_customer_profile', methods=['POST'])
def delete_customer_profile():
    if 'customer_email' not in session:
        flash("Please log in to delete your profile.", "warning")
        return redirect(url_for('login'))

    customer_email = session['customer_email']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE customer_email = ?', (customer_email,))
    conn.commit()
    conn.close()

    flash("Profile deleted successfully!", "success")
    return redirect(url_for('customer_dashboard'))

@app.route('/upload_prescription', methods=['GET', 'POST'])
def upload_prescription():
    if request.method == 'POST':
        customer_name = request.form['customer_name']
        customer_email = request.form['customer_email']
        customer_mobile = request.form['customer_mobile']
        uploaded_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Check if the POST request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']

        # If user does not select file, browser also
        # submits an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Save the file temporarily to convert to binary
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_binary = convert_to_binary(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Insert the data into the database
            conn = get_db_connection()
            conn.execute("INSERT INTO prescriptions (customer_name, customer_email, customer_mobile, uploaded_time, image) VALUES (?, ?, ?, ?, ?)",
                        (customer_name, customer_email, customer_mobile, uploaded_time, image_binary))
            conn.commit()
            conn.close()

            # Remove the temporarily saved image after converting it to binary
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            flash('Prescription uploaded successfully!')
            return redirect(url_for('customer_dashboard'))

    return render_template('upload_prescription.html',active_page='upload-prescription')

@app.route('/view_prescription', methods=['GET'])
def view_prescription():
    # Fetch all prescriptions from the database
    conn = get_db_connection()
    prescriptions = conn.execute("SELECT * FROM prescriptions").fetchall()
    conn.close()
    
    return render_template('view_prescription.html', prescriptions=prescriptions, active_page = 'view-prescription')

@app.route('/delete_prescription/<int:id>/<string:status>', methods=['POST'])
def delete_prescription(id, status):
    # Retrieve prescription details
    conn = get_db_connection()
    prescription = conn.execute('SELECT * FROM prescriptions WHERE id = ?', (id,)).fetchone()

    if not prescription:
        flash('Prescription not found.', 'error')
        return redirect(url_for('view_prescription'))

    # Sending email to the customer based on the status
    customer_email = prescription['customer_email']
    try:
        # Email message based on availability status
        if status == 'available':
            message_body = "Your prescription is available at our pharmacy.Please visit: http://127.0.0.1:5000/pharmacy_profiles/{session.get('pharmacy_email')}"
        else:
            message_body = "Your prescription is not available at our pharmacy."
        
        msg = Message('Prescription Status', sender='your_email@gmail.com', recipients=[customer_email])
        msg.body = message_body
        mail.send(msg)

        # Delete the prescription for this pharmacy owner (but not for others)
        result = conn.execute('DELETE FROM prescriptions WHERE id = ? AND pharmacy_email = ?', (id, session['pharmacy_email']))
        conn.commit()  # This was previously outside of the try block

        if result.rowcount > 0:  # If the prescription was deleted
            flash("Email sent successfully and prescription deleted!", "success")
        else:
            flash("Prescription not found.", "error")

    except Exception as e:
        print(e)
        flash('Email sent successfully.', 'success')

    finally:
        conn.close()

    return redirect(url_for('view_prescription'))

@app.route('/order_status')
def order_status():
    # Connect to the SQLite database
    conn = sqlite3.connect('mobile_medicine.db')
    cursor = conn.cursor()

    # Fetch orders with 'Processing' or 'Pending' statuses
    cursor.execute('''
        SELECT order_id, pharmacy_email, medicine_name, brand_name, dosage, quantity, price, order_date, order_status
        FROM orders
        WHERE order_status IN ('Processing', 'Pending') OR order_status IS NULL
    ''')
    
    orders = cursor.fetchall()
    conn.close()

    # Pass orders to the template
    return render_template('order_status.html', orders=orders, active_page='order')


@app.route('/customer_order_status')
def customer_order_status():
    customer_email = session.get('customer_email')  # Assuming customer is logged in and email is stored in session
    if not customer_email:
        return redirect(url_for('login'))  # Redirect if no user is logged in
    
    conn = sqlite3.connect('mobile_medicine.db')
    cursor = conn.cursor()

    # Fetch orders with 'NULL' or 'Processing' status for the logged-in customer
    cursor.execute("""
        SELECT order_id, pharmacy_email, medicine_name, brand_name, dosage, quantity, price, order_date, order_status
        FROM orders
        WHERE customer_email = ? AND (order_status IS NULL OR order_status = 'Processing')
    """, (customer_email,))
    
    orders = cursor.fetchall()
    print("Fetched Orders with Statuses:", orders)

    # Print the order details for debugging
    for order in orders:
        print(f"Order ID: {order[0]}, Status: {order[8]}")  # Print order status

    conn.close()

    return render_template('customer_order_status.html', orders=orders)


@app.route('/pharmacy_list')
def pharmacy_list():
    conn = get_db_connection()
    # Query the users table for pharmacies based on role
    pharmacies = conn.execute(
        "SELECT pharmacy_name, pharmacy_email FROM users WHERE role = 'pharmacy-owner'"
    ).fetchall()
    conn.close()

    if pharmacies:
        return render_template('pharmacy_list.html', pharmacies=pharmacies, active_page = 'inquiries-list')
    else:
        # If no pharmacies found, render the page with a message
        return render_template('pharmacy_list.html', pharmacies=pharmacies )

@app.route('/pharmacy_profiles/<pharmacy_email>')
def pharmacy_profiles(pharmacy_email):
    # Connect to the database
    conn = sqlite3.connect('mobile_medicine.db')
    cursor = conn.cursor()
    session['pharmacy_email'] = pharmacy_email
    # Fetch pharmacy details from 'users' table
    cursor.execute("SELECT * FROM users WHERE pharmacy_email = ?", (pharmacy_email,))
    pharmacy_details = cursor.fetchone()  # Fetches the first match

    # Fetch inventory details from 'inventory' table
    cursor.execute("SELECT * FROM inventory WHERE pharmacy_email = ?", (pharmacy_email,))
    inventory_details = cursor.fetchall()  # Fetches all matching records

    # Close the connection
    conn.close()

    # Render the HTML page with both pharmacy and inventory details
    return render_template('pharmacy_profiles.html', pharmacy_details=pharmacy_details, inventory_details=inventory_details, active_page = 'pharmacy-profiles')

@app.route('/select_pharmacy/<pharmacy_email>', methods=['GET', 'POST'])
def select_pharmacy(pharmacy_email):
    # Store the selected pharmacy email in the session
    session['pharmacy_email'] = pharmacy_email
    return redirect(url_for('view_cart', pharmacy_email=session['pharmacy_email']))  # Correct
    # Redirect to the cart page or wherever you want after selection

@app.route('/add_to_cart_multiple', methods=['POST'])
def add_to_cart_multiple():
    # Get the selected medicine IDs from the form
    selected_medicines = request.form.getlist('medicines')
    
    if selected_medicines:
        # Fetch medicine details for each selected medicine
        conn = get_db_connection()
        for medicine_id in selected_medicines:
            inventory_item = conn.execute('SELECT * FROM inventory WHERE inventory_id = ?', (medicine_id,)).fetchone()
            if inventory_item:
                # Add each selected medicine to the cart
                cart = session.get('cart', [])
                cart.append({
                    'medicine_name': inventory_item['medicine_name'],
                    'brand_name': inventory_item['brand_name'],
                    'dosage': inventory_item['dosage'],
                    'quantity': 1,  # Adjust if you want to add quantity selection
                    'price': inventory_item['price'],
                })
                session['cart'] = cart
        conn.close()

    # Redirect to the View Cart page
    return redirect(url_for('view_cart'))

@app.route('/view_cart', methods=['GET', 'POST'])
def view_cart():
    cart = session.get('cart', [])
    total_price = sum(item['price'] for item in cart)
    return render_template('view_cart.html', cart=cart, total_price=total_price)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    medicine = {
        'medicine_name': request.form['medicine_name'],
        'brand_name': request.form['brand_name'],
        'dosage': request.form['dosage'],
        'quantity': int(request.form['quantity']),
        'price': float(request.form['price'])
    }
    session['cart'].append(medicine)
    session.modified = True
    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<medicine_name>', methods=['POST'])
def remove_from_cart(medicine_name):
    cart = session.get('cart', [])
    session['cart'] = [item for item in cart if item['medicine_name'] != medicine_name]
    session.modified = True
    return redirect(url_for('view_cart'))

@app.route('/upload_payment', methods=['GET', 'POST'])
def upload_payment():
    if request.method == 'POST':
        # Check if the user is logged in
        if 'customer_email' not in session:
            flash("You need to log in to proceed with the payment.")
            return redirect(url_for('login'))

        # Ensure the pharmacy_email exists in the session
        pharmacy_email = session.get('pharmacy_email')
        if not pharmacy_email:
            flash("Pharmacy email is missing. Please select a pharmacy.")
            return redirect(url_for('select_pharmacy'))

        # Extract form data
        customer_email = session['customer_email']
        
        # Handle payment slip upload
        payment_slip = request.files.get('payment_slip')
        
        if payment_slip:
            # Convert payment slip to binary
            payment_slip_binary = payment_slip.read()

            # Connect to the database and store the payment slip in binary format
            conn = sqlite3.connect('mobile_medicine.db')
            cursor = conn.cursor()

            # Update orders table with the payment slip in binary
            cursor.execute("""
                UPDATE orders
                SET payment_slip = ?
                WHERE customer_email = ? AND pharmacy_email = ?
            """, (payment_slip_binary, customer_email, pharmacy_email))

            conn.commit()
            conn.close()

            # Clear the cart in the session
            session.pop('cart', None)  # Remove 'cart' from session to clear the cart

            # Flash success message
            flash("Payment successful! Your order is being processed.")

            return redirect(url_for('order_confirmation'))  # Redirect to order confirmation page

        else:
            flash("Please upload a valid payment slip")
            
            session['_flashes'] = [] 

    return render_template('upload_payment.html')


@app.route('/order_confirmation')
def order_confirmation():
    # Logic for confirming the order and showing the confirmation page
    return render_template('order_confirmation.html')  # Adjust the template name as necessary
        
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/submit_contact', methods=['POST'])
def submit_contact():
    customer_name = request.form['customer_name']
    customer_email = request.form['customer_email']
    message = request.form['message']
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO customer_inquiries (customer_name, customer_email, message) VALUES (?, ?, ?)',
        (customer_name, customer_email, message)
    )
    conn.commit()
    conn.close()

    flash('Thank you for your message! We will get back to you soon.', 'success')
    return redirect(url_for('contact'))

@app.route('/admin/inquiries')
def admin_inquiries():
    conn = sqlite3.connect('mobile_medicine.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customer_inquiries WHERE status = 'Pending'")
    inquiries = cursor.fetchall()
    conn.close()
    return render_template('admin_inquiries.html', inquiries=inquiries)

@app.route('/admin/reply/<int:inquiry_id>', methods=['POST'])
def admin_reply(inquiry_id):
    response = request.form['response']
    conn = sqlite3.connect('mobile_medicine.db')
    cursor = conn.cursor()
    # Update response and mark inquiry as 'Done'
    cursor.execute("""
        UPDATE customer_inquiries 
        SET response = ?, status = 'Done' 
        WHERE id = ?
    """, (response, inquiry_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_inquiries'))

@app.route('/notifications', methods=['GET'])
def notifications():
    
    customer_email = session.get('customer_email')  # Assuming email is stored in session after login
    if not customer_email:
        return redirect(url_for('login'))  # Redirect to login if not authenticated
    conn = sqlite3.connect('mobile_medicine.db')
    cursor = conn.cursor()
    # Fetch all completed inquiries for the customer
    cursor.execute("""
        SELECT * FROM customer_inquiries 
        WHERE customer_email = ? AND status = 'Done'
    """, (customer_email,))
    notifications = cursor.fetchall()
    conn.close()
    return render_template('notifications.html', notifications=notifications)

@app.route('/customer_order_history')
def customer_order_history():
    # Get the customer email from session (assuming the customer is logged in)
    customer_email = session.get('customer_email')  # Adjust according to your session logic
    
    # Redirect to login if the customer is not logged in
    if not customer_email:
        return redirect(url_for('login'))

    # Connect to the database
    conn = sqlite3.connect('mobile_medicine.db')
    cursor = conn.cursor()

    # Print the customer email to debug
    print(f"Customer Email: {customer_email}")  # Debugging: Print customer email

    # Query to get completed orders for the logged-in customer
    cursor.execute("""
        SELECT order_id, pharmacy_email, medicine_name, brand_name, dosage, quantity, price, order_date
        FROM orders
        WHERE customer_email = ? AND order_status = 'Completed'
    """, (customer_email,))

    # Fetch all the orders
    orders = cursor.fetchall()
    
    # Debugging: Print fetched orders to see what is returned
    print(f"Fetched Orders: {orders}")  # Debugging: Print orders fetched

    # If there are no orders found, print a message
    if not orders:
        print("No completed orders found for this customer.")  # Debugging: Print message if no orders are found

    # Close the database connection
    conn.close()

    # Return the template with the fetched orders
    return render_template('customer_order_history.html', orders=orders, active_page = 'order-history')


@app.route('/pharmacy_owner_dashboard')
def pharmacy_owner_dashboard():
    return render_template('pharmacy_owner_dashboard.html',active_page='home')

@app.route('/pharmacy_about')
def pharmacy_about():
    return render_template('pharmacy_about.html')

@app.route('/pharmacy_inquaries')
def pharmacy_inquaries():
    return render_template('pharmacy_inquaries.html')

@app.route('/order_details', methods=['GET'])
def order_details():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_id, customer_email, medicine_name, brand_name, dosage, quantity, price, order_date, order_status
        FROM orders;
    """)
    orders = cursor.fetchall()
    conn.close()
    return render_template('order_details.html', orders=orders, active_page='order-history')

# Route to update order status
@app.route('/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    new_status = request.form['order_status']

    # Update the order status in the database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE orders
        SET order_status = ?
        WHERE order_id = ?;
    """, (new_status, order_id))
    conn.commit()
    conn.close()

    # Redirect back to the orders page
    return redirect(url_for('update_order', order_id=order_id))


@app.route('/pharmacy_profile')
def pharmacy_profile():
    if 'pharmacy_email' not in session:
        flash("Please log in to view your profile.", "warning")
        return redirect(url_for('login'))

    pharmacy_email = session['pharmacy_email']
    print("Pharmacy Email in session:", pharmacy_email)  # Debugging print

    # Fetch pharmacy details
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT pharmacy_name, pharmacy_owner_name, pharmacy_email, pharmacy_mobile_number, license_number, pharmacy_location_latitude,pharmacy_location_longitude FROM users WHERE pharmacy_email = ?''', (pharmacy_email,))
    pharmacy = cursor.fetchone()
    conn.close()

    if pharmacy:
        return render_template('pharmacy_profile.html', pharmacy=pharmacy)
    else:
        flash("Pharmacy details not found.", "danger")
        return redirect(url_for('pharmacy_owner_dashboard'))

@app.route('/edit_pharmacy_profile', methods=['GET', 'POST'])
def edit_pharmacy_profile():
    if 'pharmacy_email' not in session:
        flash("Please log in to edit your profile.", "warning")
        return redirect(url_for('login'))

    pharmacy_email = session['pharmacy_email']
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Retrieving updated values from the form
        new_name = request.form['pharmacy_name']
        new_owner_name = request.form['pharmacy_owner_name']
        new_mobile = request.form['pharmacy_mobile_number']
        new_license = request.form['license_number']
        
        # Updating the database
        cursor.execute('''UPDATE users SET pharmacy_name = ?, pharmacy_owner_name = ?, 
                        pharmacy_mobile_number = ?, license_number = ? WHERE pharmacy_email = ?''', 
                    (new_name, new_owner_name, new_mobile, new_license, pharmacy_email))
        conn.commit()
        conn.close()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('pharmacy_profile'))  # Redirect to the profile page after updating

    # Fetching current data for the edit form
    cursor.execute('''SELECT pharmacy_name, pharmacy_owner_name, pharmacy_mobile_number, license_number 
                    FROM users WHERE pharmacy_email = ?''', (pharmacy_email,))
    pharmacy = cursor.fetchone()
    conn.close()

    return render_template('edit_pharmacy_profile.html', pharmacy=pharmacy)


@app.route('/delete_pharmacy_profile', methods=['POST'])
def delete_pharmacy_profile():
    if 'pharmacy_email' not in session:
        flash("Please log in to delete your profile.", "warning")
        return redirect(url_for('login'))

    pharmacy_email = session['pharmacy_email']
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM users WHERE pharmacy_email = ?', (pharmacy_email,))
    conn.commit()
    conn.close()

    flash('Pharmacy profile deleted successfully!', 'success')
    return redirect(url_for('login'))


@app.route('/add_medicine', methods=['GET', 'POST'])
def add_medicine():
    if 'pharmacy_email' not in session:
        flash("Please log in to add medicines.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Retrieve all form data
        medicine_name = request.form['medicine_name']
        brand_name = request.form['brand_name']
        category = request.form['category']
        form = request.form['form']
        dosage = request.form['dosage']
        quantity = request.form['quantity']
        price = request.form['price']
        availability = request.form['availability']
        pharmacy_email = session['pharmacy_email']

        try:
            # Open connection
            conn = get_db_connection()
            cursor = conn.cursor()

            # Start a transaction
            cursor.execute('BEGIN TRANSACTION')

            # Insert into inventory
            cursor.execute('''
                INSERT INTO inventory 
                (pharmacy_email, medicine_name, brand_name, category, form, dosage, quantity, price, availability) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (pharmacy_email, medicine_name, brand_name, category, form, dosage, quantity, price, availability))

            # Commit the transaction
            conn.commit()
            flash("Medicine added successfully!", "success")
        except sqlite3.OperationalError as e:
            flash(f"Database error: {str(e)}", "danger")
            conn.rollback()  # Rollback if there's an error
        finally:
            conn.close()  # Always close the connection

        return redirect(url_for('view_inventory'))

    return render_template('add_medicine.html')


@app.route('/view_inventory')
def view_inventory():
    if 'pharmacy_email' not in session:
        flash("Please log in to view your inventory.", "warning")
        return redirect(url_for('login'))

    pharmacy_email = session['pharmacy_email']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventory WHERE pharmacy_email = ?', (pharmacy_email,))
    medicines = cursor.fetchall()
    conn.close()

    return render_template('view_inventory.html', medicines=medicines, active_page = 'view-inventory')


@app.route('/edit_medicine/<int:inventory_id>', methods=['GET', 'POST'])
def edit_medicine(inventory_id):
    if 'pharmacy_email' not in session:
        flash("Please log in to edit medicines.", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Collect form data
        medicine_name = request.form['medicine_name']
        brand_name = request.form['brand_name']
        category = request.form['category']
        form = request.form['form']
        dosage = request.form['dosage']
        quantity = request.form['quantity']
        price = request.form['price']
        availability = request.form['availability']

        # Update the database
        cursor.execute('''
            UPDATE inventory 
            SET 
                medicine_name = ?, 
                brand_name = ?, 
                category = ?, 
                form = ?, 
                dosage = ?, 
                quantity = ?, 
                price = ?, 
                availability = ? 
            WHERE inventory_id = ?''', 
            (medicine_name, brand_name, category, form, dosage, quantity, price, availability, inventory_id))
        conn.commit()
        conn.close()
        flash("Medicine updated successfully!", "success")
        return redirect(url_for('view_inventory'))

    # Fetch medicine details for the given ID
    cursor.execute('SELECT * FROM inventory WHERE inventory_id = ?', (inventory_id,))
    medicine = cursor.fetchone()
    conn.close()

    return render_template('edit_medicine.html', medicine=medicine)


@app.route('/delete_medicine/<int:inventory_id>', methods=['POST'])
def delete_medicine(inventory_id):
    if 'pharmacy_email' not in session:
        flash("Please log in to delete medicines.", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM inventory WHERE inventory_id = ?', (inventory_id,))
    conn.commit()
    conn.close()
    flash("Medicine deleted successfully!", "success")
    return redirect(url_for('view_inventory'))


@app.route('/pharmacy_order_history')
def pharmacy_order_history():
    conn = sqlite3.connect('mobile_medicine.db')
    cursor = conn.cursor()

    # Query to get completed orders
    cursor.execute("""
        SELECT order_id, customer_email, medicine_name, brand_name, dosage, quantity, price, order_date
        FROM orders
        WHERE order_status = 'Completed'
    """)

    orders = cursor.fetchall()
    print("Completed :", order_status)  # Debugging print to see what is returned
    print(f"Number of Orders Found: {len(orders)}")  # Print the number of orders found
    conn.close()
    return render_template('pharmacy_order_history.html', orders=orders, active_page = 'pharmacy-order-history')




@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if email exists in users or admin table
        cursor.execute('''
            SELECT * FROM users WHERE customer_email = ? OR pharmacy_email = ?
        ''', (email, email))
        user = cursor.fetchone()

        if not user:
            cursor.execute('SELECT * FROM admin WHERE admin_email = ?', (email,))
            admin = cursor.fetchone()

        conn.close()

        if admin:
            token = s.dumps(email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            send_reset_email(email, reset_url)
            flash('A password reset link has been sent to your email.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email not found. Please try again.', 'danger')
            return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)  # 1-hour expiration
    except Exception:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password == confirm_password:
        
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM admin WHERE admin_email = ?', (email,))
            admin = cursor.fetchone()
            if admin:
                cursor.execute('''
                    UPDATE admin
                    SET admin_password = ?
                    WHERE admin_email = ?
                ''', (password, email))
            else:
            # Check if email exists in customer table
                cursor.execute('SELECT * FROM customers WHERE customer_email = ?', (email,))
                customer = cursor.fetchone()
                if customer:
                    cursor.execute('''
                        UPDATE customers
                        SET customer_password = ?
                        WHERE customer_email = ?
                    ''', (password, email))
                else:
                    # Check if email exists in pharmacy owner table
                    cursor.execute('SELECT * FROM pharmacy_owners WHERE pharmacy_email = ?', (email,))
                    pharmacy_owner = cursor.fetchone()
                    if pharmacy_owner:
                        cursor.execute('''
                            UPDATE pharmacy_owners
                            SET pharmacy_password = ?
                            WHERE pharmacy_email = ?
                        ''', (password, email))
                    else:
                        flash('No account associated with this email address.', 'danger')
                        conn.close()
                        return redirect(url_for('forgot_password'))

            conn.commit()
            conn.close()

            flash('Your password has been reset!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Passwords do not match', 'danger')

    return render_template('reset_password.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", 'success')
    return redirect(url_for('login'))



if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)