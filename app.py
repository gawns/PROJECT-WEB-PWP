from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from flask import send_from_directory
from functools import wraps
import random
from datetime import datetime, timedelta
import math
import hashlib
import json  
import qrcode
import io
import base64
from datetime import datetime


app = Flask(__name__)
app.secret_key = 'kunci_rahasia_dapur_thury_2025'

# ==================== DATABASE CONNECTION ====================
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',  # Sesuaikan password MySQL
            database='db_pizza_thury',
            autocommit=False
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        return None

# ==================== DECORATORS ====================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash("⚠️ Akses ditolak! Hanya untuk Admin.", "error")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("🔐 Silakan login terlebih dahulu.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== HELPER FUNCTIONS ====================
def calculate_distance(lat1, lon1, lat2, lon2):
    """Hitung jarak antara dua koordinat dalam km"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def generate_order_code():
    return f"lch-pz-thry-{random.randint(1000, 9999)}"

def get_nearest_restaurant(user_lat, user_lon):
    conn = get_db_connection()
    if not conn:
        return None, None
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM restaurants")
        restaurants = cursor.fetchall()
        
        if not restaurants:
            return None, None
        
        nearest = None
        min_distance = float('inf')
        
        for restaurant in restaurants:
            distance = calculate_distance(
                user_lat, user_lon,
                float(restaurant['latitude']), 
                float(restaurant['longitude'])
            )
            
            if distance < min_distance:
                min_distance = distance
                nearest = restaurant
        
        return nearest, min_distance
    except Exception as e:
        print(f"Error finding restaurant: {e}")
        return None, None
    finally:
        cursor.close()
        conn.close()

def estimate_delivery_time(distance_km):
    travel_time_minutes = (distance_km / 30) * 60
    return int(travel_time_minutes) + 5

# Pastikan fungsi ini yang aktif di bagian HELPER
def generate_qr_data(order_code, amount):
    qr_payload = {
        "merchant": "Pizza Lecker Thury",
        "order_code": order_code,
        "amount": float(amount),
        "status": "UNPAID"
    }
    return json.dumps(qr_payload)

# ==================== ROUTES - PUBLIC ====================
@app.route('/')
def home():
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('index.html', pizzas=[])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM menus WHERE active = 1 ORDER BY id DESC LIMIT 6")
        pizzas = cursor.fetchall()
    except Exception as e:
        print(f"Error: {e}")
        pizzas = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('index.html', pizzas=pizzas)
# Tambahkan context processor untuk menyediakan fungsi now ke semua template
@app.context_processor
def inject_now():
    return {'now': datetime.now}


# Tambahkan fungsi ini di bagian HELPER FUNCTIONS
def generate_qr_code(order_code, amount, timestamp):
    """Generate QR code image based on static order data"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    # Gunakan data statis dari database agar QR tidak berubah-ubah
    qr_data = f"""
=== PIZZA LECKER THURY ===
Order: {order_code}
Total: Rp {amount:,.0f}
Date: {timestamp}
Status: OFFICIAL PAYMENT
==========================
    """.strip()
    
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode()


# Update fungsi generate_qr_data untuk konsistensi
def generate_qr_data(order_code, amount):
    """Generate QR payment data"""
    qr_data = {
        "merchant": "Pizza Lecker Thury",
        "order_code": order_code,
        "amount": amount,
        "currency": "IDR",
        "timestamp": datetime.now().isoformat(),
        "payment_method": "QRIS",
        "checksum": hashlib.md5(f"{order_code}{amount}{datetime.now().timestamp()}".encode()).hexdigest()[:8]
    }
    return json.dumps(qr_data)

