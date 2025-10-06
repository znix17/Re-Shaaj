from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import bcrypt
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'


app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  #add password (test hash for manually populating user table with passwords)
app.config['MYSQL_DB'] = 'ReShaaj'

#image uploads
UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mysql = MySQL(app)

#image folder
if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER)
        print(f"Created upload folder: {UPLOAD_FOLDER}")
    except Exception as e:
        print(f"Failed to create upload folder: {str(e)}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    print("Accessing index route")
    if 'user_name' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/test_db')
def test_db():
    print("Accessing test_db route")
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT 1")
        cur.close()
        print("Database connection successful")
        return "Database connection successful"
    except Exception as e:
        print(f"Test DB error: {str(e)}")
        return f"Database error: {str(e)}"

@app.route('/debug_seller')
def debug_seller():
    print("Accessing debug_seller route")
    if 'user_name' not in session:
        return "Please log in to check seller status"
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            cur.close()
            return "User not found in USER table"
        user_id = user[0]
        cur.execute("SELECT 1 FROM Seller WHERE user_id = %s", (user_id,))
        is_seller = cur.fetchone() is not None
        cur.close()
        return f"User: {session['user_name']}, User ID: {user_id}, Is Seller: {is_seller}"
    except Exception as e:
        return f"Error checking seller status: {str(e)}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("Accessing login route")
    try:
        if request.method == 'POST':
            user_name = request.form['user_name']
            password = request.form['password'].encode('utf-8')
            print(f"Login attempt: {user_name}")
            cur = mysql.connection.cursor()
            cur.execute("SELECT password_hash FROM USER WHERE user_name = %s", (user_name,))
            user = cur.fetchone()
            cur.close()
            if user and bcrypt.checkpw(password, user[0].encode('utf-8')):
                session['user_name'] = user_name
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Invalid username or password', 'error')
        return render_template('login.html')
    except Exception as e:
        print(f"Error in login route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return render_template('login.html')

@app.route('/logout', methods=['GET'])
def logout():
    print("Accessing logout route")
    session.pop('user_name', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    print("Accessing signup route")
    try:
        if request.method == 'POST':
            user_name = request.form['user_name']
            email = request.form['email']
            phone = request.form['phone']
            password = request.form['password'].encode('utf-8')
            hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
            print(f"Signup attempt: {user_name}, {email}, {phone}")
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO USER (user_name, email, phone, password_hash, join_date) 
                VALUES (%s, %s, %s, %s, NOW())
            """, (user_name, email, phone, hashed_password))
            mysql.connection.commit()
            cur.execute("INSERT INTO Buyer (user_id) SELECT user_id FROM USER WHERE user_name = %s", (user_name,))
            mysql.connection.commit()
            cur.close()
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        return render_template('signup.html')
    except Exception as e:
        print(f"Error in signup route: {str(e)}")
        flash(f"Signup failed: {str(e)}", 'error')
        return render_template('signup.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    print("Accessing home route")
    try:
        if 'user_name' not in session:
            flash('Please log in to view the homepage', 'error')
            return redirect(url_for('login'))
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        user_id = user[0] if user else None
        
        if request.method == 'POST':
            search_query = request.form.get('search', '')
            print(f"Search query: {search_query}")
            cur.execute("""
                SELECT p.P_ID, p.title, p.price, p.category, p.`condition`, COALESCE(u.user_name, 'N/A'), p.seller_id, p.sold, p.image_path
                FROM Product p 
                LEFT JOIN USER u ON p.seller_id = u.user_id 
                WHERE p.title LIKE %s OR p.category LIKE %s OR u.user_name LIKE %s
            """, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
        else:
            cur.execute("""
                SELECT p.P_ID, p.title, p.price, p.category, p.`condition`, COALESCE(u.user_name, 'N/A'), p.seller_id, p.sold, p.image_path
                FROM Product p 
                LEFT JOIN USER u ON p.seller_id = u.user_id
            """)
        products = cur.fetchall()
        cur.close()
        return render_template('home.html', products=products, user_id=user_id, user_name=session['user_name'])
    except Exception as e:
        print(f"Error in home route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('login'))

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    print(f"Accessing add_to_cart route for product_id: {product_id}")
    try:
        if 'user_name' not in session:
            flash('Please log in to add to cart', 'error')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('home'))
        user_id = user[0]

        #avoid adding my own listings to the cart
        cur.execute("SELECT seller_id, sold, cart_id FROM Product WHERE P_ID = %s", (product_id,))
        product = cur.fetchone()
        if not product or product[1] or product[2] is not None or product[0] == user_id:
            flash('Product not available', 'error')
            return redirect(url_for('home'))

        # cart
        cur.execute("SELECT cart_id FROM Cart WHERE buyer_id = %s AND confirm_order_id IS NULL", (user_id,))
        cart = cur.fetchone()
        if not cart:
            cur.execute("INSERT INTO Cart (buyer_id) VALUES (%s)", (user_id,))
            mysql.connection.commit()
            cart_id = cur.lastrowid
        else:
            cart_id = cart[0]

        # Add to cart
        cur.execute("UPDATE Product SET cart_id = %s WHERE P_ID = %s", (cart_id, product_id))
        mysql.connection.commit()
        cur.close()
        flash('Product added to cart!', 'success')
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Error in add_to_cart route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('home'))

@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    print(f"Accessing remove_from_cart route for product_id: {product_id}")
    try:
        if 'user_name' not in session:
            flash('Please log in to remove from cart', 'error')
            return redirect(url_for('dashboard'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('dashboard'))

        user_id = user[0]
        
        cur.execute("SELECT cart_id FROM Cart WHERE buyer_id = %s AND confirm_order_id IS NULL", (user_id,))
        cart = cur.fetchone()
        if not cart:
            flash('No active cart found', 'error')
            return redirect(url_for('dashboard'))
        
        cart_id = cart[0]
        
        cur.execute("SELECT cart_id FROM Product WHERE P_ID = %s AND cart_id = %s", (product_id, cart_id))
        product = cur.fetchone()
        if not product:
            flash('Product not found in your cart', 'error')
            return redirect(url_for('dashboard'))
        
        cur.execute("UPDATE Product SET cart_id = NULL WHERE P_ID = %s", (product_id,))
        mysql.connection.commit()
        cur.close()
        flash('Product removed from cart!', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Error in remove_from_cart route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('dashboard'))

@app.route('/confirm_order/<int:cart_id>', methods=['POST'])
def confirm_order(cart_id):
    print(f"Accessing confirm_order route for cart_id: {cart_id}")
    try:
        if 'user_name' not in session:
            flash('Please log in to confirm order', 'error')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('home'))
        user_id = user[0]
        
        cur.execute("SELECT buyer_id FROM Cart WHERE cart_id = %s AND confirm_order_id IS NULL", (cart_id,))
        cart = cur.fetchone()
        if not cart or cart[0] != user_id:
            flash('Invalid cart or unauthorized access', 'error')
            return redirect(url_for('dashboard'))
        
        cur.execute("""
            SELECT p.P_ID, p.seller_id, price
            FROM Product p 
            WHERE p.cart_id = %s AND sold = False
        """, (cart_id,))
        products = cur.fetchall()
        if not products:
            flash('No products in cart to confirm', 'error')
            return redirect(url_for('dashboard'))
        
        for product in products:
            P_ID = product[0]
            seller_id = product[1]
            cur.execute("""
                INSERT INTO `Order` (buyer_id, seller_id, P_id, status)
                VALUES (%s, %s, %s, 'Confirmed')
            """, (user_id, seller_id, P_ID))
            cur.execute("UPDATE Product SET cart_id = NULL, sold = TRUE WHERE P_ID = %s", (P_ID,))
        
        cur.execute("UPDATE Cart SET confirm_order_id = (SELECT LAST_INSERT_ID()) WHERE cart_id = %s", (cart_id,))
        mysql.connection.commit()
        cur.close()
        flash('Order confirmed successfully!', 'success')
        return redirect(url_for('orders'))
    except Exception as e:
        print(f"Error in confirm_order route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('dashboard'))

@app.route('/cart')
def cart():
    print("Accessing cart route")
    try:
        if 'user_name' not in session:
            flash('Please log in to view cart', 'error')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('home'))
        user_id = user[0]

        cur.execute("SELECT cart_id FROM Cart WHERE buyer_id = %s AND confirm_order_id IS NULL", (user_id,))
        cart = cur.fetchone()
        cart_id = cart[0] if cart else None

        cart_products = []
        total_price = 0.0
        if cart_id:
            cur.execute("""
                SELECT p.P_ID, p.title, p.price, p.category, p.`condition`, COALESCE(u.user_name, 'N/A'), p.image_path 
                FROM Product p 
                LEFT JOIN USER u ON p.seller_id = u.user_id 
                WHERE p.cart_id = %s
            """, (cart_id,))
            cart_products = cur.fetchall()
            total_price = sum(product[2] for product in cart_products)

        cur.close()
        return render_template('cart.html', cart_products=cart_products, cart_id=cart_id, total_price=total_price)
    except Exception as e:
        print(f"Error in cart route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('home'))

@app.route('/orders', methods=['GET'])
def orders():
    print("Accessing orders route")
    try:
        if 'user_name' not in session:
            flash('Please log in to view orders', 'error')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('home'))
        user_id = user[0]

        #fetch orders
        cur.execute("""
            SELECT o.order_id, p.title, o.price, u.user_name, o.status
            FROM `Order` o
            JOIN Product p ON o.product_id = p.P_ID
            JOIN USER u ON o.seller_id = u.user_id
            WHERE o.buyer_id = %s
            ORDER BY o.order_id DESC
        """, (user_id,))
        orders = cur.fetchall()

        #total_price = sum(order[2] for order in orders)  (not implemented)

        cur.close()
        return render_template('orders.html', orders=orders, total_price=total_price)
    except Exception as e:
        print(f"Error in orders route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    print("Accessing dashboard route")
    try:
        if 'user_name' not in session:
            flash('Please log in to view the dashboard', 'error')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id, email, user_name, phone, profile_picture, bio FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('home'))
        
        user_id = user[0]
        
        cur.execute("SELECT 1 FROM Seller WHERE user_id = %s", (user_id,))
        is_seller = cur.fetchone() is not None
        
        listed_products = []
        ratings = 0.0
        reviewer_name = 'N/A'
        if is_seller:
            cur.execute("SELECT P_ID, title, price, category, `condition`, image_path FROM Product WHERE seller_id = %s AND sold = FALSE", (user_id,))
            listed_products = cur.fetchall()
            cur.execute("SELECT COALESCE(AVG(rating), 0), COALESCE((SELECT user_name FROM USER WHERE user_id = (SELECT buyer_id FROM reviews WHERE seller_id = %s LIMIT 1)), 'N/A') FROM reviews WHERE seller_id = %s", (user_id, user_id))
            rating_data = cur.fetchone()
            ratings = rating_data[0]
            reviewer_name = rating_data[1]
        cur.execute("""
            SELECT o.order_id, p.title, p.price, u.user_name, o.status, o.seller_id,
                   (SELECT COUNT(*) FROM reviews r WHERE r.seller_id = o.seller_id AND r.buyer_id = %s) AS has_reviewed
            FROM `Order` o
            JOIN Product p ON o.P_id = p.P_id
            JOIN USER u ON o.seller_id = u.user_id
            WHERE o.buyer_id = %s
            ORDER BY o.order_id DESC
        """, (user_id, user_id))
        orders = cur.fetchall()
        cur.close()
        return render_template('dashboard.html', user=user, is_seller=is_seller, listed_products=listed_products, ratings=ratings, reviewer_name=reviewer_name, orders=orders)
    except Exception as e:
        print(f"Error in dashboard route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('home'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    print("Accessing update_profile route")
    try:
        if 'user_name' not in session:
            flash('Please log in to update your profile', 'error')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('dashboard'))
        user_id = user[0]

        phone = request.form.get('phone')
        bio = request.form.get('bio')
        profile_picture = request.files.get('profile_picture')

        #initializing update queries and parameters
        update_fields = []
        update_values = []

        if phone:
            update_fields.append("phone = %s")
            update_values.append(phone)
        if bio:
            update_fields.append("bio = %s")
            update_values.append(bio)
        if profile_picture and allowed_file(profile_picture.filename):
            filename = secure_filename(profile_picture.filename)
            profile_picture.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            update_fields.append("profile_picture = %s")
            update_values.append(filename)

        if update_fields:
            update_query = f"UPDATE USER SET {', '.join(update_fields)} WHERE user_id = %s"
            update_values.append(user_id)
            cur.execute(update_query, update_values)
            mysql.connection.commit()
            flash('Profile updated successfully!', 'success')
        else:
            flash('No changes provided', 'error')

        cur.close()
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Error in update_profile route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('dashboard'))

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    print("Accessing add_product route")
    try:
        if 'user_name' not in session:
            flash('Please log in to add a product', 'error')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('dashboard'))
        user_id = user[0]

        # debug seller statur and add product feature
        cur.execute("SELECT 1 FROM Seller WHERE user_id = %s", (user_id,))
        is_seller = cur.fetchone() is not None
        if not is_seller:
            flash('You must be a seller to add products', 'error')
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            title = request.form.get('title')
            price = request.form.get('price')
            category = request.form.get('category')
            condition = request.form.get('condition')
            image = request.files.get('image')

            if not title or not price or not category or not condition:
                flash('All fields are required', 'error')
                return render_template('add_product.html')

            try:
                price = float(price)
                if price <= 0:
                    raise ValueError("invalid price")
            except ValueError:
                flash('Invalid price', 'error')
                return render_template('add_product.html')

            image_path = None
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = filename

            cur.execute("""
                INSERT INTO Product (title, price, category, `condition`, seller_id, sold, image_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (title, price, category, condition, user_id, False, image_path))
            mysql.connection.commit()
            cur.close()
            flash('Product added successfully!', 'success')
            return redirect(url_for('dashboard'))

        cur.close()
        return render_template('add_product.html')
    except Exception as e:
        print(f"Error in add_product route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('dashboard'))

@app.route('/become_seller', methods=['POST'])
def become_seller():
    print("Accessing become_seller route")
    try:
        if 'user_name' not in session:
            flash('Please log in to become a seller', 'error')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('dashboard'))
        user_id = user[0]

        #debug
        cur.execute("SELECT 1 FROM Seller WHERE user_id = %s", (user_id,))
        if cur.fetchone():
            flash('You are already a seller', 'error')
            return redirect(url_for('dashboard'))

        #populate seller table in db
        cur.execute("INSERT INTO Seller (user_id) VALUES (%s)", (user_id,))
        mysql.connection.commit()
        cur.close()
        flash('You are now a seller!', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Error in become_seller route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('dashboard'))

@app.route('/submit_review/<int:order_id>', methods=['POST'])
def submit_review(order_id):
    print(f"Accessing submit_review route for order_id: {order_id}")
    try:
        if 'user_name' not in session:
            flash('Please log in to submit a review', 'error')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id FROM USER WHERE user_name = %s", (session['user_name'],))
        user = cur.fetchone()
        if not user:
            flash('User not found', 'error')
            cur.close()
            return redirect(url_for('orders'))
        user_id = user[0]
        print(f"User ID: {user_id}")

        cur.execute("""
            SELECT seller_id, buyer_id, status 
            FROM `Order`
            WHERE order_id = %s
        """, (order_id,))
        order = cur.fetchone()
        print(f"Order query result: {order}")
        if not order:
            flash('Order not found', 'error')
            cur.close()
            return redirect(url_for('orders'))
        if not isinstance(order, tuple):
            print(f"Order is not a tuple: {order}")
            flash('Invalid order data format', 'error')
            cur.close()
            return redirect(url_for('orders'))
        if order[1] != user_id or order[2] != 'Confirmed':
            flash('Invalid order or unauthorized access', 'error')
            cur.close()
            return redirect(url_for('orders'))

        seller_id = order[0]
        print(f"Seller ID: {seller_id}")

        cur.execute("""
            SELECT COUNT(*) FROM reviews 
            WHERE seller_id = %s AND buyer_id = %s
        """, (seller_id, user_id))
        existing_review_count = cur.fetchone()[0]
        print(f"Existing review count: {existing_review_count}")
        if existing_review_count > 0:
            flash('You have already reviewed this seller for an order', 'error')
            cur.close()
            return redirect(url_for('orders'))

        rating = request.form.get('rating')
        review_text = request.form.get('review_text', '').strip()
        print(f"Form data: rating={rating}, review_text={review_text}")

        try:
            rating = float(rating)
            if not (0 <= rating <= 5):
                raise ValueError("Rating must be between 0 and 5")
        except (ValueError, TypeError) as e:
            print(f"Rating validation error: {str(e)}")
            flash('Invalid rating. Please provide a number between 0 and 5.', 'error')
            cur.close()
            return redirect(url_for('orders'))

        cur.execute("""
            INSERT INTO reviews (seller_id, buyer_id, rating, review_text, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (seller_id, user_id, rating, review_text if review_text else None))
        mysql.connection.commit()
        print(f"Inserted review: seller_id={seller_id}, buyer_id={user_id}, rating={rating}, review_text={review_text}")
        
        cur.close()
        flash('Review submitted successfully!', 'success')
        return redirect(url_for('orders'))
    except Exception as e:
        print(f"Error in submit_review route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        cur.close()
        return redirect(url_for('orders'))
    
    
@app.route('/profile/<username>', methods=['GET'])
def profile(username):
    print(f"Accessing profile route for username: {username}")
    if 'user_name' not in session:
        flash('Please log in to view profiles', 'error')
        return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id, user_name, join_date, profile_picture, bio FROM USER WHERE user_name = %s", (username,))
        target_user = cur.fetchone()
        if not target_user:
            flash('User not found', 'error')
            return redirect(url_for('home'))
        
        user_id, user_name, join_date, profile_picture, bio = target_user
        
        cur.execute("SELECT 1 FROM Seller WHERE user_id = %s", (user_id,))
        is_seller = cur.fetchone() is not None
        
        listing_count = 0
        average_rating = 0
        reviews = []
        products = []
        if is_seller:
            cur.execute("SELECT COUNT(*) FROM Product WHERE seller_id = %s AND sold = FALSE", (user_id,))
            listing_count = cur.fetchone()[0]
            
            cur.execute("""
                SELECT COALESCE(AVG(r.rating), 0)
                FROM reviews r
                WHERE r.seller_id = %s
            """, (user_id,))
            average_rating = cur.fetchone()[0]
            
            cur.execute("""
                SELECT u.user_name, r.rating, COALESCE(r.review_text, '')
                FROM reviews r
                LEFT JOIN USER u ON r.buyer_id = u.user_id
                WHERE r.seller_id = %s
                ORDER BY r.rating DESC
            """, (user_id,))
            reviews = cur.fetchall()
            
            cur.execute("SELECT P_ID, title, price, category, `condition`, image_path FROM Product WHERE seller_id = %s AND sold = FALSE", (user_id,))
            products = cur.fetchall()
        
        cur.close()
        return render_template('profile.html', user_name=user_name, join_date=join_date, 
                             profile_picture=profile_picture, bio=bio,
                             is_seller=is_seller, listing_count=listing_count, 
                             average_rating=average_rating, reviews=reviews, products=products)
    except Exception as e:
        print(f"Error in profile route: {str(e)}")
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
