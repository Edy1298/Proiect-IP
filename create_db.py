import sqlite3, config

connection = sqlite3.connect(config.DB_FILE)

cursor = connection.cursor()

cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            balance REAL DEFAULT 10000.0
        )
    ''')

cursor.execute("""
    CREATE TABLE IF NOT EXISTS virtual_balance (
        balance REAL NOT NULL
    )
""")

cursor.execute('SELECT COUNT(*) FROM virtual_balance')
row_count = cursor.fetchone()[0]

# insert value of balance only if table is empty
if row_count == 0:
    cursor.execute("""
        INSERT INTO virtual_balance (balance) VALUES ('100000')
    """)

cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY,
        symbol TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL UNIQUE,
        exchange TEXT NOT NULL
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_price (
        id INTEGER PRIMARY KEY,
        stock_id INTEGER,
        date TEXT NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume INTEGER NOT NULL,
        FOREIGN KEY (stock_id) REFERENCES stock (id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        stock_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        bought_price REAL NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (stock_id) REFERENCES stock (id)
    )
""")

connection.commit()