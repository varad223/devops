import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import time
from sqlalchemy.exc import OperationalError

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me")

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root123")
DB_HOST = os.getenv("DB_HOST", "mysql")
DB_NAME = os.getenv("DB_NAME", "appdb")

# SQLAlchemy URI using PyMySQL
app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Models
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def root():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return redirect(url_for("login"))

@app.route("/index")
@login_required
def index():
    msgs = Message.query.order_by(Message.id.desc()).limit(100).all()
    return render_template("index.html", messages=[(m.message,) for m in msgs])

@app.route("/submit", methods=["POST"])
@login_required
def submit():
    new_message = request.form.get("new_message")
    if not new_message:
        return jsonify({"error": "empty"}), 400
    msg = Message(message=new_message)
    db.session.add(msg)
    db.session.commit()
    return jsonify({"message": new_message})

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").strip()
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")
        if not username or not email or not password:
            flash("provide username, email and password", "warning")
            return redirect(url_for("register"))
        if User.query.filter((User.username==username)|(User.email==email)).first():
            flash("user exists", "warning")
            return redirect(url_for("register"))
        u = User(username=username, email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash("registration successful — please login", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("username")  # username or email field
        password = request.form.get("password")
        user = User.query.filter((User.username==identifier)|(User.email==identifier)).first()
        if not user or not user.check_password(password):
            flash("invalid credentials", "danger")
            return redirect(url_for("login"))
        login_user(user)
        flash("logged in", "success")
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("you have been logged out", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    # Wait for DB to be ready before creating tables
    with app.app_context():
        max_attempts = 10
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"[app] Attempt {attempt}/{max_attempts} to connect to DB and create tables...")
                db.create_all()
                print("[app] DB is ready and tables are ensured.")
                break
            except OperationalError as e:
                print(f"[app] DB not ready yet ({e}). Sleeping 3 seconds...")
                time.sleep(3)
        else:
            print("[app] Could not connect to DB after retries. Exiting.")
            raise SystemExit(1)

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )