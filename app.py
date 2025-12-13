from flask import Flask, request, redirect, session

app = Flask(__name__)
app.secret_key = "mg-secret-key"

# ------------------------------
# IN-MEMORY DATA (NO FIREBASE)
# ------------------------------
users = {"admin": "1234"}  # username : password
jobs = []
inventory = []
used_inventory = []

# ------------------------------
# HTML TEMPLATES (INLINE)
# ------------------------------
def page(title, body):
    return f"""
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{ background:#0b111b;color:white;font-family:Poppins,sans-serif;padding:30px }}
            a,button {{ color:#00b4ff }}
            input,button {{ padding:8px;margin:5px }}
            .box {{ background:rgba(255,255,255,0.06);padding:20px;border-radius:12px }}
        </style>
    </head>
    <body>
        {body}
    </body>
    </html>
    """

# ------------------------------
# LOGIN
# ------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["user"]
        p = request.form["pass"]
        if users.get(u) == p:
            session["user"] = u
            return redirect("/dashboard")
        return page("Login", "<h3>Invalid login</h3><a href='/'>Try again</a>")

    return page("Login", """
    <div class="box">
    <h2>MG Login</h2>
    <form method="post">
        <input name="user" placeholder="Username"><br>
        <input name="pass" placeholder="Password" type="password"><br>
        <button>Login</button>
    </form>
    </div>
    """)

# ------------------------------
# DASHBOARD
# ------------------------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return page("Dashboard", """
    <div class="box">
    <h1>MG Dashboard</h1>
    <ul>
        <li><a href="/jobs">Jobs</a></li>
        <li><a href="/inventory">Inventory</a></li>
        <li><a href="/used">Used Inventory</a></li>
        <li><a href="/logout">Logout</a></li>
    </ul>
    </div>
    """)

# ------------------------------
# JOBS
# ------------------------------
@app.route("/jobs", methods=["GET", "POST"])
def jobs_page():
    if request.method == "POST":
        jobs.append(request.form["job"])
    job_list = "<br>".join(jobs)
    return page("Jobs", f"""
    <div class="box">
    <h2>Jobs</h2>
    <form method="post">
        <input name="job" placeholder="New job">
        <button>Add</button>
    </form>
    <p>{job_list}</p>
    <a href="/dashboard">Back</a>
    </div>
    """)

# ------------------------------
# INVENTORY
# ------------------------------
@app.route("/inventory", methods=["GET", "POST"])
def inventory_page():
    if request.method == "POST":
        inventory.append(request.form["item"])
    items = "<br>".join(inventory)
    return page("Inventory", f"""
    <div class="box">
    <h2>Inventory</h2>
    <form method="post">
        <input name="item" placeholder="Item name">
        <button>Add</button>
    </form>
    <p>{items}</p>
    <a href="/dashboard">Back</a>
    </div>
    """)

# ------------------------------
# USED INVENTORY
# ------------------------------
@app.route("/used", methods=["GET", "POST"])
def used_page():
    if request.method == "POST":
        used_inventory.append(request.form["used"])
    used = "<br>".join(used_inventory)
    return page("Used Inventory", f"""
    <div class="box">
    <h2>Used Inventory</h2>
    <form method="post">
        <input name="used" placeholder="Used item">
        <button>Add</button>
    </form>
    <p>{used}</p>
    <a href="/dashboard">Back</a>
    </div>
    """)

# ------------------------------
# LOGOUT
# ------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ------------------------------
# RUN
# ------------------------------
app.run(debug=True)
