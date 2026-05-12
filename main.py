import config, sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash

from trading_bot import buy_or_sell, predict_price_trend

from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, balance):
        self.id = id
        self.username = username
        self.balance = balance

@login_manager.user_loader
def load_user(user_id):
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT id, username, balance FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return User(row['id'], row['username'], row['balance'])
    return None

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        connection = sqlite3.connect(config.DB_FILE)
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        connection.close()

        if user_row and check_password_hash(user_row['password_hash'], password):
            user_obj = User(user_row['id'], user_row['username'], user_row['balance'])
            login_user(user_obj)
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password")
            
    return render_template("login.html") # Asigură-te că ai acest fișier în templates

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = generate_password_hash(request.form.get('password'))
        
        try:
            connection = sqlite3.connect(config.DB_FILE)
            cursor = connection.cursor()
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password))
            connection.commit()
            connection.close()
            flash("Account created! Please log in.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists.")
            
    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/")
@login_required
def index():
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("""
       SELECT id, symbol, name FROM stock ORDER BY symbol
    """)

    rows = cursor.fetchall()

    return render_template("index.html", stocks=rows, balance=round(current_user.balance, 2))

@app.route("/search", methods=["POST"])
def search():
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    search = request.form["stock-search"]
    cursor.execute("""
            SELECT id, symbol, name
            FROM stock
            WHERE symbol LIKE ? OR name LIKE ?
            ORDER BY symbol
        """, (f"%{search}%", f"%{search}%"))

    rows = cursor.fetchall()

    cursor.execute("""
                SELECT balance FROM virtual_balance
            """)

    # round shown balance to 2 digits
    balance = round(cursor.fetchone()["balance"], 2)

    return render_template("index.html", stocks=rows, balance=balance)

@app.route("/stock/<symbol>")
@login_required
def stock_detail(symbol):
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("SELECT id, symbol, name FROM stock WHERE symbol = ?", (symbol,))
    row = cursor.fetchone()
    
    if not row:
        flash("Stock not found!")
        return redirect(url_for('index'))

    cursor.execute("SELECT * FROM stock_price WHERE stock_id = ? ORDER BY date ASC", (row["id"],))
    prices = cursor.fetchall()

    if not prices:
        flash(f"Nu există date de preț disponibile pentru {symbol}.")
        return redirect(url_for('index'))

    cursor.execute("""
            SELECT SUM(quantity) as total FROM portfolio 
            WHERE stock_id = ? AND user_id = ?
        """, (row["id"], current_user.id))
    
    result = cursor.fetchone()
    stock_quantity = result['total'] if result['total'] else 0

    try:
        price_trend = predict_price_trend(symbol)
        action = buy_or_sell(symbol)
    except Exception:
        price_trend = {'trend': 'Unknown', 'patterns': []}
        action = 'Hold'

    return render_template("stock_detail.html", 
                           stock=row, 
                           bars=prices,
                           last_bar=prices[-1],
                           balance=round(current_user.balance, 2), 
                           stock_quantity=stock_quantity,
                           action=action, 
                           trend=price_trend['trend'], 
                           patterns=price_trend['patterns'])
@app.route("/buy_stock/<symbol>", methods=['POST'])
def buy_stock(symbol):
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id FROM stock WHERE symbol = ?
    """, (symbol,))

    row = cursor.fetchone()
    stock_id = row["id"]

    cursor.execute("""
        SELECT * FROM stock_price
        WHERE stock_id = ?
        ORDER BY date DESC
    """, (stock_id,))

    row = cursor.fetchone()
    stock_price = row["close"]
    quantity = int(request.form['buy-quantity'])
    # cost of buying the chosen stocks
    cost = stock_price * quantity

    # flash user if they cannot afford the transaction selected
    if (cost > current_user.balance):
        flash("You do not have enough money for this transaction!")
        return redirect(url_for("stock_detail", symbol=symbol))

    # update balance after purchase
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (cost, current_user.id))

    cursor.execute("""
        INSERT INTO portfolio (user_id, stock_id, quantity, bought_price) VALUES (?, ?, ?, ?)
    """, (current_user.id, stock_id, quantity, stock_price))

    connection.commit()

    return redirect(url_for("portfolio"))

@app.route("/sell_stock/<symbol>", methods=['POST'])
def sell_stock(symbol):
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id FROM stock WHERE symbol = ?
    """, (symbol,))

    row = cursor.fetchone()
    stock_id = row["id"]

    cursor.execute("""
        SELECT id, quantity FROM portfolio WHERE stock_id = ?
    """, (stock_id,))

    # remove the sold stocks from portfolio
    stocks = cursor.fetchall()
    sold_quantity = int(request.form['sell-quantity'])
    for stock in stocks:
        if stock["quantity"] <= sold_quantity:
            # stock["id"] in this context is the row id of portfolio!!!
            cursor.execute("""
                DELETE FROM portfolio WHERE id = ?
            """, (stock["id"],))
            sold_quantity -= stock["quantity"]
        elif sold_quantity > 0:
            cursor.execute("""
                UPDATE portfolio SET quantity = quantity - ? WHERE id = ?
            """, (sold_quantity, stock["id"]))
            sold_quantity = 0
        else:
            break

    cursor.execute("""
        SELECT * FROM stock_price
        WHERE stock_id = ?
        ORDER BY date DESC
    """, (stock_id,))

    row = cursor.fetchone()
    stock_price = row["close"]
    quantity = int(request.form['sell-quantity'])
    # calculate money gained and add it to virtual balance
    value = stock_price * quantity

    cursor.execute("""
        UPDATE users SET balance = balance + ? WHERE id = ?
    """, (value, current_user.id))

    connection.commit()

    return redirect(url_for("portfolio"))

@app.route("/portfolio")
def portfolio():
    connection = sqlite3.connect(config.DB_FILE)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT stock.symbol, stock.name, portfolio.quantity, portfolio.bought_price
        FROM stock 
        JOIN portfolio ON stock.id = portfolio.stock_id
        WHERE portfolio.user_id = ?
    """, (current_user.id,))

    rows = cursor.fetchall()


    # round shown balance to 2 digits
    balance = round(current_user.balance, 2)

    cursor.execute("""
        SELECT COUNT (*) FROM portfolio
    """)

    # get count of number of rows (used for truncating the recent prices table)
    count = cursor.fetchone()[0]

    # use left join to keep duplicates of stocks in the order that they appear in the table!!!!!
    cursor.execute("""
    SELECT stock_price.close
    FROM portfolio 
    LEFT JOIN stock_price ON stock_price.stock_id = portfolio.stock_id
    WHERE portfolio.user_id = ?
    ORDER BY stock_price.date DESC
    """, (current_user.id,))

    recent_prices = cursor.fetchall()
    # create a list of the 2 lists in parallel for easier iteration (take only required number of prices)
    stocks_prices = list(zip(rows, recent_prices[:count]))

    return render_template("portfolio.html", stocks_prices=stocks_prices, balance=balance)

if __name__ == "__main__":
    app.run(debug=True)
