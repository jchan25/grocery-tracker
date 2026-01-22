import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager

# Use PostgreSQL in production (DATABASE_URL), SQLite locally
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        # Render uses postgres:// but psycopg2 needs postgresql://
        url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        conn = psycopg2.connect(url)
        return conn, True  # True = is_postgres
    else:
        conn = sqlite3.connect("grocery.db")
        conn.row_factory = sqlite3.Row
        return conn, False  # False = is_sqlite

@contextmanager
def get_db():
    conn, is_postgres = get_connection()
    try:
        yield conn, is_postgres
    finally:
        conn.close()

def execute_query(conn, is_postgres, query, params=None):
    """Execute a query, handling SQLite vs PostgreSQL differences"""
    if is_postgres:
        # Convert ? to %s for PostgreSQL
        query = query.replace('?', '%s')
        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cursor = conn.cursor()

    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    return cursor

def fetchall_as_dicts(cursor, is_postgres):
    """Fetch all results as list of dicts"""
    if is_postgres:
        return cursor.fetchall()  # Already dicts with RealDictCursor
    else:
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def fetchone_as_dict(cursor, is_postgres):
    """Fetch one result as dict"""
    row = cursor.fetchone()
    if row is None:
        return None
    if is_postgres:
        return dict(row)
    else:
        return dict(row)

def init_db():
    conn, is_postgres = get_connection()
    cursor = conn.cursor()

    if is_postgres:
        # PostgreSQL schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                whole_foods_url TEXT,
                image_url TEXT,
                on_list INTEGER DEFAULT 1,
                store_id INTEGER REFERENCES stores(id),
                added_by INTEGER REFERENCES users(id),
                occasional INTEGER DEFAULT 0,
                target_frequency INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id SERIAL PRIMARY KEY,
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id),
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                price REAL,
                on_sale INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id SERIAL PRIMARY KEY,
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                price REAL,
                regular_price REAL,
                on_sale INTEGER DEFAULT 0,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS store_history (
                id SERIAL PRIMARY KEY,
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                from_store_id INTEGER REFERENCES stores(id),
                to_store_id INTEGER REFERENCES stores(id),
                changed_by INTEGER REFERENCES users(id),
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_purchases_item
            ON purchases (item_id, purchased_at DESC)
        """)
    else:
        # SQLite schema
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                whole_foods_url TEXT,
                image_url TEXT,
                on_list INTEGER DEFAULT 1,
                store_id INTEGER,
                added_by INTEGER,
                occasional INTEGER DEFAULT 0,
                target_frequency INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (store_id) REFERENCES stores (id),
                FOREIGN KEY (added_by) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                user_id INTEGER,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                price REAL,
                on_sale INTEGER DEFAULT 0,
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                price REAL,
                regular_price REAL,
                on_sale INTEGER DEFAULT 0,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS store_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                from_store_id INTEGER,
                to_store_id INTEGER,
                changed_by INTEGER,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE,
                FOREIGN KEY (from_store_id) REFERENCES stores (id),
                FOREIGN KEY (to_store_id) REFERENCES stores (id),
                FOREIGN KEY (changed_by) REFERENCES users (id)
            );

            CREATE INDEX IF NOT EXISTS idx_purchases_item
            ON purchases (item_id, purchased_at DESC);
        """)

        # Add columns to existing SQLite tables if they don't exist
        for col in ['store_id INTEGER', 'added_by INTEGER', 'occasional INTEGER DEFAULT 0', 'target_frequency INTEGER', 'image_url TEXT']:
            try:
                cursor.execute(f"ALTER TABLE items ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass
        try:
            cursor.execute("ALTER TABLE purchases ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

def add_item(name, whole_foods_url=None, image_url=None, store_id=None, added_by=None, occasional=False):
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres,
            "INSERT INTO items (name, whole_foods_url, image_url, on_list, store_id, added_by, occasional) VALUES (?, ?, ?, 1, ?, ?, ?)" + (" RETURNING id" if is_postgres else ""),
            (name, whole_foods_url, image_url, store_id, added_by, 1 if occasional else 0)
        )
        conn.commit()
        if is_postgres:
            return cursor.fetchone()['id']
        return cursor.lastrowid

def get_all_items():
    """Get all items with purchase stats"""
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres, """
            SELECT i.*,
                   COUNT(p.id) as purchase_count,
                   MAX(p.purchased_at) as last_purchased,
                   MAX(ph.price) as current_price,
                   MAX(ph.on_sale) as on_sale
            FROM items i
            LEFT JOIN purchases p ON p.item_id = i.id
            LEFT JOIN price_history ph ON ph.id = (
                SELECT id FROM price_history
                WHERE item_id = i.id
                ORDER BY checked_at DESC
                LIMIT 1
            )
            GROUP BY i.id
            ORDER BY i.on_list DESC, i.created_at DESC
        """)
        items = fetchall_as_dicts(cursor, is_postgres)

        result = []
        for item in items:
            item['frequency_days'] = calculate_frequency(item['id'])
            item['next_purchase'] = predict_next_purchase(item['id'])
            result.append(item)
        return result

