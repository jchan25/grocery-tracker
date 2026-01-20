from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os

import database as db
from scraper import scrape_whole_foods_price

# Get absolute path to static folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR)
CORS(app)

# Initialize database on startup
db.init_db()

# Background scheduler for daily price checks
scheduler = BackgroundScheduler()

def check_all_prices_job():
    """Background job to check all item prices"""
    print(f"[{datetime.now()}] Running scheduled price check...")
    items = db.get_items_with_urls()
    for item in items:
        try:
            print(f"  Checking: {item['name']}")
            price_info = scrape_whole_foods_price(item['whole_foods_url'])
            if price_info.price is not None:
                db.add_price_record(
                    item['id'],
                    price_info.price,
                    price_info.regular_price,
                    price_info.on_sale
                )
                print(f"    Price: ${price_info.price}, On Sale: {price_info.on_sale}")
            else:
                print(f"    Error: {price_info.error}")
        except Exception as e:
            print(f"    Failed: {e}")
    print(f"[{datetime.now()}] Price check complete!")

# Schedule daily price check at 8 AM
scheduler.add_job(check_all_prices_job, 'cron', hour=8, minute=0)
scheduler.start()

# API Routes

@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/api/items', methods=['GET'])
def get_items():
    """Get all grocery items with current prices"""
    items = db.get_all_items()
    return jsonify(items)

@app.route('/api/items', methods=['POST'])
def add_item():
    """Add a new grocery item"""
    data = request.json
    name = data.get('name', '').strip()
    whole_foods_url = data.get('whole_foods_url', '').strip() or None

    if not name:
        return jsonify({'error': 'Item name is required'}), 400

    item_id = db.add_item(name, whole_foods_url)

    # If URL provided, immediately check the price
    if whole_foods_url:
        price_info = scrape_whole_foods_price(whole_foods_url)
        if price_info.price is not None:
            db.add_price_record(
                item_id,
                price_info.price,
                price_info.regular_price,
                price_info.on_sale
            )

    return jsonify({'id': item_id, 'message': 'Item added successfully'}), 201

@app.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    """Update a grocery item"""
    data = request.json
    db.update_item(
        item_id,
        name=data.get('name'),
        whole_foods_url=data.get('whole_foods_url'),
        purchased=data.get('purchased')
    )
    return jsonify({'message': 'Item updated successfully'})

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Delete a grocery item"""
    db.delete_item(item_id)
    return jsonify({'message': 'Item deleted successfully'})

@app.route('/api/items/<int:item_id>/check-price', methods=['POST'])
def check_item_price(item_id):
    """Manually trigger a price check for an item"""
    item = db.get_item(item_id)
    if not item:
        return jsonify({'error': 'Item not found'}), 404

    if not item['whole_foods_url']:
        return jsonify({'error': 'No Whole Foods URL set for this item'}), 400

    price_info = scrape_whole_foods_price(item['whole_foods_url'])

    if price_info.error:
        return jsonify({'error': price_info.error}), 500

    if price_info.price is not None:
        db.add_price_record(
            item_id,
            price_info.price,
            price_info.regular_price,
            price_info.on_sale
        )

    return jsonify({
        'price': price_info.price,
        'regular_price': price_info.regular_price,
        'on_sale': price_info.on_sale,
        'product_name': price_info.product_name
    })

@app.route('/api/items/<int:item_id>/price-history', methods=['GET'])
def get_item_price_history(item_id):
    """Get price history for an item"""
    history = db.get_price_history(item_id)
    return jsonify(history)

@app.route('/api/sales', methods=['GET'])
def get_sales():
    """Get all items currently on sale"""
    items = db.get_sale_items()
    return jsonify(items)

@app.route('/api/check-all-prices', methods=['POST'])
def check_all_prices():
    """Manually trigger a price check for all items"""
    items = db.get_items_with_urls()
    results = []

    for item in items:
        price_info = scrape_whole_foods_price(item['whole_foods_url'])
        if price_info.price is not None:
            db.add_price_record(
                item['id'],
                price_info.price,
                price_info.regular_price,
                price_info.on_sale
            )
        results.append({
            'item_id': item['id'],
            'name': item['name'],
            'price': price_info.price,
            'on_sale': price_info.on_sale,
            'error': price_info.error
        })

    return jsonify(results)

if __name__ == '__main__':
    print("Starting Grocery Tracker...")
    print("Daily price checks scheduled for 8:00 AM")
    print("Server running at http://localhost:5000")
    app.run(debug=True, port=5000)
