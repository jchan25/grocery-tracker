from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from functools import wraps
import os

import database as db

# Get absolute path to static folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)

# Simple password protection
APP_PASSWORD = os.environ.get('APP_PASSWORD', '')  # Set in environment for production

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Skip auth if no password is set
        if not APP_PASSWORD:
            return f(*args, **kwargs)
        if not session.get('authenticated'):
            if request.is_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

# Initialize database on startup
db.init_db()

@app.route('/login', methods=['GET'])
def login_page():
    if not APP_PASSWORD or session.get('authenticated'):
        return redirect(url_for('index'))
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login - Grocery Tracker</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                min-height: 100vh;
                background: linear-gradient(135deg, #1a5f2a 0%, #2d8f4e 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: system-ui, -apple-system, sans-serif;
            }
            .login-box {
                background: white;
                padding: 40px;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                width: 90%;
                max-width: 400px;
            }
            h1 { color: #1a5f2a; margin-bottom: 10px; }
            p { color: #666; margin-bottom: 25px; }
            input {
                width: 100%;
                padding: 15px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 16px;
                margin-bottom: 15px;
            }
            input:focus { outline: none; border-color: #1a5f2a; }
            button {
                width: 100%;
                padding: 15px;
                background: #1a5f2a;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
            }
            button:hover { background: #15501f; }
            .error { color: #e74c3c; margin-bottom: 15px; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h1>Grocery Tracker</h1>
            <p>Enter the password to continue</p>
            <form method="POST" action="/login">
                <input type="password" name="password" placeholder="Password" autofocus required>
                <button type="submit">Login</button>
            </form>
        </div>
    </body>
    </html>
    '''

@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password', '')
    if password == APP_PASSWORD:
        session['authenticated'] = True
        return redirect(url_for('index'))
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login - Grocery Tracker</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                min-height: 100vh;
                background: linear-gradient(135deg, #1a5f2a 0%, #2d8f4e 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: system-ui, -apple-system, sans-serif;
            }
            .login-box {
                background: white;
                padding: 40px;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                width: 90%;
                max-width: 400px;
            }
            h1 { color: #1a5f2a; margin-bottom: 10px; }
            p { color: #666; margin-bottom: 25px; }
            input {
                width: 100%;
                padding: 15px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 16px;
                margin-bottom: 15px;
            }
            input:focus { outline: none; border-color: #1a5f2a; }
            button {
                width: 100%;
                padding: 15px;
                background: #1a5f2a;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
            }
            button:hover { background: #15501f; }
            .error { color: #e74c3c; margin-bottom: 15px; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h1>Grocery Tracker</h1>
            <p>Enter the password to continue</p>
            <p class="error">Incorrect password. Please try again.</p>
            <form method="POST" action="/login">
                <input type="password" name="password" placeholder="Password" autofocus required>
                <button type="submit">Login</button>
            </form>
        </div>
    </body>
    </html>
    ''', 401

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login_page'))

@app.route('/')
@require_auth
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/api/items', methods=['GET'])
@require_auth
def get_items():
    """Get all items"""
    items = db.get_all_items()
    return jsonify(items)

@app.route('/api/items/on-list', methods=['GET'])
@require_auth
def get_items_on_list():
    """Get items currently on shopping list"""
    items = db.get_items_on_list()
    return jsonify(items)

@app.route('/api/items/frequent', methods=['GET'])
@require_auth
def get_frequent_items():
    """Get frequently purchased items not on list"""
    items = db.get_frequent_items()
    return jsonify(items)

@app.route('/api/items', methods=['POST'])
@require_auth
def add_item():
    """Add a new grocery item to the list"""
    data = request.json
    name = (data.get('name') or '').strip()
    whole_foods_url = (data.get('whole_foods_url') or '').strip() or None
    image_url = (data.get('image_url') or '').strip() or None
    price = data.get('price')
    store_id = data.get('store_id')
    added_by = data.get('added_by')
    occasional = data.get('occasional', False)

    if not name:
        return jsonify({'error': 'Item name is required'}), 400

    item_id = db.add_item(name, whole_foods_url, image_url, store_id, added_by, occasional)

    if price is not None:
        try:
            price = float(price)
            db.add_price_record(item_id, price, price, False)
        except (ValueError, TypeError):
            pass

    return jsonify({'id': item_id, 'message': 'Item added'}), 201

@app.route('/api/items/<int:item_id>', methods=['PUT'])
@require_auth
def update_item(item_id):
    """Update item details"""
    data = request.json
    db.update_item(
        item_id,
        name=data.get('name'),
        whole_foods_url=data.get('whole_foods_url'),
        image_url=data.get('image_url'),
        on_list=data.get('on_list')
    )
    return jsonify({'message': 'Item updated'})

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
@require_auth
def delete_item(item_id):
    """Delete an item permanently"""
    db.delete_item(item_id)
    return jsonify({'message': 'Item deleted'})

@app.route('/api/items/<int:item_id>/bought', methods=['POST'])
@require_auth
def mark_bought(item_id):
    """Mark item as bought - records purchase and removes from list"""
    data = request.json or {}
    price = data.get('price')
    on_sale = data.get('on_sale', False)
    user_id = data.get('user_id')

    if price:
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = None

    db.record_purchase(item_id, price, on_sale, user_id)
    return jsonify({'message': 'Purchase recorded'})

@app.route('/api/items/<int:item_id>/add-to-list', methods=['POST'])
@require_auth
def add_to_list(item_id):
    """Add item back to shopping list"""
    db.add_to_list(item_id)
    return jsonify({'message': 'Added to list'})

@app.route('/api/items/<int:item_id>/price', methods=['POST'])
@require_auth
def update_price(item_id):
    """Update price for an item"""
    data = request.json
    price = data.get('price')
    on_sale = data.get('on_sale', False)

    if price is None:
        return jsonify({'error': 'Price is required'}), 400

    try:
        price = float(price)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid price'}), 400

    db.add_price_record(item_id, price, price, on_sale)
    return jsonify({'message': 'Price updated'})

@app.route('/api/items/<int:item_id>/purchases', methods=['GET'])
@require_auth
def get_purchase_history(item_id):
    """Get purchase history for an item"""
    history = db.get_purchase_history(item_id)
    return jsonify(history)

@app.route('/api/items/<int:item_id>/price-history', methods=['GET'])
@require_auth
def get_price_history(item_id):
    """Get price history for an item"""
    history = db.get_price_history(item_id)
    return jsonify(history)

# User endpoints
@app.route('/api/users', methods=['GET'])
@require_auth
def get_users():
    """Get all users"""
    users = db.get_all_users()
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
@require_auth
def create_user():
    """Create a new user"""
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'User name is required'}), 400
    try:
        user_id = db.add_user(name)
        return jsonify({'id': user_id, 'message': 'User created'}), 201
    except Exception as e:
        return jsonify({'error': 'User already exists'}), 400

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_auth
def remove_user(user_id):
    """Delete a user"""
    db.delete_user(user_id)
    return jsonify({'message': 'User deleted'})

# Store endpoints
@app.route('/api/stores', methods=['GET'])
@require_auth
def get_stores():
    """Get all stores"""
    stores = db.get_all_stores()
    return jsonify(stores)

@app.route('/api/stores', methods=['POST'])
@require_auth
def create_store():
    """Create a new store"""
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Store name is required'}), 400
    try:
        store_id = db.add_store(name)
        return jsonify({'id': store_id, 'message': 'Store created'}), 201
    except Exception as e:
        return jsonify({'error': 'Store already exists'}), 400

@app.route('/api/stores/<int:store_id>', methods=['DELETE'])
@require_auth
def remove_store(store_id):
    """Delete a store"""
    db.delete_store(store_id)
    return jsonify({'message': 'Store deleted'})

@app.route('/api/items/<int:item_id>/store', methods=['PUT'])
@require_auth
def change_store(item_id):
    """Change item's store"""
    data = request.json
    new_store_id = data.get('store_id')
    changed_by = data.get('changed_by')
    db.change_item_store(item_id, new_store_id, changed_by)
    return jsonify({'message': 'Store updated'})

@app.route('/api/items/<int:item_id>/store-history', methods=['GET'])
@require_auth
def get_store_history(item_id):
    """Get store change history for an item"""
    history = db.get_store_history(item_id)
    return jsonify(history)

@app.route('/api/items/<int:item_id>/frequency', methods=['PUT'])
@require_auth
def set_frequency(item_id):
    """Set target frequency for an item"""
    data = request.json
    days = data.get('days')
    db.set_target_frequency(item_id, days)
    return jsonify({'message': 'Frequency updated'})

if __name__ == '__main__':
    print("Starting Grocery Tracker...")
    print("Server running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
