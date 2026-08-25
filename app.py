import os
import io
import csv
import shutil
from datetime import datetime, date, timedelta
from functools import wraps
from decimal import Decimal, InvalidOperation

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, send_file, jsonify, abort
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.getenv("DATABASE_PATH", os.path.join(DATA_DIR, "guilherme_eletrica.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_PATH
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

db = SQLAlchemy(app)


# -------------------- Models --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AppSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True, default=1)
    business_name = db.Column(db.String(120), default="Guilherme Elétrica")
    owner_name = db.Column(db.String(120), default="Guilherme")
    phone = db.Column(db.String(40), default="")
    whatsapp = db.Column(db.String(40), default="")
    city = db.Column(db.String(120), default="")
    pix_key = db.Column(db.String(120), default="")
    hourly_rate = db.Column(db.Numeric(12, 2), default=0)
    footer_text = db.Column(db.String(255), default="Serviço elétrico com organização e segurança.")


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False, index=True)
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(140), default="")
    cpf_cnpj = db.Column(db.String(30), default="")
    address = db.Column(db.String(255), default="")
    city = db.Column(db.String(120), default="")
    reference = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    services = db.relationship("Service", backref="client", lazy=True)
    quotes = db.relationship("Quote", backref="client", lazy=True)


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    service_date = db.Column(db.Date, nullable=False, index=True)
    service_time = db.Column(db.Time, nullable=True)
    all_day = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, default="")
    address = db.Column(db.String(255), default="")
    status = db.Column(db.String(30), default="scheduled", index=True)  # scheduled, in_progress, completed, cancelled
    charge_type = db.Column(db.String(20), default="fixed")  # fixed/hourly
    hourly_rate = db.Column(db.Numeric(12, 2), default=0)
    labor_value = db.Column(db.Numeric(12, 2), default=0)
    material_value = db.Column(db.Numeric(12, 2), default=0)
    discount = db.Column(db.Numeric(12, 2), default=0)
    total_value = db.Column(db.Numeric(12, 2), default=0)
    payment_status = db.Column(db.String(20), default="pending", index=True)  # pending/partial/paid
    amount_paid = db.Column(db.Numeric(12, 2), default=0)
    payment_method = db.Column(db.String(40), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    timer_sessions = db.relationship("TimerSession", backref="service", cascade="all, delete-orphan", lazy=True)
    service_materials = db.relationship("ServiceMaterial", backref="service", cascade="all, delete-orphan", lazy=True)

    @property
    def timer_running(self):
        return any(x.ended_at is None for x in self.timer_sessions)

    def elapsed_seconds(self):
        total = 0
        now = datetime.utcnow()
        for s in self.timer_sessions:
            end = s.ended_at or now
            total += max(0, int((end - s.started_at).total_seconds()))
        return total

    def hourly_calculated_value(self):
        rate = Decimal(self.hourly_rate or 0)
        return (Decimal(self.elapsed_seconds()) / Decimal(3600) * rate).quantize(Decimal("0.01"))


class TimerSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)


class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    quote_date = db.Column(db.Date, default=date.today)
    valid_until = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="draft", index=True)  # draft/sent/approved/rejected
    description = db.Column(db.Text, default="")
    labor_value = db.Column(db.Numeric(12, 2), default=0)
    material_value = db.Column(db.Numeric(12, 2), default=0)
    discount = db.Column(db.Numeric(12, 2), default=0)
    total_value = db.Column(db.Numeric(12, 2), default=0)
    notes = db.Column(db.Text, default="")
    converted_service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("QuoteItem", backref="quote", cascade="all, delete-orphan", lazy=True)


class QuoteItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey("quote.id"), nullable=False, index=True)
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(20), default="service")  # service/material
    qty = db.Column(db.Numeric(12, 3), default=1)
    unit = db.Column(db.String(20), default="un")
    unit_price = db.Column(db.Numeric(12, 2), default=0)

    @property
    def subtotal(self):
        return Decimal(self.qty or 0) * Decimal(self.unit_price or 0)


class FinanceEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False, index=True)  # income/expense
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=True, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=True, index=True)
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(80), default="")
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    due_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    paid_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(20), default="pending", index=True)  # pending/paid
    payment_method = db.Column(db.String(40), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship("Client", foreign_keys=[client_id])
    service = db.relationship("Service", foreign_keys=[service_id])


class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    unit = db.Column(db.String(20), default="un")
    stock_qty = db.Column(db.Numeric(12, 3), default=0)
    min_stock = db.Column(db.Numeric(12, 3), default=0)
    unit_cost = db.Column(db.Numeric(12, 2), default=0)
    sale_price = db.Column(db.Numeric(12, 2), default=0)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    movements = db.relationship("MaterialMovement", backref="material", cascade="all, delete-orphan", lazy=True)


class MaterialMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("material.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=True)
    type = db.Column(db.String(20), nullable=False)  # in/out/adjustment
    qty = db.Column(db.Numeric(12, 3), nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), default=0)
    notes = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ServiceMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("material.id"), nullable=True)
    description = db.Column(db.String(180), nullable=False)
    qty = db.Column(db.Numeric(12, 3), default=1)
    unit = db.Column(db.String(20), default="un")
    unit_price = db.Column(db.Numeric(12, 2), default=0)
    material = db.relationship("Material")

    @property
    def subtotal(self):
        return Decimal(self.qty or 0) * Decimal(self.unit_price or 0)


# -------------------- Helpers --------------------
def money(v):
    try:
        val = Decimal(v or 0)
    except Exception:
        val = Decimal(0)
    s = f"{val:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def decimal_or_zero(v):
    if v is None or v == "":
        return Decimal("0")
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    v = str(v).strip().replace("R$", "").replace(" ", "")
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        return Decimal(v)
    except InvalidOperation:
        return Decimal("0")


