import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

'''
.schema transactions
CREATE TABLE transactions (
    id INTEGER,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price NUMERIC NOT NULL,
    shares INTEGER NOT NULL,
    created_datetime TIMESTAMP DEFAULT (datetime(CURRENT_TIMESTAMP,'localtime')),
    PRIMARY KEY(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
'''

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("IEXAPIS_API_KEY"):
    raise RuntimeError("API_KEY not set")


def sum_stocks(user_id):
    # define def sum_stocks
    transactions = db.execute("SELECT symbol, type, SUM( shares ) AS sum FROM transactions \
                                WHERE user_id = ? \
                                GROUP BY symbol, type", user_id)

    # calculate stock Quantity
    stocks = {}
    for t in transactions:
        symbol = t['symbol']
        if t['type'] == 'BUY':
            stocks[symbol] = stocks.get(symbol, 0) + t['sum']
        else:
            stocks[symbol] = stocks.get(symbol, 0) - t['sum']

    return stocks


@app.route("/")
@login_required
def index():
    user_id = session.get("user_id")
    stocks = sum_stocks(user_id)

    # add rows
    rows = []
    for k, v in stocks.items():
        if v < 1:
            continue
        # get quote
        quote_data = lookup(k)
        price = quote_data['price']

        row = {}
        row['symbol'] = k
        row['name'] = quote_data['name']
        row['shares'] = v
        row['price'] = price
        row['total'] = v * price
        rows.append(row)

    # get user cash
    cash = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]["cash"]
    print(f'{cash}, type: {type(cash)}')
    total = cash
    for row in rows:
        total += row["total"]
    rows.append({'symbol': 'CASH', 'total': cash})
    return render_template("index.html", total=total, rows=rows)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        # get symbol
        symbol = request.form.get('symbol').upper()

        # check symbol is inputed
        if not symbol:
            return apology("symbol is required.", 400)

        # get quote
        quote_data = lookup(symbol)

        if not quote_data:
            return apology(f"can't get {symbol} quote.", 400)

        # get shares
        shares = request.form.get('shares')

        # check shares is integer
        try:
            shares = int(shares)
        except ValueError:
            return apology("Shares must be integer", 400)

        # check shares is greater than 1
        if shares < 1:
            return apology("shares must be greater than 1.", 400)

        # check user has enough money
        price = float(quote_data['price'])
        total_price = price * shares

        user_id = session.get("user_id")
        cash = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]["cash"]
        print(f"price is {total_price}, cash is {cash}")

        if total_price > cash:
            return apology(f"No cash available for buy {shares} {quote_data['name']} stocks", 400)

        """Buy shares of stock"""
        # save transaction
        db.execute("INSERT INTO transactions (user_id, type, symbol, price, shares) VALUES(?, ?, ?, ?, ?)",
                   user_id, "BUY", symbol, price, shares)

        # update cash
        cash -= total_price
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, user_id)

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ? ", session.get("user_id"))
    if len(transactions) > 0:
        return render_template("history.html", rows=transactions)
    else:
        return apology("no history", 400)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == 'POST':
        """Get stock quote."""
        symbol = request.form.get('symbol')
        # check symbol is inputed
        if not symbol:
            return apology("symbol is required.", 400)

        # get quote
        quote_data = lookup(symbol)

        if not quote_data:
            return apology(f"can't get {symbol} quote.", 400)

        # return quote_data
        return render_template("quote.html", quote=quote_data)
    else:
        return render_template("quote.html")

    return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # check username
        if not username:
            return apology("username is required.", 400)

        # check passwords
        if not password:
            return apology("password is required.", 400)
        if not confirmation:
            return apology("Confirmation password is required.", 400)
        elif password != confirmation:
            return apology("Confirmation password do not match.", 400)

        """Register user"""
        # check username is already in used
        users = db.execute("SELECT * FROM users")
        for user in users:
            if username == user['username']:
                return apology("The user name is already in used.", 400)

        hash = generate_password_hash(password)
        id = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)
        print(f'id: {id}')

        # Remember which user has logged in
        session["user_id"] = id

        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/changepw", methods=["GET", "POST"])
@login_required
def changepw():
    if request.method == "POST":
        user_id = session.get("user_id")

        # get form data
        current_pw = request.form.get("current_pw")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure password was submitted
        if not current_pw:
            return apology("must provide password", 400)

        # get current pw hash
        hash = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]["hash"]

        # Ensure password is correct
        if not check_password_hash(hash, current_pw):
            return apology("invalid password", 400)

        # check new passwords
        if not password:
            return apology("new password is required.", 400)
        if not confirmation:
            return apology("Confirmation password is required.", 400)
        elif password != confirmation:
            return apology("Confirmation password do not match.", 400)

        """Update password"""
        hash = generate_password_hash(password)
        id = db.execute("UPDATE users SET hash = ? WHERE id = ?", hash, user_id)

        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("changepw.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = session.get("user_id")
    stocks = sum_stocks(user_id)

    if request.method == "POST":
        """Sell shares of stock"""
        # get symbol
        symbol = request.form.get('symbol').upper()

        # check symbol is inputed
        if not symbol in stocks.keys():
            return apology("symbol is invalid", 400)

        # get shares
        shares = request.form.get('shares')

        # check shares is integer
        try:
            shares = int(shares)
        except ValueError:
            return apology("Shares must be integer", 400)

        # check shares is greater than 1
        if shares < 1:
            return apology("shares must be greater than 1.", 400)

        # check user has enough shares
        if shares > stocks[symbol]:
            return apology(f"shares must be less than {stocks[symbol]}.", 400)

        # get current price
        price = float(lookup(symbol)['price'])

        # save transaction
        db.execute("INSERT INTO transactions (user_id, type, symbol, price, shares) VALUES(?, ?, ?, ?, ?)",
                   user_id, "SELL", symbol, price, shares)

        # update cash
        cash = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]["cash"]
        cash += price * shares
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, user_id)

        # Redirect user to home page
        return redirect("/")

    else:
        symbols = []
        # add symbol to symbols
        for k, v in stocks.items():
            if v > 0:
                symbols.append(k)

        return render_template("sell.html", symbols=symbols)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        user_id = session.get("user_id")
        # get deposit
        deposit = request.form.get('deposit')
        # check shares is integer
        try:
            deposit = int(deposit)
        except ValueError:
            return apology("deposit must be integer", 400)

        # check shares is greater than 1
        if deposit < 1:
            return apology("deposit must be greater than 1.", 400)

        # update cash
        cash = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]["cash"]
        cash += deposit
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, user_id)

        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("deposit.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

if __name__ == '__main__':
    app.run()