# Tambahkan route untuk QR code
@app.route('/order/qr/<order_code>')
@login_required
def get_qr_code(order_code):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Ambil total_harga dan tanggal pesanan
        cursor.execute("SELECT total_harga, tanggal FROM orders WHERE kode_pesanan = %s LIMIT 1", (order_code,))
        order = cursor.fetchone()
        
        if not order:
            return jsonify({"error": "Order not found"}), 404
        
        # Kirim tanggal dari database ke fungsi QR
        formatted_date = order['tanggal'].strftime('%d/%m/%Y %H:%M')
        qr_base64 = generate_qr_code(order_code, order['total_harga'], formatted_date)
        
        return jsonify({
            "success": True,
            "qr_code": qr_base64,
            "order_code": order_code,
            "amount": float(order['total_harga'])
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Tambahkan API endpoint untuk reset password admin
@app.route('/admin/api/user/<int:user_id>/reset_password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    data = request.json
    new_password = data.get('password')
    
    if not new_password or len(new_password) < 6:
        return jsonify({"success": False, "error": "Password minimal 6 karakter"})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database error"})
    
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", 
                     (new_password, user_id))
        conn.commit()
        
        return jsonify({"success": True, "message": "Password berhasil direset"})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        # MENGGUNAKAN .get() AGAR TIDAK ERROR 400 JIKA DATA KOSONG
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Validasi sederhana sebelum ke database
        if not email or not password:
            flash("❌ Email dan password harus diisi!", "error")
            return render_template('auth.html', panel='login')
        
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "error")
            return render_template('auth.html', panel='login')
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
            user = cursor.fetchone()
            
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['email']
                session['role'] = user['role']
                
                flash(f"🎉 Selamat datang, {user['username']}!", "success")
                
                # Respon JSON jika dites via Postman (Opsional agar lebih informatif)
                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({"success": True, "message": "Login Berhasil", "user": user['username']})

                if user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('home'))
            else:
                flash("❌ Email atau password salah!", "error")
        except Exception as e:
            flash(f"Error: {e}", "error")
        finally:
            cursor.close()
            conn.close()
    
    return render_template('auth.html', panel='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash("⚠️ Semua kolom harus diisi!", "error")
            return redirect(url_for('register'))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("❌ Email sudah terdaftar. Gunakan email lain.", "error")
                return redirect(url_for('register'))

            query = "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (username, email, password, 'user'))
            
            conn.commit()
            flash("✅ Akun berhasil dibuat! Silakan login.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            conn.rollback()
            print(f"Error saat registrasi: {e}")
            flash("❌ Terjadi kesalahan sistem. Coba lagi nanti.", "error")
        finally:
            cursor.close()
            conn.close()

    return render_template('auth.html', panel='register')

# ==================== ROUTES - USER ====================
@app.route('/order', methods=['GET', 'POST'])
@login_required
def order():
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('home'))
    
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            selected_ids = request.form.getlist('selected_pizzas')
            address = request.form.get('address', '').strip()
            coordinate = request.form.get('coordinate', '')
            
            if not selected_ids:
                flash("⚠️ Pilih minimal satu pizza!", "warning")
                return redirect(url_for('order'))
            
            if not address:
                flash("⚠️ Masukkan alamat pengiriman!", "warning")
                return redirect(url_for('order'))
            
            order_summary = []
            subtotal = 0
            
            for pid in selected_ids:
                qty = int(request.form.get(f'qty_{pid}', 1))
                
                cursor.execute("SELECT * FROM menus WHERE id = %s", (pid,))
                pizza = cursor.fetchone()
                
                if pizza:
                    item_total = pizza['harga'] * qty
                    subtotal += item_total
                    
                    order_summary.append({
                        'id': pizza['id'],
                        'nama': pizza['nama'],
                        'qty': qty,
                        'harga': pizza['harga'],
                        'subtotal': item_total,
                        'gambar': pizza['gambar_url']
                    })
            
            # Pastikan session order data valid
            session['temp_order'] = {
                'items': order_summary,  # Pastikan ini list
                'subtotal': subtotal,
                'address': address,
                'coordinate': coordinate,
                'created_at': datetime.now().isoformat()
            }
            
            # Debug: Cek session data
            print(f"DEBUG order: Session order set with {len(order_summary)} items")
            
            return redirect(url_for('checkout_page'))
            
        except Exception as e:
            flash(f"Error: {e}", "error")
            import traceback
            traceback.print_exc()
        finally:
            cursor.close()
            conn.close()
    
    # GET method - show order page
    try:
        cursor.execute("SELECT * FROM menus WHERE active = 1 ORDER BY nama")
        pizzas = cursor.fetchall()
    except Exception as e:
        flash(f"Error: {e}", "error")
        pizzas = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('order.html', pizzas=pizzas)

@app.route('/checkout')
@login_required
def checkout_page():
    if 'temp_order' not in session:
        flash("⚠️ Silakan buat pesanan terlebih dahulu", "warning")
        return redirect(url_for('order'))
    
    order_data = session.get('temp_order', {})
    
    # Debug: Print order data untuk troubleshooting
    print(f"DEBUG checkout: order_data = {order_data}")
    
    # Pastikan items ada dan berupa list
    items = order_data.get('items', [])
    if not isinstance(items, list):
        items = []
    
    subtotal = order_data.get('subtotal', 0)
    
    return render_template('checkout.html', 
                         subtotal=subtotal,
                         items=items,
                         order_data=order_data)

@app.route('/process_checkout', methods=['POST'])
@login_required
def process_checkout():
    try:
        # 1. Validasi session
        if 'temp_order' not in session:
            flash("⚠️ Sesi pesanan tidak ditemukan. Silakan buat pesanan baru.", "error")
            return redirect(url_for('order'))
        
        order_data = session.get('temp_order', {})
        items = order_data.get('items', [])
        
        # Debug: Print order data
        print(f"DEBUG process_checkout: Order data keys = {list(order_data.keys())}")
        print(f"DEBUG process_checkout: Items type = {type(items)}, length = {len(items) if isinstance(items, list) else 'N/A'}")
        
        # 2. Validasi data pesanan
        if not isinstance(items, list) or len(items) == 0:
            flash("❌ Pesanan tidak valid. Tidak ada item dalam keranjang.", "error")
            return redirect(url_for('order'))
        
        # 3. Validasi form data
        payment_method = request.form.get('payment_method', 'QRIS')
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', order_data.get('address', '')).strip()
        
        # Validation checks
        validation_errors = []
        
        if not full_name:
            validation_errors.append("Nama lengkap harus diisi")
        elif len(full_name) < 3:
            validation_errors.append("Nama terlalu pendek (minimal 3 karakter)")
        
        if not phone:
            validation_errors.append("Nomor WhatsApp harus diisi")
        elif not phone.replace(' ', '').isdigit() or len(phone.replace(' ', '')) < 10:
            validation_errors.append("Nomor WhatsApp tidak valid (minimal 10 digit angka)")
        
        if not address:
            validation_errors.append("Alamat pengiriman harus diisi")
        elif len(address) < 10:
            validation_errors.append("Alamat terlalu pendek (minimal 10 karakter)")
        
        if validation_errors:
            for error in validation_errors:
                flash(f"❌ {error}", "error")
            return redirect(url_for('checkout_page'))
        
        # 4. Get user coordinates
        user_lat, user_lon = -7.797068, 110.370529  # Default location
        if order_data.get('coordinate'):
            try:
                coords = order_data['coordinate'].split(',')
                if len(coords) == 2:
                    user_lat, user_lon = float(coords[0].strip()), float(coords[1].strip())
                    print(f"DEBUG: Using coordinates from order: {user_lat}, {user_lon}")
            except Exception as e:
                print(f"WARNING: Failed to parse coordinates: {e}")
                # Use default coordinates
        
        # 5. Find nearest restaurant
        nearest_restaurant, distance = get_nearest_restaurant(user_lat, user_lon)
        
        if not nearest_restaurant:
            flash("❌ Tidak ada restoran yang tersedia untuk lokasi Anda", "error")
            return redirect(url_for('checkout_page'))
        
        print(f"DEBUG: Nearest restaurant: {nearest_restaurant.get('nama')}, Distance: {distance} km")
        
        # 6. Calculate delivery time
        estimated_prep = 20  # minutes
        estimated_delivery = estimate_delivery_time(distance) if distance else 25
        total_time = estimated_prep + estimated_delivery
        
        # 7. Calculate totals
        subtotal = order_data.get('subtotal', 0)
        
        # Tax calculation based on payment method
        tax_rates = {
            'QRIS': 0,
            'BCA': 0.005,  # 0.5%
            'COD': 0.005   # 0.5%
        }
        
        tax_rate = tax_rates.get(payment_method, 0)
        tax_amount = subtotal * tax_rate
        
        # Shipping fee calculation based on distance
        base_shipping = 15000
        additional_shipping = max(0, (distance - 5) * 2000) if distance else 0  # Rp 2,000 per km after 5km
        shipping_fee = base_shipping + additional_shipping
        
        total_final = subtotal + tax_amount + shipping_fee
        
        print(f"DEBUG: Subtotal: {subtotal}, Tax: {tax_amount}, Shipping: {shipping_fee}, Total: {total_final}")
        
        # 8. Database connection
        conn = get_db_connection()
        if not conn:
            flash("❌ Koneksi database gagal. Silakan coba lagi.", "error")
            return redirect(url_for('checkout_page'))
        
        cursor = conn.cursor()
        
        try:
            # 9. Generate order code for the entire order
            order_code = generate_order_code()
            print(f"DEBUG: Generated order code: {order_code}")
            
            # 10. Insert each item as separate order record
            order_ids = []
            for item in items:
                # Validate item structure
                if not isinstance(item, dict):
                    print(f"WARNING: Invalid item structure: {item}")
                    continue
                
                item_name = item.get('nama', 'Unknown Item')
                quantity = item.get('qty', 1)
                item_total = item.get('subtotal', 0)
                
                # Generate QR data for this item
                qr_data = generate_qr_data(order_code, total_final)
                
                # Insert order
                sql = """
                    INSERT INTO orders 
                    (user_id, menu_nama, quantity, total_harga, alamat, koordinat, 
                     status, kode_pesanan, restaurant_id, payment_method,
                     estimated_prep_time, estimated_delivery_time, total_delivery_time,
                     qr_payment_data, customer_name, customer_phone, tanggal, shipping_fee, tax_amount, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)
                """
                val = (
                    session['user_id'], 
                    item_name, 
                    quantity, 
                    item_total,
                    address, 
                    order_data.get('coordinate', ''),
                    'pending', 
                    order_code, 
                    nearest_restaurant['id'],
                    payment_method,
                    estimated_prep, 
                    estimated_delivery, 
                    total_time,
                    qr_data,
                    full_name,
                    phone,
                    shipping_fee,
                    tax_amount,
                    subtotal
                )
                
                cursor.execute(sql, val)
                order_id = cursor.lastrowid
                order_ids.append(order_id)
                
                # Insert status history
                cursor.execute("""
                    INSERT INTO order_status_history (order_id, status, updated_at)
                    VALUES (%s, 'pending', NOW())
                """, (order_id,))
                
                print(f"DEBUG: Inserted order item: {item_name} x{quantity} = Rp {item_total}")
            
            # 11. Commit transaction
            conn.commit()
            print(f"DEBUG: Transaction committed. Order IDs: {order_ids}")
            
            # 12. Clear session
            session.pop('temp_order', None)
            
            # 13. Prepare success message
            success_message = f"""
            ✅ Pesanan Berhasil!
            
            • Kode Pesanan: {order_code}
            • Estimasi Pengiriman: {total_time} menit
            • Metode Pembayaran: {payment_method}
            • Total: Rp {total_final:,.0f}
            
            Detail:
            - Subtotal: Rp {subtotal:,.0f}
            - Pajak: Rp {tax_amount:,.0f}
            - Ongkir: Rp {shipping_fee:,.0f}
            - Total: Rp {total_final:,.0f}
            
            Pesanan Anda sedang diproses. Notifikasi akan dikirim ke WhatsApp.
            """
            
            flash(success_message, "success")
            
            # 14. Optional: Send notification (simulated)
            try:
                # In production, integrate with WhatsApp API or email service
                print(f"NOTIFICATION: Order {order_code} created for {full_name} ({phone})")
            except Exception as e:
                print(f"WARNING: Notification failed: {e}")
            
            # 15. Redirect to profile page with order details
            return redirect(url_for('profile'))
            
        except mysql.connector.Error as db_error:
            conn.rollback()
            print(f"DATABASE ERROR: {db_error}")
            flash(f"❌ Database error: {db_error}", "error")
            return redirect(url_for('checkout_page'))
            
        except Exception as e:
            conn.rollback()
            print(f"ERROR in process_checkout: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f"❌ Terjadi kesalahan sistem: {str(e)}", "error")
            return redirect(url_for('checkout_page'))
            
        finally:
            cursor.close()
            conn.close()
    
    except Exception as e:
        print(f"CRITICAL ERROR in process_checkout: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"❌ Terjadi kesalahan kritis: {str(e)}", "error")
        return redirect(url_for('checkout_page'))


# Tambahkan helper function untuk mengecek validitas koordinat
def validate_coordinates(coord_str):
    """Validate coordinate string format"""
    if not coord_str:
        return False, None, None
    
    try:
        coords = coord_str.split(',')
        if len(coords) != 2:
            return False, None, None
        
        lat = float(coords[0].strip())
        lon = float(coords[1].strip())
        
        # Basic geographic bounds for Indonesia
        if -11.0 <= lat <= 6.0 and 95.0 <= lon <= 141.0:
            return True, lat, lon
        else:
            return False, lat, lon
            
    except (ValueError, AttributeError):
        return False, None, None


# Update get_nearest_restaurant function dengan validasi
def get_nearest_restaurant(user_lat, user_lon):
    """Get nearest restaurant with validation"""
    # Validate coordinates
    if not (-90 <= user_lat <= 90) or not (-180 <= user_lon <= 180):
        print(f"WARNING: Invalid coordinates: {user_lat}, {user_lon}")
        # Use default Yogyakarta coordinates
        user_lat, user_lon = -7.7956, 110.3695
    
    conn = get_db_connection()
    if not conn:
        return None, None
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM restaurants WHERE active = 1")
        restaurants = cursor.fetchall()
        
        if not restaurants:
            return None, None
        
        nearest = None
        min_distance = float('inf')
        
        for restaurant in restaurants:
            try:
                rest_lat = float(restaurant.get('latitude', 0))
                rest_lon = float(restaurant.get('longitude', 0))
                
                # Validate restaurant coordinates
                if not (-90 <= rest_lat <= 90) or not (-180 <= rest_lon <= 180):
                    print(f"WARNING: Invalid restaurant coordinates: {rest_lat}, {rest_lon}")
                    continue
                
                distance = calculate_distance(user_lat, user_lon, rest_lat, rest_lon)
                
                if distance < min_distance:
                    min_distance = distance
                    nearest = restaurant
                    
            except (ValueError, TypeError) as e:
                print(f"WARNING: Error processing restaurant {restaurant.get('id')}: {e}")
                continue
        
        if nearest:
            print(f"DEBUG: Found nearest restaurant: {nearest.get('nama')} at {min_distance:.2f} km")
        
        return nearest, min_distance if nearest else None
        
    except Exception as e:
        print(f"ERROR finding restaurant: {e}")
        return None, None
    finally:
        cursor.close()
        conn.close()


# Update estimate_delivery_time function
def estimate_delivery_time(distance_km):
    """Estimate delivery time based on distance"""
    if not distance_km or distance_km <= 0:
        return 25  # Default 25 minutes
    
    # Base time + time based on distance (30 km/h average speed)
    base_time = 15  # minutes
    travel_time = (distance_km / 30) * 60  # Convert to minutes
    
    # Add buffer time
    buffer_time = 5
    
    total_time = base_time + travel_time + buffer_time
    
    # Cap at reasonable maximum
    max_time = 120  # 2 hours max
    return min(int(total_time), max_time)


# Update generate_qr_data untuk format yang lebih baik
def generate_qr_data(order_code, amount):
    """Generate QR payment data with better formatting"""
    qr_data = {
        "merchant": "Pizza Lecker Thury",
        "order_code": order_code,
        "amount": float(amount),
        "currency": "IDR",
        "timestamp": datetime.now().isoformat(),
        "payment_method": "QRIS",
        "merchant_code": "PIZZALTHRY001",
        "checksum": hashlib.md5(f"{order_code}{amount}{datetime.now().timestamp()}".encode()).hexdigest()[:8]
    }
    return json.dumps(qr_data, indent=2)

@app.route('/profile')
@login_required
def profile():
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('home'))
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        cursor.execute("""
            SELECT o.*, r.nama as restaurant_name 
            FROM orders o 
            LEFT JOIN restaurants r ON o.restaurant_id = r.id 
            WHERE o.user_id = %s 
            ORDER BY o.tanggal DESC 
            LIMIT 10
        """, (session['user_id'],))
        orders = cursor.fetchall()
        
        user['orders'] = orders
        
    except Exception as e:
        flash(f"Error: {e}", "error")
        user = {'orders': []}
    finally:
        cursor.close()
        conn.close()
    
    return render_template('edit_profile.html', user=user)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    action = request.form.get('action')
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('profile'))
    
    cursor = conn.cursor()
    
    try:
        if action == 'update_profile':
            new_username = request.form['username']
            cursor.execute("UPDATE users SET username = %s WHERE id = %s", 
                         (new_username, session['user_id']))
            session['username'] = new_username
            flash("✅ Nama berhasil diperbarui", "success")
            
        elif action == 'change_password':
            old_password = request.form['old_password']
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            
            cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
            current_password = cursor.fetchone()[0]
            
            if old_password != current_password:
                flash("❌ Password lama salah", "error")
            elif new_password != confirm_password:
                flash("❌ Password baru tidak cocok", "error")
            elif len(new_password) < 6:
                flash("❌ Password minimal 6 karakter", "error")
            else:
                cursor.execute("UPDATE users SET password = %s WHERE id = %s", 
                             (new_password, session['user_id']))
                flash("✅ Password berhasil diubah", "success")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('profile'))

# ==================== ROUTES - ADMIN ====================
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('admin_dashboard.html', stats={'income': 0, 'sold': 0, 'new_users': 0, 'best': '-'}, orders=[])
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Ambil data menu
        cursor.execute("SELECT * FROM menus ORDER BY id DESC")
        pizzas = cursor.fetchall()
        
        # Hitung statistik
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE tanggal >= DATE_SUB(NOW(), INTERVAL 3 DAY)")
        orders_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE created_at >= DATE_SUB(NOW(), INTERVAL 3 DAY)")
        new_users = cursor.fetchone()['count']
        
        cursor.execute("SELECT COALESCE(SUM(total_harga), 0) as total FROM orders WHERE tanggal >= DATE_SUB(NOW(), INTERVAL 3 DAY)")
        income = cursor.fetchone()['total']
        
        cursor.execute("SELECT menu_nama, COUNT(*) as count FROM orders GROUP BY menu_nama ORDER BY count DESC LIMIT 1")
        best_seller = cursor.fetchone()
        
        # PERBAIKAN DI SINI: Query orders dengan join restaurants
        cursor.execute("""
            SELECT o.*, u.username, r.nama as restaurant_name 
            FROM orders o 
            LEFT JOIN users u ON o.user_id = u.id 
            LEFT JOIN restaurants r ON o.restaurant_id = r.id 
            ORDER BY o.tanggal DESC 
            LIMIT 5
        """)
        orders = cursor.fetchall()
        
        # Hitung jarak untuk setiap order jika ada koordinat
        for order in orders:
            # Berikan nilai default untuk field yang dibutuhkan template
            order['titik_restoran'] = order.get('restaurant_name', 'Restoran Pusat')
            
            # Hitung jarak jika ada koordinat
            if order.get('koordinat'):
                try:
                    user_coords = order['koordinat'].split(',')
                    user_lat, user_lon = float(user_coords[0]), float(user_coords[1])
                    
                    # Cari restoran
                    cursor.execute("SELECT latitude, longitude FROM restaurants WHERE id = %s", (order['restaurant_id'],))
                    rest = cursor.fetchone()
                    if rest:
                        distance = calculate_distance(user_lat, user_lon, float(rest['latitude']), float(rest['longitude']))
                        order['jarak_km'] = round(distance, 1)
                    else:
                        order['jarak_km'] = 0
                except:
                    order['jarak_km'] = 0
            else:
                order['jarak_km'] = 0
                
            # Hitung estimasi waktu
            if order.get('jarak_km'):
                order['estimated_minutes'] = 15 + (order['jarak_km'] * 5)
            else:
                order['estimated_minutes'] = order.get('total_delivery_time', 30)
        
        stats = {
            'income': income,
            'sold': orders_count,
            'new_users': new_users,
            'best': best_seller['menu_nama'] if best_seller else '-'
        }
        
    except Exception as e:
        flash(f"Error: {e}", "error")
        stats = {'income': 0, 'sold': 0, 'new_users': 0, 'best': '-'}
        orders = []
        pizzas = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin_dashboard.html', stats=stats, orders=orders, pizzas=pizzas)