def parse_date(v, default=None):
    if not v:
        return default
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        return default


def parse_time(v):
    if not v:
        return None
    try:
        return datetime.strptime(v, "%H:%M").time()
    except ValueError:
        return None


def phone_digits(phone):
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def duration_text(seconds):
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}min"
    if m:
        return f"{m}min {s:02d}s"
    return f"{s}s"


@app.template_filter("money")
def money_filter(v):
    return money(v)


@app.template_filter("datebr")
def datebr_filter(v):
    if not v:
        return "—"
    if isinstance(v, str):
        v = parse_date(v)
    return v.strftime("%d/%m/%Y") if v else "—"


@app.template_filter("timebr")
def timebr_filter(v):
    if not v:
        return ""
    return v.strftime("%H:%M")


@app.template_filter("duration")
def duration_filter(v):
    return duration_text(v)

@app.template_filter("wa")
def wa_filter(v):
    digits = phone_digits(v)
    if not digits:
        return ""
    if digits.startswith("55") and len(digits) >= 12:
        return digits
    return "55" + digits


def get_settings():
    settings = db.session.get(AppSettings, 1)
    if not settings:
        settings = AppSettings(id=1)
        db.session.add(settings)
        db.session.commit()
    return settings


@app.context_processor
def inject_globals():
    return {
        "app_settings": get_settings(),
        "today": date.today(),
        "now": datetime.now(),
        "timedelta": timedelta,
        "status_labels": {
            "scheduled": "Agendado",
            "in_progress": "Em andamento",
            "completed": "Concluído",
            "cancelled": "Cancelado",
        },
        "payment_labels": {"pending": "Pendente", "partial": "Parcial", "paid": "Pago"},
        "quote_status_labels": {"draft": "Rascunho", "sent": "Enviado", "approved": "Aprovado", "rejected": "Recusado"},
    }


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped


def sync_service_total(service):
    material_total = sum((sm.subtotal for sm in service.service_materials), Decimal("0"))
    if material_total > 0:
        service.material_value = material_total
    if service.charge_type == "hourly" and service.hourly_rate:
        service.labor_value = service.hourly_calculated_value()
    service.total_value = max(
        Decimal("0"),
        Decimal(service.labor_value or 0) + Decimal(service.material_value or 0) - Decimal(service.discount or 0),
    )
    paid = Decimal(service.amount_paid or 0)
    total = Decimal(service.total_value or 0)
    if paid <= 0:
        service.payment_status = "pending"
    elif paid >= total and total > 0:
        service.payment_status = "paid"
    else:
        service.payment_status = "partial"


def ensure_income_entry(service):
    # Keep one service-linked receivable synchronized with total / payment status.
    entry = FinanceEntry.query.filter_by(service_id=service.id, type="income").first()
    if Decimal(service.total_value or 0) <= 0:
        return
    if not entry:
        entry = FinanceEntry(
            type="income",
            client_id=service.client_id,
            service_id=service.id,
            description=f"Serviço #{service.id} - {service.title}",
            category="Serviços",
            amount=service.total_value,
            due_date=service.service_date,
            status="paid" if service.payment_status == "paid" else "pending",
            paid_date=date.today() if service.payment_status == "paid" else None,
            payment_method=service.payment_method or "",
        )
        db.session.add(entry)
    else:
        entry.client_id = service.client_id
        entry.description = f"Serviço #{service.id} - {service.title}"
        entry.amount = service.total_value
        entry.due_date = service.service_date
        entry.status = "paid" if service.payment_status == "paid" else "pending"
        entry.paid_date = date.today() if service.payment_status == "paid" else None
        entry.payment_method = service.payment_method or entry.payment_method


