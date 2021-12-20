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
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    
    stocks = db.execute("SELECT symbol FROM transactions WHERE user_id=?", session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
    total = 0
    
    for stock in stocks:
        amount = db.execute("SELECT SUM(amount) AS amount FROM transactions WHERE user_id=? AND symbol=?", session["user_id"], stock["symbol"])
        stock["amount"] = amount[0]["amount"]
        updated_stock = lookup(stock["symbol"])
        stock["price"] = updated_stock["price"]
        stock["total"] = float(stock["price"]) * float(stock["amount"])
        
        total = total + float(stock["total"])
    
    total = total + float(cash[0]["cash"])
    
    cash[0]["total"] = total
       
    return render_template("index.html", stocks=stocks, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    
    if request.method == "POST":
        
        if not request.form.get("symbol"):
            return apology("symbol is required", 400)
            
        stock = lookup(request.form.get("symbol"))
        
        if not stock:
            return apology("symbol doesn't exist", 400)
            
        if not request.form.get("shares") or int(request.form.get("shares")) < 1:
            return apology("number of shares must be a positive integer", 400)
            
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        buy_quantity = request.form.get("shares")
        price = stock["price"]
        
        if int(user_cash[0]["cash"]) < (int(price) * int(buy_quantity)):
            return apology("not enough cash to comoplete the transaction", 400)
            
        new_cash = int(user_cash[0]["cash"]) - (int(price) * int(buy_quantity))
            
        db.execute("INSERT INTO transactions (symbol, amount, price, user_id, transaction_type) VALUES (?, ?, ?, ?, 'buy')", stock["symbol"], int(buy_quantity), int(stock["price"]), session["user_id"])
        db.execute("UPDATE users SET cash=? WHERE id=?", new_cash, session["user_id"])
        
        return redirect("/")
        
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    stocks = db.execute("SELECT * FROM transactions WHERE user_id=?", session["user_id"])
    
    return render_template("history.html", stocks=stocks)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

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
    """Get stock quote."""
    
    if request.method == "POST":
        
        if not request.form.get("symbol"):
            return apology("symbol is required", 400)
        
        stock = lookup(request.form.get("symbol"))
        
        if not stock:
            return apology("symbol is invalid", 400)
        
        return render_template("quoted.html", stock=stock)
    
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    
    if request.method == "POST":
        
        if not request.form.get("username"):
            return apology("must provide username", 400)
            
        db_username = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        
        if len(db_username) != 0:
            return apology("username already exists", 400)
        
        if not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide password", 400)
            
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)
            
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"), method="pbkdf2:sha256", salt_length=8)
        
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, password)
        
        user = db.execute("SELECT * FROM users WHERE username = ?", username)
        
        session["user_id"] = user[0]["id"]
    
        return redirect("/")
        
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    
    user_stocks = db.execute("SELECT symbol FROM transactions WHERE user_id=?", session["user_id"])
    
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("a stock must be selected", 400)
            
        if not request.form.get("shares") or int(request.form.get("shares")) < 1:
            return apology("number of shares must be a positive integer", 400)
            
        symbol = request.form.get("symbol")
        quantity = int(request.form.get("shares"))
        
        user_symbol = db.execute("SELECT symbol FROM transactions WHERE user_id=? AND symbol=?", session["user_id"], symbol)
        user_amount = db.execute("SELECT SUM(amount) AS amount FROM transactions WHERE user_id=? AND symbol=?", session["user_id"], symbol)
        
        if not user_symbol:
            return apology("you don't own any of the selected shares", 400)
        
        amount = int(user_amount[0]["amount"])
        
        if amount < quantity:
            return apology("you don't own that many of the selected shares", 400)
        
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"]) 
        stock = lookup(symbol)
        price = int(stock["price"])
        sell_price = 0 - price
        sell_quantity = 0 - quantity
        new_cash = int(user_cash[0]["cash"]) + (price * quantity)
            
        db.execute("INSERT INTO transactions (symbol, amount, price, user_id, transaction_type) VALUES (?, ?, ?, ?, 'sell')", symbol, sell_quantity, sell_price, session["user_id"])
        db.execute("UPDATE users SET cash=? WHERE id=?", new_cash, session["user_id"])
            
        return redirect("/")
        
    else:
        return render_template("sell.html", user_stocks=user_stocks)
        
        
@app.route("/cash", methods=["GET", "POST"])
def cash():
    """Add cash"""

    if request.method == "POST":
        cash = int(request.form.get("cash"))
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        new_cash = int(user_cash[0]["cash"]) + cash
        
        db.execute("UPDATE users SET cash=? WHERE id=?", new_cash, session["user_id"])
        
        return redirect("/")
        
    else:
        return render_template("cash.html")
    

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