@app.route('/admin/add', methods=['GET', 'POST'])
@admin_required
def add_menu():
    if request.method == 'POST':
        nama = request.form['nama']
        deskripsi = request.form['deskripsi']
        harga = int(request.form['harga'])
        gambar_url = request.form['gambar_url']
        kategori = request.form.get('kategori', 'Premium Signature')
        
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "error")
            return redirect(url_for('add_menu'))
        
        cursor = conn.cursor()
        try:
            sql = """
                INSERT INTO menus (nama, deskripsi, harga, gambar_url, kategori, active, created_at)
                VALUES (%s, %s, %s, %s, %s, 1, NOW())
            """
            val = (nama, deskripsi, harga, gambar_url, kategori)
            cursor.execute(sql, val)
            conn.commit()
            
            flash("✅ Menu berhasil ditambahkan", "success")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}", "error")
        finally:
            cursor.close()
            conn.close()
    
    return render_template('add.html')

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_menu(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('admin_dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            nama = request.form['nama']
            deskripsi = request.form['deskripsi']
            harga = int(request.form['harga'])
            gambar_url = request.form['gambar_url']
            
            sql = """
                UPDATE menus 
                SET nama = %s, deskripsi = %s, harga = %s, gambar_url = %s, updated_at = NOW()
                WHERE id = %s
            """
            val = (nama, deskripsi, harga, gambar_url, id)
            cursor.execute(sql, val)
            conn.commit()
            
            flash("✅ Menu berhasil diperbarui", "success")
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}", "error")
        finally:
            cursor.close()
            conn.close()
    
    try:
        cursor.execute("SELECT * FROM menus WHERE id = %s", (id,))
        pizza = cursor.fetchone()
        
        if not pizza:
            flash("❌ Menu tidak ditemukan", "error")
            return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f"Error: {e}", "error")
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
        conn.close()
    
    return render_template('edit.html', pizza=pizza)