def get_items_on_list():
    """Get items currently on the shopping list"""
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres, """
            SELECT i.*,
                   COUNT(p.id) as purchase_count,
                   MAX(p.purchased_at) as last_purchased,
                   MAX(ph.price) as current_price,
                   MAX(ph.on_sale) as on_sale,
                   s.name as store_name,
                   u.name as added_by_name
            FROM items i
            LEFT JOIN purchases p ON p.item_id = i.id
            LEFT JOIN price_history ph ON ph.id = (
                SELECT id FROM price_history
                WHERE item_id = i.id
                ORDER BY checked_at DESC
                LIMIT 1
            )
            LEFT JOIN stores s ON i.store_id = s.id
            LEFT JOIN users u ON i.added_by = u.id
            WHERE i.on_list = 1
            GROUP BY i.id, s.name, u.name
            ORDER BY i.created_at DESC
        """)
        items = fetchall_as_dicts(cursor, is_postgres)

        result = []
        for item in items:
            item['frequency_days'] = calculate_frequency(item['id'])
            result.append(item)
        return result

def get_frequent_items():
    """Get items not on list, ordered by purchase frequency (excludes occasional items)"""
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres, """
            SELECT i.*,
                   COUNT(p.id) as purchase_count,
                   MAX(p.purchased_at) as last_purchased,
                   MAX(ph.price) as current_price,
                   MAX(ph.on_sale) as on_sale,
                   s.name as store_name,
                   u.name as added_by_name
            FROM items i
            LEFT JOIN purchases p ON p.item_id = i.id
            LEFT JOIN price_history ph ON ph.id = (
                SELECT id FROM price_history
                WHERE item_id = i.id
                ORDER BY checked_at DESC
                LIMIT 1
            )
            LEFT JOIN stores s ON i.store_id = s.id
            LEFT JOIN users u ON i.added_by = u.id
            WHERE i.on_list = 0 AND (i.occasional = 0 OR i.occasional IS NULL)
            GROUP BY i.id, s.name, u.name
            HAVING COUNT(p.id) >= 1
            ORDER BY COUNT(p.id) DESC, MAX(p.purchased_at) DESC
            LIMIT 20
        """)
        items = fetchall_as_dicts(cursor, is_postgres)

        result = []
        for item in items:
            item['frequency_days'] = calculate_frequency(item['id'])
            item['next_purchase'] = predict_next_purchase(item['id'])
            result.append(item)
        return result

def calculate_frequency(item_id):
    """Calculate average days between purchases"""
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres,
            "SELECT purchased_at FROM purchases WHERE item_id = ? ORDER BY purchased_at",
            (item_id,)
        )
        purchases = fetchall_as_dicts(cursor, is_postgres)

        if len(purchases) < 2:
            return None

        # Calculate intervals between purchases
        intervals = []
        for i in range(1, len(purchases)):
            prev_str = str(purchases[i-1]['purchased_at'])
            curr_str = str(purchases[i]['purchased_at'])
            # Handle both string and datetime objects
            if 'T' in prev_str or ' ' in prev_str:
                prev = datetime.fromisoformat(prev_str.replace(' ', 'T').split('.')[0])
                curr = datetime.fromisoformat(curr_str.replace(' ', 'T').split('.')[0])
            else:
                prev = datetime.fromisoformat(prev_str)
                curr = datetime.fromisoformat(curr_str)
            days = (curr - prev).days
            if days > 0:  # Ignore same-day purchases
                intervals.append(days)

        if not intervals:
            return None

        return round(sum(intervals) / len(intervals))