# -------------------- Auth / setup --------------------
@app.route("/setup", methods=["GET", "POST"])
def setup():
    if User.query.first():
        return redirect(url_for("login"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        business_name = request.form.get("business_name", "Guilherme Elétrica").strip()
        owner_name = request.form.get("owner_name", "Guilherme").strip()
        if not username or len(password) < 4:
            flash("Informe um usuário e uma senha com pelo menos 4 caracteres.", "error")
            return render_template("setup.html")
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        settings = get_settings()
        settings.business_name = business_name or "Guilherme Elétrica"
        settings.owner_name = owner_name or "Guilherme"
        db.session.commit()
        session["user_id"] = user.id
        flash("Sistema configurado. Bem-vindo!", "success")
        return redirect(url_for("dashboard"))
    return render_template("setup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if not User.query.first():
        return redirect(url_for("setup"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Usuário ou senha inválidos.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------------------- Dashboard --------------------
@app.route("/")
@login_required
def dashboard():
    today = date.today()
    month_start = today.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

    today_services = Service.query.filter(Service.service_date == today, Service.status != "cancelled").order_by(Service.service_time.asc().nullslast(), Service.id).all()
    upcoming = Service.query.filter(Service.service_date > today, Service.status.in_(["scheduled", "in_progress"])).order_by(Service.service_date, Service.service_time).limit(8).all()
    overdue_services = Service.query.filter(Service.service_date < today, Service.status.in_(["scheduled", "in_progress"])).order_by(Service.service_date).limit(8).all()

    month_income = db.session.query(func.coalesce(func.sum(FinanceEntry.amount), 0)).filter(
        FinanceEntry.type == "income", FinanceEntry.status == "paid",
        FinanceEntry.paid_date >= month_start, FinanceEntry.paid_date < next_month
    ).scalar() or 0
    month_expense = db.session.query(func.coalesce(func.sum(FinanceEntry.amount), 0)).filter(
        FinanceEntry.type == "expense", FinanceEntry.status == "paid",
        FinanceEntry.paid_date >= month_start, FinanceEntry.paid_date < next_month
    ).scalar() or 0
    receivable = db.session.query(func.coalesce(func.sum(FinanceEntry.amount), 0)).filter(
        FinanceEntry.type == "income", FinanceEntry.status == "pending"
    ).scalar() or 0
    pending_count = FinanceEntry.query.filter_by(type="income", status="pending").count()
    low_stock = Material.query.filter(Material.stock_qty <= Material.min_stock).order_by(Material.name).limit(8).all()

    return render_template(
        "dashboard.html",
        today_services=today_services,
        upcoming=upcoming,
        overdue_services=overdue_services,
        month_income=month_income,
        month_expense=month_expense,
        receivable=receivable,
        pending_count=pending_count,
        low_stock=low_stock,
    )


# -------------------- Clients --------------------
@app.route("/clients")
@login_required
def clients():
    q = request.args.get("q", "").strip()
    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Client.name.ilike(like), Client.phone.ilike(like), Client.cpf_cnpj.ilike(like), Client.city.ilike(like)))
    items = query.order_by(Client.name).all()
    return render_template("clients.html", clients=items, q=q)


@app.route("/clients/new", methods=["GET", "POST"])
@login_required
def client_new():
    if request.method == "POST":
        client = Client(
            name=request.form.get("name", "").strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            cpf_cnpj=request.form.get("cpf_cnpj", "").strip(),
            address=request.form.get("address", "").strip(),
            city=request.form.get("city", "").strip(),
            reference=request.form.get("reference", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        if not client.name:
            flash("O nome do cliente é obrigatório.", "error")
            return render_template("client_form.html", client=client)
        db.session.add(client)
        db.session.commit()
        flash("Cliente cadastrado.", "success")
        return redirect(url_for("client_detail", client_id=client.id))
    return render_template("client_form.html", client=None)


@app.route("/clients/<int:client_id>")
@login_required
def client_detail(client_id):
    client = Client.query.get_or_404(client_id)
    services = Service.query.filter_by(client_id=client.id).order_by(Service.service_date.desc()).all()
    quotes = Quote.query.filter_by(client_id=client.id).order_by(Quote.quote_date.desc()).all()
    finances = FinanceEntry.query.filter_by(client_id=client.id).order_by(FinanceEntry.due_date.desc()).all()
    total_billed = sum((Decimal(x.total_value or 0) for x in services), Decimal("0"))
    total_paid = sum((Decimal(x.amount_paid or 0) for x in services), Decimal("0"))
    return render_template("client_detail.html", client=client, services=services, quotes=quotes, finances=finances, total_billed=total_billed, total_paid=total_paid)


@app.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
def client_edit(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == "POST":
        client.name = request.form.get("name", "").strip()
        client.phone = request.form.get("phone", "").strip()
        client.email = request.form.get("email", "").strip()
        client.cpf_cnpj = request.form.get("cpf_cnpj", "").strip()
        client.address = request.form.get("address", "").strip()
        client.city = request.form.get("city", "").strip()
        client.reference = request.form.get("reference", "").strip()
        client.notes = request.form.get("notes", "").strip()
        db.session.commit()
        flash("Cliente atualizado.", "success")
        return redirect(url_for("client_detail", client_id=client.id))
    return render_template("client_form.html", client=client)


@app.route("/clients/<int:client_id>/delete", methods=["POST"])
@login_required
def client_delete(client_id):
    client = Client.query.get_or_404(client_id)
    if client.services or client.quotes:
        flash("Não é possível excluir um cliente com serviços ou orçamentos. Você pode editar os dados dele.", "error")
        return redirect(url_for("client_detail", client_id=client.id))
    FinanceEntry.query.filter_by(client_id=client.id).update({FinanceEntry.client_id: None})
    db.session.delete(client)
    db.session.commit()
    flash("Cliente excluído.", "success")
    return redirect(url_for("clients"))


# -------------------- Agenda / Services --------------------
@app.route("/agenda")
@login_required
def agenda():
    view = request.args.get("view", "week")
    base = parse_date(request.args.get("date"), date.today())
    if view == "month":
        start = base.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    elif view == "day":
        start = base
        end = base + timedelta(days=1)
    else:
        start = base - timedelta(days=base.weekday())
        end = start + timedelta(days=7)
        view = "week"
    services = Service.query.filter(Service.service_date >= start, Service.service_date < end).order_by(Service.service_date, Service.service_time.asc().nullslast(), Service.id).all()
    grouped = {}
    for s in services:
        grouped.setdefault(s.service_date, []).append(s)
    return render_template("agenda.html", services=services, grouped=grouped, start=start, end=end, base=base, view=view)


@app.route("/services")
@login_required
def services():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    query = Service.query.join(Client)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Service.title.ilike(like), Client.name.ilike(like), Service.description.ilike(like)))
    if status:
        query = query.filter(Service.status == status)
    items = query.order_by(Service.service_date.desc(), Service.id.desc()).all()
    return render_template("services.html", services=items, q=q, status=status)


@app.route("/services/new", methods=["GET", "POST"])
@login_required
def service_new():
    clients_list = Client.query.order_by(Client.name).all()
    selected_client = request.args.get("client_id", type=int)
    selected_date = parse_date(request.args.get("date"), date.today())
    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        client = Client.query.get(client_id) if client_id else None
        if not client:
            flash("Selecione um cliente.", "error")
            return render_template("service_form.html", service=None, clients=clients_list, selected_client=client_id, selected_date=selected_date)
        all_day = request.form.get("all_day") == "1"
        service = Service(
            client_id=client.id,
            title=request.form.get("title", "").strip(),
            service_date=parse_date(request.form.get("service_date"), date.today()),
            service_time=None if all_day else parse_time(request.form.get("service_time")),
            all_day=all_day,
            description=request.form.get("description", "").strip(),
            address=request.form.get("address", "").strip() or client.address,
            status=request.form.get("status", "scheduled"),
            charge_type=request.form.get("charge_type", "fixed"),
            hourly_rate=decimal_or_zero(request.form.get("hourly_rate")),
            labor_value=decimal_or_zero(request.form.get("labor_value")),
            material_value=decimal_or_zero(request.form.get("material_value")),
            discount=decimal_or_zero(request.form.get("discount")),
            amount_paid=decimal_or_zero(request.form.get("amount_paid")),
            payment_method=request.form.get("payment_method", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        if not service.title:
            flash("Informe o serviço.", "error")
            return render_template("service_form.html", service=service, clients=clients_list, selected_client=client_id, selected_date=selected_date)
        sync_service_total(service)
        db.session.add(service)
        db.session.flush()
        ensure_income_entry(service)
        db.session.commit()
        flash("Serviço agendado.", "success")
        return redirect(url_for("service_detail", service_id=service.id))
    return render_template("service_form.html", service=None, clients=clients_list, selected_client=selected_client, selected_date=selected_date)


@app.route("/services/<int:service_id>")
@login_required
def service_detail(service_id):
    service = Service.query.get_or_404(service_id)
    materials = Material.query.order_by(Material.name).all()
    elapsed = service.elapsed_seconds()
    return render_template("service_detail.html", service=service, materials=materials, elapsed=elapsed)


@app.route("/services/<int:service_id>/edit", methods=["GET", "POST"])
@login_required
def service_edit(service_id):
    service = Service.query.get_or_404(service_id)
    clients_list = Client.query.order_by(Client.name).all()
    if request.method == "POST":
        service.client_id = request.form.get("client_id", type=int)
        service.title = request.form.get("title", "").strip()
        service.service_date = parse_date(request.form.get("service_date"), service.service_date)
        service.all_day = request.form.get("all_day") == "1"
        service.service_time = None if service.all_day else parse_time(request.form.get("service_time"))
        service.description = request.form.get("description", "").strip()
        service.address = request.form.get("address", "").strip()
        service.status = request.form.get("status", service.status)
        service.charge_type = request.form.get("charge_type", service.charge_type)
        service.hourly_rate = decimal_or_zero(request.form.get("hourly_rate"))
        service.labor_value = decimal_or_zero(request.form.get("labor_value"))
        service.material_value = decimal_or_zero(request.form.get("material_value"))
        service.discount = decimal_or_zero(request.form.get("discount"))
        service.amount_paid = decimal_or_zero(request.form.get("amount_paid"))
        service.payment_method = request.form.get("payment_method", "").strip()
        service.notes = request.form.get("notes", "").strip()
        sync_service_total(service)
        ensure_income_entry(service)
        db.session.commit()
        flash("Serviço atualizado.", "success")
        return redirect(url_for("service_detail", service_id=service.id))
    return render_template("service_form.html", service=service, clients=clients_list, selected_client=service.client_id, selected_date=service.service_date)


@app.route("/services/<int:service_id>/delete", methods=["POST"])
@login_required
def service_delete(service_id):
    service = Service.query.get_or_404(service_id)
    FinanceEntry.query.filter_by(service_id=service.id).delete(synchronize_session=False)
    # Return linked inventory usage to stock.
    for sm in service.service_materials:
        if sm.material:
            sm.material.stock_qty = Decimal(sm.material.stock_qty or 0) + Decimal(sm.qty or 0)
            db.session.add(MaterialMovement(material_id=sm.material.id, service_id=None, type="in", qty=sm.qty, unit_cost=sm.material.unit_cost, notes=f"Estorno por exclusão do serviço #{service.id}"))
    db.session.delete(service)
    db.session.commit()
    flash("Serviço excluído.", "success")
    return redirect(url_for("services"))


@app.route("/services/<int:service_id>/status", methods=["POST"])
@login_required
def service_status(service_id):
    service = Service.query.get_or_404(service_id)
    status = request.form.get("status")
    if status not in {"scheduled", "in_progress", "completed", "cancelled"}:
        abort(400)
    service.status = status
    if status == "completed":
        # close any running timer
        for t in service.timer_sessions:
            if t.ended_at is None:
                t.ended_at = datetime.utcnow()
        sync_service_total(service)
        ensure_income_entry(service)
    db.session.commit()
    flash("Status atualizado.", "success")
    return redirect(request.referrer or url_for("service_detail", service_id=service.id))


@app.route("/services/<int:service_id>/timer/start", methods=["POST"])
@login_required
def timer_start(service_id):
    service = Service.query.get_or_404(service_id)
    if not service.timer_running:
        db.session.add(TimerSession(service_id=service.id, started_at=datetime.utcnow()))
        if service.status == "scheduled":
            service.status = "in_progress"
        db.session.commit()
        flash("Cronômetro iniciado.", "success")
    return redirect(url_for("service_detail", service_id=service.id))


@app.route("/services/<int:service_id>/timer/pause", methods=["POST"])
@login_required
def timer_pause(service_id):
    service = Service.query.get_or_404(service_id)
    running = TimerSession.query.filter_by(service_id=service.id, ended_at=None).order_by(TimerSession.started_at.desc()).first()
    if running:
        running.ended_at = datetime.utcnow()
        sync_service_total(service)
        ensure_income_entry(service)
        db.session.commit()
        flash("Cronômetro pausado.", "success")
    return redirect(url_for("service_detail", service_id=service.id))


@app.route("/services/<int:service_id>/timer/reset", methods=["POST"])
@login_required
def timer_reset(service_id):
    service = Service.query.get_or_404(service_id)
    TimerSession.query.filter_by(service_id=service.id).delete()
    sync_service_total(service)
    ensure_income_entry(service)
    db.session.commit()
    flash("Cronômetro zerado.", "success")
    return redirect(url_for("service_detail", service_id=service.id))


@app.route("/services/<int:service_id>/payment", methods=["POST"])
@login_required
def service_payment(service_id):
    service = Service.query.get_or_404(service_id)
    amount = decimal_or_zero(request.form.get("amount"))
    method = request.form.get("payment_method", "").strip()
    if amount <= 0:
        flash("Informe um valor recebido maior que zero.", "error")
        return redirect(url_for("service_detail", service_id=service.id))
    service.amount_paid = min(Decimal(service.total_value or 0), Decimal(service.amount_paid or 0) + amount)
    if method:
        service.payment_method = method
    sync_service_total(service)
    ensure_income_entry(service)
    db.session.commit()
    flash(f"Recebimento de {money(amount)} registrado.", "success")
    return redirect(url_for("service_detail", service_id=service.id))


@app.route("/services/<int:service_id>/materials/add", methods=["POST"])
@login_required
def service_material_add(service_id):
    service = Service.query.get_or_404(service_id)
    material_id = request.form.get("material_id", type=int)
    material = Material.query.get(material_id) if material_id else None
    qty = decimal_or_zero(request.form.get("qty"))
    if qty <= 0:
        flash("Informe uma quantidade válida.", "error")
        return redirect(url_for("service_detail", service_id=service.id))
    description = request.form.get("description", "").strip() or (material.name if material else "Material")
    unit = request.form.get("unit", "").strip() or (material.unit if material else "un")
    unit_price = decimal_or_zero(request.form.get("unit_price"))
    if material and unit_price <= 0:
        unit_price = Decimal(material.sale_price or material.unit_cost or 0)
    if material and Decimal(material.stock_qty or 0) < qty:
        flash("Estoque insuficiente. Ajuste o estoque ou use um item avulso.", "error")
        return redirect(url_for("service_detail", service_id=service.id))
    sm = ServiceMaterial(service_id=service.id, material_id=material.id if material else None, description=description, qty=qty, unit=unit, unit_price=unit_price)
    db.session.add(sm)
    if material:
        material.stock_qty = Decimal(material.stock_qty or 0) - qty
        db.session.add(MaterialMovement(material_id=material.id, service_id=service.id, type="out", qty=qty, unit_cost=material.unit_cost, notes=f"Uso no serviço #{service.id}"))
    db.session.flush()
    sync_service_total(service)
    ensure_income_entry(service)
    db.session.commit()
    flash("Material adicionado ao serviço.", "success")
    return redirect(url_for("service_detail", service_id=service.id))


@app.route("/services/<int:service_id>/materials/<int:item_id>/delete", methods=["POST"])
@login_required
def service_material_delete(service_id, item_id):
    service = Service.query.get_or_404(service_id)
    item = ServiceMaterial.query.filter_by(id=item_id, service_id=service.id).first_or_404()
    if item.material:
        item.material.stock_qty = Decimal(item.material.stock_qty or 0) + Decimal(item.qty or 0)
        db.session.add(MaterialMovement(material_id=item.material.id, service_id=service.id, type="in", qty=item.qty, unit_cost=item.material.unit_cost, notes=f"Estorno do serviço #{service.id}"))
    db.session.delete(item)
    db.session.flush()
    sync_service_total(service)
    ensure_income_entry(service)
    db.session.commit()
    flash("Material removido.", "success")
    return redirect(url_for("service_detail", service_id=service.id))


@app.route("/services/<int:service_id>/print")
@login_required
def service_print(service_id):
    service = Service.query.get_or_404(service_id)
    return render_template("service_print.html", service=service)


# API timer used by live clock
@app.route("/api/services/<int:service_id>/timer")
@login_required
def api_service_timer(service_id):
    service = Service.query.get_or_404(service_id)
    return jsonify({
        "seconds": service.elapsed_seconds(),
        "running": service.timer_running,
        "hourly_value": float(service.hourly_calculated_value()),
    })


# -------------------- Quotes --------------------
def parse_quote_items():
    descriptions = request.form.getlist("item_description[]")
    categories = request.form.getlist("item_category[]")
    qtys = request.form.getlist("item_qty[]")
    units = request.form.getlist("item_unit[]")
    prices = request.form.getlist("item_price[]")
    items = []
    for i, desc in enumerate(descriptions):
        desc = desc.strip()
        if not desc:
            continue
        qty = decimal_or_zero(qtys[i] if i < len(qtys) else 1)
        price = decimal_or_zero(prices[i] if i < len(prices) else 0)
        items.append({
            "description": desc,
            "category": categories[i] if i < len(categories) else "service",
            "qty": qty if qty > 0 else Decimal("1"),
            "unit": (units[i] if i < len(units) else "un") or "un",
            "unit_price": price,
        })
    return items


def sync_quote_totals(quote):
    labor = Decimal("0")
    material = Decimal("0")
    for item in quote.items:
        if item.category == "material":
            material += item.subtotal
        else:
            labor += item.subtotal
    quote.labor_value = labor
    quote.material_value = material
    quote.total_value = max(Decimal("0"), labor + material - Decimal(quote.discount or 0))


@app.route("/quotes")
@login_required
def quotes():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    query = Quote.query.join(Client)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Quote.title.ilike(like), Client.name.ilike(like)))
    if status:
        query = query.filter(Quote.status == status)
    items = query.order_by(Quote.quote_date.desc(), Quote.id.desc()).all()
    return render_template("quotes.html", quotes=items, q=q, status=status)


@app.route("/quotes/new", methods=["GET", "POST"])
@login_required
def quote_new():
    clients_list = Client.query.order_by(Client.name).all()
    selected_client = request.args.get("client_id", type=int)
    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        if not Client.query.get(client_id):
            flash("Selecione um cliente.", "error")
            return render_template("quote_form.html", quote=None, clients=clients_list, selected_client=client_id)
        quote = Quote(
            client_id=client_id,
            title=request.form.get("title", "").strip(),
            quote_date=parse_date(request.form.get("quote_date"), date.today()),
            valid_until=parse_date(request.form.get("valid_until")),
            status=request.form.get("status", "draft"),
            description=request.form.get("description", "").strip(),
            discount=decimal_or_zero(request.form.get("discount")),
            notes=request.form.get("notes", "").strip(),
        )
        if not quote.title:
            flash("Informe o título do orçamento.", "error")
            return render_template("quote_form.html", quote=quote, clients=clients_list, selected_client=client_id)
        db.session.add(quote)
        db.session.flush()
        for item in parse_quote_items():
            db.session.add(QuoteItem(quote_id=quote.id, **item))
        db.session.flush()
        sync_quote_totals(quote)
        db.session.commit()
        flash("Orçamento criado.", "success")
        return redirect(url_for("quote_detail", quote_id=quote.id))
    return render_template("quote_form.html", quote=None, clients=clients_list, selected_client=selected_client)


@app.route("/quotes/<int:quote_id>")
@login_required
def quote_detail(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    return render_template("quote_detail.html", quote=quote)


@app.route("/quotes/<int:quote_id>/edit", methods=["GET", "POST"])
@login_required
def quote_edit(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    clients_list = Client.query.order_by(Client.name).all()
    if request.method == "POST":
        quote.client_id = request.form.get("client_id", type=int)
        quote.title = request.form.get("title", "").strip()
        quote.quote_date = parse_date(request.form.get("quote_date"), quote.quote_date)
        quote.valid_until = parse_date(request.form.get("valid_until"))
        quote.status = request.form.get("status", quote.status)
        quote.description = request.form.get("description", "").strip()
        quote.discount = decimal_or_zero(request.form.get("discount"))
        quote.notes = request.form.get("notes", "").strip()
        QuoteItem.query.filter_by(quote_id=quote.id).delete()
        for item in parse_quote_items():
            db.session.add(QuoteItem(quote_id=quote.id, **item))
        db.session.flush()
        sync_quote_totals(quote)
        db.session.commit()
        flash("Orçamento atualizado.", "success")
        return redirect(url_for("quote_detail", quote_id=quote.id))
    return render_template("quote_form.html", quote=quote, clients=clients_list, selected_client=quote.client_id)


@app.route("/quotes/<int:quote_id>/status", methods=["POST"])
@login_required
def quote_status(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    status = request.form.get("status")
    if status not in {"draft", "sent", "approved", "rejected"}:
        abort(400)
    quote.status = status
    db.session.commit()
    flash("Status do orçamento atualizado.", "success")
    return redirect(request.referrer or url_for("quote_detail", quote_id=quote.id))


@app.route("/quotes/<int:quote_id>/convert", methods=["POST"])
@login_required
def quote_convert(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    if quote.converted_service_id:
        return redirect(url_for("service_detail", service_id=quote.converted_service_id))
    service_date = parse_date(request.form.get("service_date"), date.today())
    service = Service(
        client_id=quote.client_id,
        title=quote.title,
        service_date=service_date,
        all_day=True,
        description=quote.description,
        address=quote.client.address,
        status="scheduled",
        charge_type="fixed",
        labor_value=quote.labor_value,
        material_value=quote.material_value,
        discount=quote.discount,
        total_value=quote.total_value,
        notes=(quote.notes or "") + f"\nConvertido do orçamento #{quote.id}.",
    )
    db.session.add(service)
    db.session.flush()
    quote.status = "approved"
    quote.converted_service_id = service.id
    ensure_income_entry(service)
    db.session.commit()
    flash("Orçamento aprovado e transformado em serviço.", "success")
    return redirect(url_for("service_detail", service_id=service.id))


@app.route("/quotes/<int:quote_id>/delete", methods=["POST"])
@login_required
def quote_delete(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    db.session.delete(quote)
    db.session.commit()
    flash("Orçamento excluído.", "success")
    return redirect(url_for("quotes"))


@app.route("/quotes/<int:quote_id>/print")
@login_required
def quote_print(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    return render_template("quote_print.html", quote=quote)


# -------------------- Finance --------------------
@app.route("/finance")
@login_required
def finance():
    type_filter = request.args.get("type", "")
    status_filter = request.args.get("status", "")
    start = parse_date(request.args.get("start"), date.today().replace(day=1))
    end = parse_date(request.args.get("end"), date.today())
    query = FinanceEntry.query.filter(FinanceEntry.due_date >= start, FinanceEntry.due_date <= end)
    if type_filter:
        query = query.filter_by(type=type_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    entries = query.order_by(FinanceEntry.due_date.desc(), FinanceEntry.id.desc()).all()

    paid_income = sum((Decimal(x.amount or 0) for x in entries if x.type == "income" and x.status == "paid"), Decimal("0"))
    pending_income = sum((Decimal(x.amount or 0) for x in entries if x.type == "income" and x.status == "pending"), Decimal("0"))
    paid_expense = sum((Decimal(x.amount or 0) for x in entries if x.type == "expense" and x.status == "paid"), Decimal("0"))
    return render_template("finance.html", entries=entries, type_filter=type_filter, status_filter=status_filter, start=start, end=end, paid_income=paid_income, pending_income=pending_income, paid_expense=paid_expense)


@app.route("/finance/new", methods=["GET", "POST"])
@login_required
def finance_new():
    clients_list = Client.query.order_by(Client.name).all()
    if request.method == "POST":
        entry = FinanceEntry(
            type=request.form.get("type", "expense"),
            client_id=request.form.get("client_id", type=int),
            description=request.form.get("description", "").strip(),
            category=request.form.get("category", "").strip(),
            amount=decimal_or_zero(request.form.get("amount")),
            due_date=parse_date(request.form.get("due_date"), date.today()),
            paid_date=parse_date(request.form.get("paid_date")),
            status=request.form.get("status", "pending"),
            payment_method=request.form.get("payment_method", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        if entry.status == "paid" and not entry.paid_date:
            entry.paid_date = date.today()
        if not entry.description or entry.amount <= 0:
            flash("Preencha a descrição e um valor maior que zero.", "error")
            return render_template("finance_form.html", entry=entry, clients=clients_list)
        db.session.add(entry)
        db.session.commit()
        flash("Lançamento financeiro criado.", "success")
        return redirect(url_for("finance"))
    return render_template("finance_form.html", entry=None, clients=clients_list)


@app.route("/finance/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def finance_edit(entry_id):
    entry = FinanceEntry.query.get_or_404(entry_id)
    clients_list = Client.query.order_by(Client.name).all()
    if request.method == "POST":
        entry.type = request.form.get("type", entry.type)
        entry.client_id = request.form.get("client_id", type=int)
        entry.description = request.form.get("description", "").strip()
        entry.category = request.form.get("category", "").strip()
        entry.amount = decimal_or_zero(request.form.get("amount"))
        entry.due_date = parse_date(request.form.get("due_date"), entry.due_date)
        entry.paid_date = parse_date(request.form.get("paid_date"))
        entry.status = request.form.get("status", entry.status)
        entry.payment_method = request.form.get("payment_method", "").strip()
        entry.notes = request.form.get("notes", "").strip()
        if entry.status == "paid" and not entry.paid_date:
            entry.paid_date = date.today()
        if entry.status == "pending":
            entry.paid_date = None
        db.session.commit()
        flash("Lançamento atualizado.", "success")
        return redirect(url_for("finance"))
    return render_template("finance_form.html", entry=entry, clients=clients_list)


@app.route("/finance/<int:entry_id>/toggle", methods=["POST"])
@login_required
def finance_toggle(entry_id):
    entry = FinanceEntry.query.get_or_404(entry_id)
    if entry.status == "paid":
        entry.status = "pending"
        entry.paid_date = None
    else:
        entry.status = "paid"
        entry.paid_date = date.today()
    if entry.service_id:
        service = Service.query.get(entry.service_id)
        if service:
            if entry.status == "paid":
                service.amount_paid = service.total_value
                service.payment_status = "paid"
            elif service.payment_status == "paid":
                service.amount_paid = 0
                service.payment_status = "pending"
    db.session.commit()
    flash("Situação financeira atualizada.", "success")
    return redirect(request.referrer or url_for("finance"))


@app.route("/finance/<int:entry_id>/delete", methods=["POST"])
@login_required
def finance_delete(entry_id):
    entry = FinanceEntry.query.get_or_404(entry_id)
    if entry.service_id:
        flash("Esse lançamento veio de um serviço. Altere o serviço para manter os dados sincronizados.", "error")
        return redirect(url_for("finance"))
    db.session.delete(entry)
    db.session.commit()
    flash("Lançamento excluído.", "success")
    return redirect(url_for("finance"))


# -------------------- Materials --------------------
@app.route("/materials")
@login_required
def materials():
    q = request.args.get("q", "").strip()
    query = Material.query
    if q:
        query = query.filter(Material.name.ilike(f"%{q}%"))
    items = query.order_by(Material.name).all()
    return render_template("materials.html", materials=items, q=q)


@app.route("/materials/new", methods=["GET", "POST"])
@login_required
def material_new():
    if request.method == "POST":
        material = Material(
            name=request.form.get("name", "").strip(),
            unit=request.form.get("unit", "un").strip() or "un",
            stock_qty=decimal_or_zero(request.form.get("stock_qty")),
            min_stock=decimal_or_zero(request.form.get("min_stock")),
            unit_cost=decimal_or_zero(request.form.get("unit_cost")),
            sale_price=decimal_or_zero(request.form.get("sale_price")),
            notes=request.form.get("notes", "").strip(),
        )
        if not material.name:
            flash("Informe o material.", "error")
            return render_template("material_form.html", material=material)
        db.session.add(material)
        db.session.flush()
        if material.stock_qty:
            db.session.add(MaterialMovement(material_id=material.id, type="in", qty=material.stock_qty, unit_cost=material.unit_cost, notes="Estoque inicial"))
        db.session.commit()
        flash("Material cadastrado.", "success")
        return redirect(url_for("materials"))
    return render_template("material_form.html", material=None)


@app.route("/materials/<int:material_id>/edit", methods=["GET", "POST"])
@login_required
def material_edit(material_id):
    material = Material.query.get_or_404(material_id)
    if request.method == "POST":
        material.name = request.form.get("name", "").strip()
        material.unit = request.form.get("unit", "un").strip() or "un"
        material.min_stock = decimal_or_zero(request.form.get("min_stock"))
        material.unit_cost = decimal_or_zero(request.form.get("unit_cost"))
        material.sale_price = decimal_or_zero(request.form.get("sale_price"))
        material.notes = request.form.get("notes", "").strip()
        db.session.commit()
        flash("Material atualizado.", "success")
        return redirect(url_for("materials"))
    return render_template("material_form.html", material=material)


@app.route("/materials/<int:material_id>/movement", methods=["POST"])
@login_required
def material_movement(material_id):
    material = Material.query.get_or_404(material_id)
    typ = request.form.get("type", "in")
    qty = decimal_or_zero(request.form.get("qty"))
    if qty <= 0:
        flash("Informe uma quantidade maior que zero.", "error")
        return redirect(url_for("materials"))
    if typ == "out":
        if Decimal(material.stock_qty or 0) < qty:
            flash("Saída maior que o estoque atual.", "error")
            return redirect(url_for("materials"))
        material.stock_qty = Decimal(material.stock_qty or 0) - qty
    else:
        material.stock_qty = Decimal(material.stock_qty or 0) + qty
        typ = "in"
    db.session.add(MaterialMovement(material_id=material.id, type=typ, qty=qty, unit_cost=material.unit_cost, notes=request.form.get("notes", "").strip()))
    db.session.commit()
    flash("Movimentação registrada.", "success")
    return redirect(url_for("materials"))


@app.route("/materials/<int:material_id>/delete", methods=["POST"])
@login_required
def material_delete(material_id):
    material = Material.query.get_or_404(material_id)
    if ServiceMaterial.query.filter_by(material_id=material.id).first():
        flash("Esse material já foi usado em serviços e não pode ser excluído.", "error")
        return redirect(url_for("materials"))
    db.session.delete(material)
    db.session.commit()
    flash("Material excluído.", "success")
    return redirect(url_for("materials"))


# -------------------- Reports --------------------
@app.route("/reports")
@login_required
def reports():
    start = parse_date(request.args.get("start"), date.today().replace(day=1))
    end = parse_date(request.args.get("end"), date.today())
    services_range = Service.query.filter(Service.service_date >= start, Service.service_date <= end, Service.status != "cancelled").all()
    finances = FinanceEntry.query.filter(FinanceEntry.due_date >= start, FinanceEntry.due_date <= end).all()

    billed = sum((Decimal(s.total_value or 0) for s in services_range), Decimal("0"))
    paid_income = sum((Decimal(f.amount or 0) for f in finances if f.type == "income" and f.status == "paid"), Decimal("0"))
    expenses = sum((Decimal(f.amount or 0) for f in finances if f.type == "expense" and f.status == "paid"), Decimal("0"))
    pending = sum((Decimal(f.amount or 0) for f in finances if f.type == "income" and f.status == "pending"), Decimal("0"))
    completed = sum(1 for s in services_range if s.status == "completed")
    by_status = {k: sum(1 for s in services_range if s.status == k) for k in ["scheduled", "in_progress", "completed", "cancelled"]}

    top_clients = db.session.query(Client.name, func.sum(Service.total_value).label("total")).join(Service).filter(
        Service.service_date >= start, Service.service_date <= end, Service.status != "cancelled"
    ).group_by(Client.id).order_by(func.sum(Service.total_value).desc()).limit(10).all()

    return render_template("reports.html", start=start, end=end, billed=billed, paid_income=paid_income, expenses=expenses, pending=pending, completed=completed, by_status=by_status, top_clients=top_clients, services=services_range)


@app.route("/reports/export.csv")
@login_required
def reports_export():
    start = parse_date(request.args.get("start"), date.today().replace(day=1))
    end = parse_date(request.args.get("end"), date.today())
    items = Service.query.filter(Service.service_date >= start, Service.service_date <= end).order_by(Service.service_date).all()
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["Data", "Cliente", "Serviço", "Status", "Mão de obra", "Materiais", "Total", "Recebido", "Pagamento"])
    for s in items:
        writer.writerow([
            s.service_date.strftime("%d/%m/%Y"), s.client.name, s.title, s.status,
            str(s.labor_value or 0).replace(".", ","), str(s.material_value or 0).replace(".", ","),
            str(s.total_value or 0).replace(".", ","), str(s.amount_paid or 0).replace(".", ","), s.payment_status
        ])
    data = io.BytesIO(out.getvalue().encode("utf-8-sig"))
    return send_file(data, mimetype="text/csv", as_attachment=True, download_name=f"relatorio_{start}_{end}.csv")


# -------------------- Settings / backup --------------------
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    settings = get_settings()
    if request.method == "POST":
        settings.business_name = request.form.get("business_name", "").strip() or settings.business_name
        settings.owner_name = request.form.get("owner_name", "").strip()
        settings.phone = request.form.get("phone", "").strip()
        settings.whatsapp = request.form.get("whatsapp", "").strip()
        settings.city = request.form.get("city", "").strip()
        settings.pix_key = request.form.get("pix_key", "").strip()
        settings.hourly_rate = decimal_or_zero(request.form.get("hourly_rate"))
        settings.footer_text = request.form.get("footer_text", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.session.get(User, session["user_id"])
        if username:
            exists = User.query.filter(User.username == username, User.id != user.id).first()
            if exists:
                flash("Esse usuário já existe.", "error")
                return render_template("settings.html", settings=settings, user=user)
            user.username = username
        if password:
            if len(password) < 4:
                flash("A nova senha precisa ter pelo menos 4 caracteres.", "error")
                return render_template("settings.html", settings=settings, user=user)
            user.password_hash = generate_password_hash(password)
        db.session.commit()
        flash("Configurações salvas.", "success")
        return redirect(url_for("settings"))
    user = db.session.get(User, session["user_id"])
    return render_template("settings.html", settings=settings, user=user)


@app.route("/backup/download")
@login_required
def backup_download():
    db.session.commit()
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = os.path.join(DATA_DIR, f"backup_guilherme_eletrica_{stamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    return send_file(backup_path, as_attachment=True, download_name=os.path.basename(backup_path))


@app.route("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat() + "Z"}


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