# Ganti blok kode setelah fungsi edit_menu atau delete_order yang rusak dengan ini:
@app.route('/admin/delete/<int:id>')
@admin_required
def delete_menu(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('admin_dashboard'))
    
    cursor = conn.cursor()
    try:
        # Gunakan soft delete (active=0) atau hard delete. 
        # Di sini kita gunakan hard delete agar menu benar-benar hilang dari daftar CRUD.
        cursor.execute("DELETE FROM menus WHERE id = %s", (id,))
        conn.commit()
        flash("✅ Menu berhasil dihapus secara permanen", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    status_filter = request.args.get('status')
    
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('admin_order.html', orders=[])
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Perbaikan Query: Tambahkan JOIN ke tabel users untuk mengambil u.username
        base_query = """
            SELECT o.*, u.username, u.email, r.nama as restaurant_name,
                   (o.estimated_prep_time + o.estimated_delivery_time) as total_estimate
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            LEFT JOIN restaurants r ON o.restaurant_id = r.id
        """
        
        if status_filter:
            query = base_query + " WHERE o.status = %s ORDER BY o.tanggal DESC"
            cursor.execute(query, (status_filter,))
        else:
            query = base_query + " ORDER BY o.tanggal DESC"
            cursor.execute(query)
            
        orders = cursor.fetchall()
        
        # Ambil history status (opsional)
        for order in orders:
            cursor.execute("""
                SELECT * FROM order_status_history 
                WHERE order_id = %s 
                ORDER BY updated_at DESC
            """, (order['id'],))
            order['history'] = cursor.fetchall()
            
    except Exception as e:
        print(f"Error fetching orders: {e}")
        flash(f"Error: {e}", "error")
        orders = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin_order.html', orders=orders)

@app.route('/admin/order/update_status/<int:order_id>', methods=['POST'])
@admin_required
def update_order_status(order_id):
    new_status = request.form.get('status')
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return redirect(url_for('admin_orders'))
    
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE orders SET status = %s WHERE id = %s", 
                     (new_status, order_id))
        
        cursor.execute("""
            INSERT INTO order_status_history (order_id, status, updated_at)
            VALUES (%s, %s, NOW())
        """, (order_id, new_status))
        
        conn.commit()
        
        flash(f"✅ Status diperbarui menjadi {new_status}", "success")
        
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin_orders'))

