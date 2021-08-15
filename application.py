import os

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy.orm import Session as orm_session


from helpers import apology, login_required, lookup, usd
from models import Users, Transactions, Base

# create engine
DATABASE_URL = os.environ.get('DATABASE_URL') or 'sqlite+pysqlite:///finance.db'
DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')
engine = create_engine(DATABASE_URL, future=True, echo=True)

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

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


# Make sure API key is set
if not os.environ.get("IEXAPIS_API_KEY"):
    raise RuntimeError("IEXAPIS_API_KEY not set")


def sum_stocks(user_id):
    # define def sum_stocks
    with orm_session(engine) as ss:
        transactions = ss.query(Transactions.symbol, Transactions.type, func.sum(Transactions.shares)).\
                        filter(Transactions.user_id == user_id).\
                        group_by(Transactions.symbol, Transactions.type)
    # calculate stock Quantity
    stocks = {}
    for symbol, type, sum in transactions:
        if type == 'BUY':
            stocks[symbol] = stocks.get(symbol, 0) + sum
        else:
            stocks[symbol] = stocks.get(symbol, 0) - sum

    return stocks

def get_user_cash(user_id):
    with orm_session(engine) as ss:
        user = ss.query(Users).filter(Users.id==user_id).first()
    return user.cash

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
    cash = get_user_cash(user_id)
    
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
        # get user cash
        cash = get_user_cash(user_id)
        print(f"price is {total_price}, cash is {cash}")

        if total_price > cash:
            return apology(f"No cash available for buy {shares} {quote_data['name']} stocks", 400)

        """Buy shares of stock"""
        # save transaction
        with orm_session(engine) as ss:
            transaction = Transactions()
            transaction.user_id = user_id
            transaction.type = 'BUY'
            transaction.symbol = symbol
            transaction.price = price
            transaction.shares = shares
            ss.add(transaction)

            # update cash
            cash -= total_price
            user = ss.query(Users).filter(Users.id==user_id).first()
            user.cash = cash
            ss.commit()
        
        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = []
    with orm_session(engine) as ss:
        rows = ss.query(Transactions).filter(Transactions.user_id == session.get("user_id"))
        for row in rows:
            transaction = {'type': row.type,
                            'symbol': row.symbol,
                            'price': row.price,
                            'shares': row.shares,
                            'created_datetime': row.created_datetime,
                            }
            transactions.append(transaction)
    
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

        with orm_session(engine) as ss:
            # Query database for username
            user = ss.query(Users).filter(Users.username == request.form.get('username')).first()
            
            # Ensure username exists and password is correct
            if user == None or not check_password_hash(user.hash, request.form.get("password")):
                return apology("invalid username and/or password", 403)

            # Remember which user has logged in
            session["user_id"] = user.id

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

        with orm_session(engine) as ss:
            """Register user"""
            # check username is already in used
            users = ss.query(Users)
            for user in users:
                if user.username == username:
                    return apology("The user name is already in used.", 400)

            user = Users();
            user.username = username
            user.hash = generate_password_hash(password)
            ss.add(user)
            ss.commit()
            print(f'id: {user.id}')

            # Remember which user has logged in
            session["user_id"] = user.id

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

        with orm_session(engine) as ss:
            # get current pw hash
            hash = ss.query(Users).filter(Users.id==user_id).first().hash

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
            user = ss.query(Users).filter(Users.id==user_id).first()
            user.hash = hash
            ss.commit()

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

        with orm_session(engine) as ss:
            # save transaction
            transaction = Transactions()
            transaction.user_id = user_id
            transaction.type = 'SELL'
            transaction.symbol = symbol
            transaction.price = price
            transaction.shares = shares
            ss.add(transaction)

            # update cash
            user = ss.query(Users).filter(Users.id==user_id).first()
            user.cash += price * shares
            ss.commit()

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

        with orm_session(engine) as ss:
            # update cash
            user = ss.query(Users).filter(Users.id==user_id).first()
            user.cash += deposit
            ss.commit()

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