def predict_next_purchase(item_id):
    """Predict when item will be needed next"""
    with get_db() as (conn, is_postgres):
        # Get item info including target_frequency
        cursor = execute_query(conn, is_postgres,
            "SELECT target_frequency FROM items WHERE id = ?",
            (item_id,)
        )
        item = fetchone_as_dict(cursor, is_postgres)

        cursor = execute_query(conn, is_postgres,
            "SELECT purchased_at FROM purchases WHERE item_id = ? ORDER BY purchased_at DESC LIMIT 1",
            (item_id,)
        )
        last = fetchone_as_dict(cursor, is_postgres)

        if not last:
            return None

        # Use target_frequency if set, otherwise calculate from purchases
        freq = item['target_frequency'] if item and item.get('target_frequency') else calculate_frequency(item_id)
        if not freq:
            return None

        last_str = str(last['purchased_at'])
        if 'T' in last_str or ' ' in last_str:
            last_date = datetime.fromisoformat(last_str.replace(' ', 'T').split('.')[0])
        else:
            last_date = datetime.fromisoformat(last_str)
        next_date = last_date + timedelta(days=freq)
        return next_date.strftime('%Y-%m-%d')

def get_item(item_id):
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres,
            "SELECT * FROM items WHERE id = ?", (item_id,)
        )
        return fetchone_as_dict(cursor, is_postgres)

def update_item(item_id, name=None, whole_foods_url=None, image_url=None, on_list=None):
    with get_db() as (conn, is_postgres):
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if whole_foods_url is not None:
            updates.append("whole_foods_url = ?")
            params.append(whole_foods_url)
        if image_url is not None:
            updates.append("image_url = ?")
            params.append(image_url)
        if on_list is not None:
            updates.append("on_list = ?")
            params.append(1 if on_list else 0)

        if updates:
            params.append(item_id)
            query = f"UPDATE items SET {', '.join(updates)} WHERE id = ?"
            execute_query(conn, is_postgres, query, params)
            conn.commit()

def delete_item(item_id):
    with get_db() as (conn, is_postgres):
        execute_query(conn, is_postgres, "DELETE FROM purchases WHERE item_id = ?", (item_id,))
        execute_query(conn, is_postgres, "DELETE FROM price_history WHERE item_id = ?", (item_id,))
        execute_query(conn, is_postgres, "DELETE FROM store_history WHERE item_id = ?", (item_id,))
        execute_query(conn, is_postgres, "DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()

def record_purchase(item_id, price=None, on_sale=False, user_id=None):
    """Record a purchase and remove item from list"""
    with get_db() as (conn, is_postgres):
        execute_query(conn, is_postgres,
            "INSERT INTO purchases (item_id, price, on_sale, user_id) VALUES (?, ?, ?, ?)",
            (item_id, price, 1 if on_sale else 0, user_id)
        )
        execute_query(conn, is_postgres, "UPDATE items SET on_list = 0 WHERE id = ?", (item_id,))
        conn.commit()

def add_to_list(item_id):
    """Add an item back to the shopping list"""
    with get_db() as (conn, is_postgres):
        execute_query(conn, is_postgres, "UPDATE items SET on_list = 1 WHERE id = ?", (item_id,))
        conn.commit()

def get_purchase_history(item_id, limit=30):
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres,
            """SELECT * FROM purchases
               WHERE item_id = ?
               ORDER BY purchased_at DESC
               LIMIT ?""",
            (item_id, limit)
        )
        return fetchall_as_dicts(cursor, is_postgres)