@app.route('/admin/statistics')
@admin_required
def admin_statistics():
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('admin_statistics.html', 
                             revenue={'total_pendapatan': 0},
                             new_users={'user_baru': 0},
                             sales={'total_terjual': 0},
                             best_sellers=[],
                             daily_stats=[])
        

    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT COALESCE(SUM(total_harga), 0) as total_pendapatan
            FROM orders 
            WHERE tanggal >= DATE_SUB(CURDATE(), INTERVAL 3 DAY)
            AND status NOT IN ('dibatalkan', 'pending')
        """)
        revenue = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(*) as user_baru
            FROM users 
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 3 DAY)
        """)
        new_users = cursor.fetchone()
        
        cursor.execute("""
            SELECT COALESCE(SUM(quantity), 0) as total_terjual
            FROM orders 
            WHERE tanggal >= DATE_SUB(CURDATE(), INTERVAL 3 DAY)
            AND status NOT IN ('dibatalkan', 'pending')
        """)
        sales = cursor.fetchone()
        
        cursor.execute("""
            SELECT menu_nama, SUM(quantity) as total_terjual
            FROM orders 
            WHERE tanggal >= DATE_SUB(CURDATE(), INTERVAL 3 DAY)
            AND status NOT IN ('dibatalkan', 'pending')
            GROUP BY menu_nama
            ORDER BY total_terjual DESC
            LIMIT 5
        """)
        best_sellers = cursor.fetchall()
        
        cursor.execute("""
            SELECT 
                DATE(tanggal) as hari,
                COUNT(*) as jumlah_pesanan,
                COALESCE(SUM(total_harga), 0) as pendapatan
            FROM orders 
            WHERE tanggal >= DATE_SUB(CURDATE(), INTERVAL 3 DAY)
            AND status NOT IN ('dibatalkan', 'pending')
            GROUP BY DATE(tanggal)
            ORDER BY hari DESC
        """)
        daily_stats = cursor.fetchall()
        
    except Exception as e:
        flash(f"Error: {e}", "error")
        revenue = {'total_pendapatan': 0}
        new_users = {'user_baru': 0}
        sales = {'total_terjual': 0}
        best_sellers = []
        daily_stats = []
    finally:
        cursor.close()
        conn.close()
    
    # Tambahkan current_date ke context
    current_date = datetime.now().strftime('%d %B %Y')
    
    return render_template('admin_statistics.html',
                         revenue=revenue,
                         new_users=new_users,
                         sales=sales,
                         best_sellers=best_sellers,
                         daily_stats=daily_stats,
                         current_date=current_date)  # Tambahkan ini

