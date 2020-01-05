from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd
from datetime import datetime

# Configure application
app = Flask(__name__)


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
db = SQL("postgres://lwospfhkqetgnl:0b691c2d8c24ac7d8232bfb92ec908c43075e2d3a5c33fcd441b25ff5bffc123@ec2-174-129-33-107.compute-1.amazonaws.com:5432/d2oblsj06uhat8?sslmode=require")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Create a dict of stock information unique to the user
    rows = db.execute("SELECT symbol, sum(shares) FROM portfolio WHERE id = :user_id GROUP BY symbol", user_id=session["user_id"])

    # Create a list of user stock dicts
    stocks = []
    holdings = 0
    for row in rows:

        # Find current price of stock
        quote = lookup(row['symbol'])

        # Find total value of stock
        total = row['sum(shares)'] * quote['price']
        total = float(total)

        holdings += total

        # Create a dict of individual stock informationa and append it to a list of other stocks
        stockrow = {"symbol": row["symbol"], "shares": row["sum(shares)"], "price": usd(quote["price"]), "total": usd(total)}
        stocks.append(stockrow)

    # Find user's remaining cash
    cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
    cash = cash[0]["cash"]

    grandtotal = cash + holdings

    return render_template("index.html", stocks=stocks, cash=usd(cash), grandtotal=usd(grandtotal))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Set local variables
        stock = request.form.get("symbol")
        shares = request.form.get("shares")
        quote = lookup(stock)
        user_id = session["user_id"]

        # Ensure stock symbol was submitted
        if not stock:
            return apology("must provide stock symbol", 400)

        # Ensure a positive number of shares was submitted
        if not shares:
            return apology("must provide number of shares", 400)

        if not shares.isdigit():
            return apology("must provide number of shares", 400)

        # Check if stock symbol is valid
        if not quote:
            return apology("stock symbol not valid", 400)

        # Can user afford the stock?
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        cash = cash[0]["cash"]
        price = quote['price']
        cost = float(price) * float(shares)

        # If user can't afford it, apologize
        if cost > cash:
            return apology("not enough funds", 400)

        # Else, add stock shares to portfolio
        now = datetime.now().time()
        purchase = db.execute("INSERT INTO portfolio (id, symbol, price, shares, saletype) VALUES (:user_id, :stock, :price, :shares, :saletype)",
                            user_id=session["user_id"], stock=stock, price=cost, shares=shares, saletype="Purchase")

        # Update cash in users table
        cash = db.execute("UPDATE users SET cash = cash - :cost WHERE id = :user_id", cost=cost, user_id=session["user_id"])

        return index()

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Create a dict of all user's transactions
    sales = db.execute("SELECT * from portfolio WHERE id = :user_id", user_id=session["user_id"])

    return render_template("history.html", sales=sales)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return index()

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
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Save symbol from html
        symbol = request.form.get("symbol")

        # Check if symbol exists
        if not symbol:
            return apology("must provide stock symbol", 400)

        # Lookup a quote from yahoo
        quote = lookup(symbol)

        # If stock is not valid, return apology
        if not quote:
            return apology("stock symbol doesn't exist", 400)

        # Else, send quote to new html page
        else:
            return render_template("quoted.html", name=quote['name'], price=usd(quote['price']), symbol=quote['symbol'])

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        # Ensure password confirmation was submitted
        elif not confirmation:
            return apology("must provide password confirmation", 400)

        # Ensure password and confirmation match
        elif password != confirmation:
            return apology("password and confirmation do not match", 400)

        # Hash password
        password_hash = generate_password_hash(password)

        # Ensure username is unique
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :password_hash)",
                            username=username, password_hash=password_hash)

        # If not unique...
        if not result:
            return apology("username already exists", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Log user in automatically
        session["user_id"] = rows[0]["id"]

        # Head to logged in page
        return render_template("index.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Import variables
        user_id = session["user_id"]
        symbol = request.form.get("symbol")
        sellshares = float(request.form.get("shares"))

        # Ensure stock symbol was submitted
        if not symbol:
            return apology("must provide stock symbol", 400)

        # Ensure number of shares were submitted
        if not sellshares:
            return apology("must provide number of shares", 400)

        # Ensure user has enough shares to sell
        shares = db.execute("SELECT sum(shares) FROM portfolio WHERE id = :user_id AND symbol = :symbol",
                            user_id=session["user_id"], symbol=symbol)
        shares = shares[0]["sum(shares)"]
        if sellshares > shares:
            return apology("number of shares exceeds amount you own", 400)

        # Create transaction variables
        quote = lookup(symbol)
        price = quote['price'] * sellshares
        sellshares = -sellshares
        now = datetime.now().time()

        # Insert sold stock into user's portfolio
        sell = db.execute("INSERT INTO portfolio (id, symbol, price, shares, saletype) VALUES (:user_id, :symbol, :price, :sellshares, :saletype)",
                        user_id=user_id, symbol=symbol, price=price, sellshares=sellshares, saletype="Sale")

        # Add sale price back to user's wallet
        cash = db.execute("UPDATE users SET cash = cash + :price WHERE id = :user_id", price=price, user_id=session["user_id"])

        # Show updated portfolio
        return index()

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        stocks = db.execute("SELECT symbol FROM portfolio WHERE id = :user_id GROUP BY symbol", user_id=session["user_id"])
        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
