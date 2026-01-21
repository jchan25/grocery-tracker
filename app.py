from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

import database as db

# Get absolute path to static folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR)
CORS(app)

# Initialize database on startup
db.init_db()

@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/api/items', methods=['GET'])
def get_items():
    """Get all items"""
    items = db.get_all_items()
    return jsonify(items)

@app.route('/api/items/on-list', methods=['GET'])
def get_items_on_list():
    """Get items currently on shopping list"""
    items = db.get_items_on_list()
    return jsonify(items)

@app.route('/api/items/frequent', methods=['GET'])
def get_frequent_items():
    """Get frequently purchased items not on list"""
    items = db.get_frequent_items()
    return jsonify(items)

@app.route('/api/items', methods=['POST'])
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
def delete_item(item_id):
    """Delete an item permanently"""
    db.delete_item(item_id)
    return jsonify({'message': 'Item deleted'})

@app.route('/api/items/<int:item_id>/bought', methods=['POST'])
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
def add_to_list(item_id):
    """Add item back to shopping list"""
    db.add_to_list(item_id)
    return jsonify({'message': 'Added to list'})

@app.route('/api/items/<int:item_id>/price', methods=['POST'])
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
def get_purchase_history(item_id):
    """Get purchase history for an item"""
    history = db.get_purchase_history(item_id)
    return jsonify(history)

@app.route('/api/items/<int:item_id>/price-history', methods=['GET'])
def get_price_history(item_id):
    """Get price history for an item"""
    history = db.get_price_history(item_id)
    return jsonify(history)

# User endpoints
@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users"""
    users = db.get_all_users()
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
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
def remove_user(user_id):
    """Delete a user"""
    db.delete_user(user_id)
    return jsonify({'message': 'User deleted'})

# Store endpoints
@app.route('/api/stores', methods=['GET'])
def get_stores():
    """Get all stores"""
    stores = db.get_all_stores()
    return jsonify(stores)

@app.route('/api/stores', methods=['POST'])
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
def remove_store(store_id):
    """Delete a store"""
    db.delete_store(store_id)
    return jsonify({'message': 'Store deleted'})

@app.route('/api/items/<int:item_id>/store', methods=['PUT'])
def change_store(item_id):
    """Change item's store"""
    data = request.json
    new_store_id = data.get('store_id')
    changed_by = data.get('changed_by')
    db.change_item_store(item_id, new_store_id, changed_by)
    return jsonify({'message': 'Store updated'})

@app.route('/api/items/<int:item_id>/store-history', methods=['GET'])
def get_store_history(item_id):
    """Get store change history for an item"""
    history = db.get_store_history(item_id)
    return jsonify(history)

@app.route('/api/items/<int:item_id>/frequency', methods=['PUT'])
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