@app.route('/admin/users')
@admin_required
def admin_users():
    conn = get_db_connection()
    if not conn:
        flash("Database connection error", "error")
        return render_template('admin_users.html', users=[])
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, username, email, role, 
                   DATE_FORMAT(created_at, '%d/%m/%Y %H:%i') as tanggal_daftar
            FROM users 
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        
    except Exception as e:
        flash(f"Error: {e}", "error")
        users = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin_users.html', users=users)

@app.route('/admin/api/user/<int:user_id>/toggle_role', methods=['POST'])
@admin_required
def toggle_user_role(user_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database error"})
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"success": False, "error": "User not found"})
        
        new_role = 'admin' if user['role'] == 'user' else 'user'
        
        cursor.execute("UPDATE users SET role = %s WHERE id = %s", 
                     (new_role, user_id))
        conn.commit()
        
        return jsonify({"success": True, "new_role": new_role})
        
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)})
    finally:
        cursor.close()
        conn.close()
        
@app.route('/admin/api/order/<int:order_id>/details')
def get_order_details(order_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    # Cari order di data dummy
    order = None
    for o in order_details:
        if o['id'] == order_id:
            order = o
            break
    
    if not order:
        return jsonify({'success': False, 'error': 'Order not found'}), 404
    
    # Data lengkap order
    order_details = {
        'success': True,
        'order': {
            'kode_pesanan': order.get('kode_pesanan', 'N/A'),
            'username': order.get('username', 'Unknown'),
            'email': order.get('email', 'No email'),
            'menu_nama': order.get('menu_nama', 'Unknown Menu'),
            'quantity': order.get('quantity', 1),
            'total_harga': order.get('total_harga', 0),
            'status': order.get('status', 'pending'),
            'created_at': order.get('created_at', datetime.now()).strftime('%d %b %Y %H:%M'),
            'phone': order.get('phone', '081234567890'),
            'address': 'Jl. Contoh No. 123, Jakarta'  # Dummy address
        },
        'history': [
            {'status': 'pending', 'updated_at': '10:00 - 01 Jan 2024'},
            {'status': 'diproses', 'updated_at': '11:30 - 01 Jan 2024'},
            {'status': order.get('status', 'pending'), 'updated_at': 'Sekarang'}
        ]
    }
    
    return jsonify(order_details)

### API SEMUA
@app.route('/api/pizzas')
@login_required
def get_pizzas_api():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nama, harga, deskripsi FROM menus WHERE active = 1")
    pizzas = cursor.fetchall()
    
    return jsonify({
        "status": "success",
        "total_items": len(pizzas),
        "pizzas": pizzas
    })

@app.route('/api/checkout', methods=['POST'])
@login_required
def api_checkout():
    # Mengambil data JSON dari Body Postman
    data = request.get_json()
    items = data.get('items') # List ID pizza dan qty
    address = data.get('address')
    
    if not items or not address:
        return jsonify({"status": "error", "message": "Data pesanan tidak lengkap"}), 400

    order_code = generate_order_code()
    total_bayar = 150000 # Contoh perhitungan statis untuk tes

    # BUKTI DI POSTMAN: Notifikasi pesanan masuk
    return jsonify({
        "status": "success",
        "message": "✅ Pesanan Berhasil Dibuat!",
        "data": {
            "kode_pesanan": order_code,
            "total_pembayaran": total_bayar,
            "alamat_kirim": address,
            "estimasi_tiba": "30 Menit"
        }
    }), 201
    
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() if request.is_json else request.form
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not email or not password:
        return jsonify({"status": "error", "message": "⚠️ Semua kolom harus diisi!"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "❌ Email sudah terdaftar"}), 409

        cursor.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, 'user')", 
                     (username, email, password))
        conn.commit()
        return jsonify({"status": "success", "message": "✅ Akun berhasil dibuat! Silakan login."}), 201
    finally:
        cursor.close()
        conn.close()