def add_price_record(item_id, price, regular_price=None, on_sale=False):
    with get_db() as (conn, is_postgres):
        execute_query(conn, is_postgres,
            """INSERT INTO price_history (item_id, price, regular_price, on_sale)
               VALUES (?, ?, ?, ?)""",
            (item_id, price, regular_price, 1 if on_sale else 0)
        )
        conn.commit()

def get_price_history(item_id, limit=30):
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres,
            """SELECT * FROM price_history
               WHERE item_id = ?
               ORDER BY checked_at DESC
               LIMIT ?""",
            (item_id, limit)
        )
        return fetchall_as_dicts(cursor, is_postgres)

def get_sale_items():
    """Get all items currently on sale"""
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres, """
            SELECT i.*, ph.price, ph.regular_price, ph.on_sale
            FROM items i
            JOIN price_history ph ON ph.id = (
                SELECT id FROM price_history
                WHERE item_id = i.id
                ORDER BY checked_at DESC
                LIMIT 1
            )
            WHERE ph.on_sale = 1 AND i.on_list = 1
        """)
        return fetchall_as_dicts(cursor, is_postgres)

# User management
def add_user(name):
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres,
            "INSERT INTO users (name) VALUES (?)" + (" RETURNING id" if is_postgres else ""),
            (name,)
        )
        conn.commit()
        if is_postgres:
            return cursor.fetchone()['id']
        return cursor.lastrowid

def get_all_users():
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres, "SELECT * FROM users ORDER BY name")
        return fetchall_as_dicts(cursor, is_postgres)

def delete_user(user_id):
    with get_db() as (conn, is_postgres):
        execute_query(conn, is_postgres, "DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

# Store management
def add_store(name):
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres,
            "INSERT INTO stores (name) VALUES (?)" + (" RETURNING id" if is_postgres else ""),
            (name,)
        )
        conn.commit()
        if is_postgres:
            return cursor.fetchone()['id']
        return cursor.lastrowid

def get_all_stores():
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres, "SELECT * FROM stores ORDER BY name")
        return fetchall_as_dicts(cursor, is_postgres)

def delete_store(store_id):
    with get_db() as (conn, is_postgres):
        execute_query(conn, is_postgres, "DELETE FROM stores WHERE id = ?", (store_id,))
        conn.commit()

def change_item_store(item_id, new_store_id, changed_by=None):
    """Change item's store and log the change"""
    with get_db() as (conn, is_postgres):
        # Get current store
        cursor = execute_query(conn, is_postgres, "SELECT store_id FROM items WHERE id = ?", (item_id,))
        current = fetchone_as_dict(cursor, is_postgres)
        from_store_id = current['store_id'] if current else None

        # Log the change
        execute_query(conn, is_postgres,
            "INSERT INTO store_history (item_id, from_store_id, to_store_id, changed_by) VALUES (?, ?, ?, ?)",
            (item_id, from_store_id, new_store_id, changed_by)
        )

        # Update the item
        execute_query(conn, is_postgres, "UPDATE items SET store_id = ? WHERE id = ?", (new_store_id, item_id))
        conn.commit()

def get_store_history(item_id):
    """Get store change history for an item"""
    with get_db() as (conn, is_postgres):
        cursor = execute_query(conn, is_postgres, """
            SELECT sh.*,
                   fs.name as from_store_name,
                   ts.name as to_store_name,
                   u.name as changed_by_name
            FROM store_history sh
            LEFT JOIN stores fs ON sh.from_store_id = fs.id
            LEFT JOIN stores ts ON sh.to_store_id = ts.id
            LEFT JOIN users u ON sh.changed_by = u.id
            WHERE sh.item_id = ?
            ORDER BY sh.changed_at DESC
        """, (item_id,))
        return fetchall_as_dicts(cursor, is_postgres)

def set_target_frequency(item_id, days):
    """Set target frequency for an item (in days)"""
    with get_db() as (conn, is_postgres):
        execute_query(conn, is_postgres, "UPDATE items SET target_frequency = ? WHERE id = ?", (days, item_id))
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