@app.route('/api/profile', methods=['GET'])
@login_required
def api_profile():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, username, email, role FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        return jsonify({
            "status": "success",
            "message": "Data profil berhasil diambil",
            "user_data": user
        }), 200
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/add-menu', methods=['POST'])
@admin_required
def api_add_menu():
    data = request.get_json() if request.is_json else request.form
    nama = data.get('nama')
    harga = data.get('harga')
    deskripsi = data.get('deskripsi')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO menus (nama, harga, deskripsi, active) VALUES (%s, %s, %s, 1)", 
                     (nama, harga, deskripsi))
        conn.commit()
        return jsonify({
            "status": "success", 
            "message": f"✅ Menu '{nama}' berhasil ditambahkan ke database!"
        }), 201
    finally:
        cursor.close()
        conn.close()
        
@app.route('/api/admin/delete-menu/<int:id>', methods=['DELETE'])
@admin_required
def api_delete_menu(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM menus WHERE id = %s", (id,))
        conn.commit()
        return jsonify({
            "status": "success",
            "message": f"🗑️ Menu ID {id} telah dihapus permanen"
        }), 200
    finally:
        cursor.close()
        conn.close()
        
@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    data = request.get_json()
    email = data.get('email')
    new_password = data.get('new_password')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if not cursor.fetchone():
            return jsonify({"status": "error", "message": "❌ Email tidak ditemukan"}), 404
            
        cursor.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
        conn.commit()
        return jsonify({
            "status": "success",
            "message": f"✅ Password untuk {email} berhasil diubah! Silakan login ulang."
        }), 200
    finally:
        cursor.close()
        conn.close()

@app.route('/api/user/orders', methods=['GET'])
@login_required
def api_user_order_history():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT o.kode_pesanan, o.menu_nama, o.quantity, o.total_harga, o.status, o.tanggal 
            FROM orders o 
            WHERE o.user_id = %s 
            ORDER BY o.tanggal DESC
        """, (session['user_id'],))
        orders = cursor.fetchall()
        
        return jsonify({
            "status": "success",
            "message": "Riwayat pesanan berhasil diambil",
            "total_pesanan": len(orders),
            "orders": orders
        }), 200
    finally:
        cursor.close()
        conn.close()
        
@app.route('/api/admin/update-order-status', methods=['PUT'])
@admin_required
def api_admin_update_status():
    data = request.get_json()
    order_code = data.get('kode_pesanan')
    new_status = data.get('status') # contoh: 'diproses', 'dikirim', 'selesai'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE orders SET status = %s WHERE kode_pesanan = %s", (new_status, order_code))
        conn.commit()
        
        return jsonify({
            "status": "success",
            "message": f"✅ Status pesanan {order_code} sekarang menjadi: {new_status}"
        }), 200
    finally:
        cursor.close()
        conn.close()
        
@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def api_admin_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Hitung Total Pendapatan
        cursor.execute("SELECT SUM(total_harga) as total_income FROM orders WHERE status = 'selesai'")
        income = cursor.fetchone()['total_income'] or 0
        
        # Hitung Total User
        cursor.execute("SELECT COUNT(id) as total_users FROM users")
        users_count = cursor.fetchone()['total_users']
        
        return jsonify({
            "status": "success",
            "message": "Data statistik berhasil diambil",
            "data": {
                "total_pendapatan": f"Rp {income:,.0f}",
                "jumlah_pengguna": users_count,
                "server_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }), 200
    finally:
        cursor.close()
        conn.close()
        



@app.route('/logout')
def logout():
    session.clear()
    flash("👋 Anda telah logout", "info")
    return redirect(url_for('home'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)