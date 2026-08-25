import os
import io
import csv
import shutil
import zipfile
import base64
import uuid
from datetime import datetime, date, timedelta
from functools import wraps
from decimal import Decimal, InvalidOperation

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, send_file, send_from_directory, jsonify, abort
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.getenv("DATABASE_PATH", os.path.join(DATA_DIR, "guilherme_eletrica.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_PATH
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic"}

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


class ServiceMaterialCost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_material_id = db.Column(db.Integer, db.ForeignKey("service_material.id"), nullable=False, unique=True, index=True)
    unit_cost = db.Column(db.Numeric(12, 2), default=0)
    service_material = db.relationship("ServiceMaterial", backref=db.backref("cost_snapshot", uselist=False, cascade="all, delete-orphan"))


class ServicePhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), default="before", index=True)  # before/after
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), default="")
    caption = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    service = db.relationship("Service", backref=db.backref("photos", cascade="all, delete-orphan", lazy=True))


class ServiceSignature(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False, unique=True, index=True)
    filename = db.Column(db.String(255), nullable=False)
    signer_name = db.Column(db.String(140), default="")
    signed_at = db.Column(db.DateTime, default=datetime.utcnow)
    service = db.relationship("Service", backref=db.backref("signature", uselist=False, cascade="all, delete-orphan"))


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False, index=True)
    phone = db.Column(db.String(40), default="")
    active = db.Column(db.Boolean, default=True, index=True)
    pay_type = db.Column(db.String(20), default="daily")  # daily/hourly/weekly/fixed
    rate = db.Column(db.Numeric(12, 2), default=0)
    username = db.Column(db.String(80), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship("ServiceAssignment", backref="employee", cascade="all, delete-orphan", lazy=True)
    tasks = db.relationship("EmployeeTask", backref="employee", cascade="all, delete-orphan", lazy=True)
    expenses = db.relationship("EmployeeExpense", backref="employee", cascade="all, delete-orphan", lazy=True)
    time_sessions = db.relationship("EmployeeTimeSession", backref="employee", cascade="all, delete-orphan", lazy=True)


class ServiceAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("service_id", "employee_id", name="uq_service_employee"),)
    service = db.relationship("Service")


class EmployeeTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=True, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=True, index=True)
    title = db.Column(db.String(180), nullable=False)
    task_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    task_time = db.Column(db.Time, nullable=True)
    description = db.Column(db.Text, default="")
    address = db.Column(db.String(255), default="")
    priority = db.Column(db.String(20), default="normal")  # low/normal/high
    status = db.Column(db.String(20), default="pending", index=True)  # pending/in_progress/done/cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    client = db.relationship("Client")
    service = db.relationship("Service")


class EmployeeExpense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=True, index=True)
    expense_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    category = db.Column(db.String(40), default="daily")  # daily/meal/fuel/advance/payment/other
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(20), default="paid", index=True)  # pending/paid
    notes = db.Column(db.String(255), default="")
    finance_entry_id = db.Column(db.Integer, db.ForeignKey("finance_entry.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    service = db.relationship("Service")
    finance_entry = db.relationship("FinanceEntry", foreign_keys=[finance_entry_id])


class EmployeeTimeSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=True, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("employee_task.id"), nullable=True, index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    service = db.relationship("Service")
    task = db.relationship("EmployeeTask")


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


def allowed_image(filename):
    return "." in (filename or "") and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_uploaded_image(file_storage, prefix):
    if not file_storage or not file_storage.filename or not allowed_image(file_storage.filename):
        return None
    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[1].lower()
    name = f"{prefix}_{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_DIR, name))
    return name, original


def delete_upload(filename):
    if not filename:
        return
    path = os.path.join(UPLOAD_DIR, os.path.basename(filename))
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def service_material_cost_total(service):
    total = Decimal("0")
    for item in service.service_materials:
        if item.cost_snapshot:
            unit_cost = Decimal(item.cost_snapshot.unit_cost or 0)
        elif item.material:
            unit_cost = Decimal(item.material.unit_cost or 0)
        else:
            unit_cost = Decimal("0")
        total += Decimal(item.qty or 0) * unit_cost
    return total


def service_expense_total(service_id):
    return Decimal(db.session.query(func.coalesce(func.sum(FinanceEntry.amount), 0)).filter(
        FinanceEntry.service_id == service_id, FinanceEntry.type == "expense"
    ).scalar() or 0)


def service_profit(service):
    material_cost = service_material_cost_total(service)
    linked_expenses = service_expense_total(service.id)
    total_cost = material_cost + linked_expenses
    profit = Decimal(service.total_value or 0) - total_cost
    return material_cost, linked_expenses, total_cost, profit


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


def current_employee():
    employee_id = session.get("employee_id")
    return db.session.get(Employee, employee_id) if employee_id else None


def is_employee_session():
    return bool(session.get("employee_id"))


@app.context_processor
def inject_globals():
    return {
        "app_settings": get_settings(),
        "today": date.today(),
        "now": datetime.now(),
        "timedelta": timedelta,
        "current_employee": current_employee(),
        "is_employee": is_employee_session(),
        "status_labels": {
            "scheduled": "Agendado",
            "in_progress": "Em andamento",
            "completed": "Concluído",
            "cancelled": "Cancelado",
        },
        "task_status_labels": {"pending": "Pendente", "in_progress": "Em andamento", "done": "Concluída", "cancelled": "Cancelada"},
        "priority_labels": {"low": "Baixa", "normal": "Normal", "high": "Alta"},
        "pay_type_labels": {"daily": "Diária", "hourly": "Por hora", "weekly": "Semanal", "fixed": "Valor fixo"},
        "employee_expense_labels": {"daily": "Diária", "meal": "Alimentação", "fuel": "Combustível", "advance": "Adiantamento", "payment": "Pagamento", "other": "Outro"},
        "payment_labels": {"pending": "Pendente", "partial": "Parcial", "paid": "Pago"},
        "quote_status_labels": {"draft": "Rascunho", "sent": "Enviado", "approved": "Aprovado", "rejected": "Recusado"},
    }


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("user_id") and not session.get("employee_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if session.get("employee_id"):
                return redirect(url_for("helper_dashboard"))
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped


@app.before_request
def restrict_employee_access():
    if not session.get("employee_id"):
        return None
    endpoint = request.endpoint or ""
    allowed = {"static", "login", "logout", "health"}
    if endpoint in allowed or endpoint.startswith("helper_"):
        return None
    return redirect(url_for("helper_dashboard"))


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
        session.clear()
        session["user_id"] = user.id
        session["role"] = "admin"
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
            session.clear()
            session["user_id"] = user.id
            session["role"] = "admin"
            return redirect(request.args.get("next") or url_for("dashboard"))
        employee = Employee.query.filter_by(username=username, active=True).first()
        if employee and employee.password_hash and check_password_hash(employee.password_hash, password):
            session.clear()
            session["employee_id"] = employee.id
            session["role"] = "employee"
            return redirect(url_for("helper_dashboard"))
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
    team_pending_tasks = EmployeeTask.query.join(Employee).filter(Employee.active.is_(True), EmployeeTask.status.in_(["pending", "in_progress"]), EmployeeTask.task_date <= today).count()
    helper_pending_amount = db.session.query(func.coalesce(func.sum(EmployeeExpense.amount), 0)).join(Employee).filter(Employee.active.is_(True), EmployeeExpense.status == "pending").scalar() or 0

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
        team_pending_tasks=team_pending_tasks,
        helper_pending_amount=helper_pending_amount,
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
@admin_required
def client_delete(client_id):
    client = Client.query.get_or_404(client_id)
    if client.services or client.quotes:
        flash("Esse cliente possui serviços ou orçamentos. Exclua primeiro esses registros para evitar apagar o histórico por engano.", "error")
        return redirect(url_for("client_detail", client_id=client.id))
    FinanceEntry.query.filter_by(client_id=client.id).update({FinanceEntry.client_id: None}, synchronize_session=False)
    EmployeeTask.query.filter_by(client_id=client.id).update({EmployeeTask.client_id: None}, synchronize_session=False)
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
    employees_list = Employee.query.filter_by(active=True).order_by(Employee.name).all()
    selected_client = request.args.get("client_id", type=int)
    selected_date = parse_date(request.args.get("date"), date.today())
    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        client = Client.query.get(client_id) if client_id else None
        if not client:
            flash("Selecione um cliente.", "error")
            return render_template("service_form.html", service=None, clients=clients_list, employees=employees_list, selected_client=client_id, selected_date=selected_date, assigned_employee_id=request.form.get("employee_id", type=int))
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
            return render_template("service_form.html", service=service, clients=clients_list, employees=employees_list, selected_client=client_id, selected_date=selected_date, assigned_employee_id=request.form.get("employee_id", type=int))
        sync_service_total(service)
        db.session.add(service)
        db.session.flush()
        ensure_income_entry(service)
        employee_id = request.form.get("employee_id", type=int)
        employee = db.session.get(Employee, employee_id) if employee_id else None
        if employee and employee.active:
            db.session.add(ServiceAssignment(service_id=service.id, employee_id=employee.id))
        db.session.commit()
        flash("Serviço agendado.", "success")
        return redirect(url_for("service_detail", service_id=service.id))
    return render_template("service_form.html", service=None, clients=clients_list, employees=employees_list, selected_client=selected_client, selected_date=selected_date, assigned_employee_id=None)


@app.route("/services/<int:service_id>")
@login_required
def service_detail(service_id):
    service = Service.query.get_or_404(service_id)
    materials = Material.query.order_by(Material.name).all()
    elapsed = service.elapsed_seconds()
    assignments = ServiceAssignment.query.filter_by(service_id=service.id).all()
    helper_expenses = EmployeeExpense.query.filter_by(service_id=service.id).order_by(EmployeeExpense.expense_date.desc()).all()
    helper_cost = sum((Decimal(x.amount or 0) for x in helper_expenses), Decimal("0"))
    material_cost, linked_expenses, total_cost, profit = service_profit(service)
    other_expenses = FinanceEntry.query.filter(
        FinanceEntry.service_id == service.id,
        FinanceEntry.type == "expense",
        FinanceEntry.category != "Equipe / Ajudante"
    ).order_by(FinanceEntry.due_date.desc(), FinanceEntry.id.desc()).all()
    before_photos = ServicePhoto.query.filter_by(service_id=service.id, kind="before").order_by(ServicePhoto.created_at.desc()).all()
    after_photos = ServicePhoto.query.filter_by(service_id=service.id, kind="after").order_by(ServicePhoto.created_at.desc()).all()
    return render_template(
        "service_detail.html", service=service, materials=materials, elapsed=elapsed,
        assignments=assignments, helper_expenses=helper_expenses, helper_cost=helper_cost,
        material_cost=material_cost, linked_expenses=linked_expenses, total_cost=total_cost, profit=profit,
        other_expenses=other_expenses, before_photos=before_photos, after_photos=after_photos
    )


@app.route("/services/<int:service_id>/edit", methods=["GET", "POST"])
@login_required
def service_edit(service_id):
    service = Service.query.get_or_404(service_id)
    clients_list = Client.query.order_by(Client.name).all()
    employees_list = Employee.query.filter_by(active=True).order_by(Employee.name).all()
    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        client = db.session.get(Client, client_id) if client_id else None
        if not client:
            flash("Selecione um cliente.", "error")
            assignment = ServiceAssignment.query.filter_by(service_id=service.id).first()
            return render_template("service_form.html", service=service, clients=clients_list, employees=employees_list, selected_client=None, selected_date=service.service_date, assigned_employee_id=assignment.employee_id if assignment else None)
        service.client_id = client.id
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
        ServiceAssignment.query.filter_by(service_id=service.id).delete(synchronize_session=False)
        employee_id = request.form.get("employee_id", type=int)
        employee = db.session.get(Employee, employee_id) if employee_id else None
        if employee and employee.active:
            db.session.add(ServiceAssignment(service_id=service.id, employee_id=employee.id))
        db.session.commit()
        flash("Serviço atualizado.", "success")
        return redirect(url_for("service_detail", service_id=service.id))
    assignment = ServiceAssignment.query.filter_by(service_id=service.id).first()
    return render_template("service_form.html", service=service, clients=clients_list, employees=employees_list, selected_client=service.client_id, selected_date=service.service_date, assigned_employee_id=assignment.employee_id if assignment else None)


@app.route("/services/<int:service_id>/delete", methods=["POST"])
@admin_required
def service_delete(service_id):
    service = Service.query.get_or_404(service_id)
    FinanceEntry.query.filter_by(service_id=service.id, type="income").delete(synchronize_session=False)
    FinanceEntry.query.filter_by(service_id=service.id, type="expense").update({FinanceEntry.service_id: None}, synchronize_session=False)
    EmployeeExpense.query.filter_by(service_id=service.id).update({EmployeeExpense.service_id: None}, synchronize_session=False)
    EmployeeTask.query.filter_by(service_id=service.id).update({EmployeeTask.service_id: None}, synchronize_session=False)
    EmployeeTimeSession.query.filter_by(service_id=service.id).delete(synchronize_session=False)
    ServiceAssignment.query.filter_by(service_id=service.id).delete(synchronize_session=False)
    # Remove uploaded photos/signature from disk.
    for photo in list(service.photos):
        delete_upload(photo.filename)
    if service.signature:
        delete_upload(service.signature.filename)
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
    unit_cost = decimal_or_zero(request.form.get("unit_cost"))
    if material and unit_cost <= 0:
        unit_cost = Decimal(material.unit_cost or 0)
    sm = ServiceMaterial(service_id=service.id, material_id=material.id if material else None, description=description, qty=qty, unit=unit, unit_price=unit_price)
    db.session.add(sm)
    db.session.flush()
    db.session.add(ServiceMaterialCost(service_material_id=sm.id, unit_cost=unit_cost))
    if material:
        material.stock_qty = Decimal(material.stock_qty or 0) - qty
        db.session.add(MaterialMovement(material_id=material.id, service_id=service.id, type="out", qty=qty, unit_cost=material.unit_cost, notes=f"Uso no serviço #{service.id}"))
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


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_media(filename):
    return send_from_directory(UPLOAD_DIR, os.path.basename(filename))


@app.route("/services/<int:service_id>/photos/add", methods=["POST"])
@login_required
def service_photo_add(service_id):
    service = Service.query.get_or_404(service_id)
    kind = request.form.get("kind", "before")
    if kind not in {"before", "after"}:
        kind = "before"
    files = request.files.getlist("photos")
    saved = 0
    for file_storage in files:
        result = save_uploaded_image(file_storage, f"service_{service.id}_{kind}")
        if not result:
            continue
        filename, original = result
        db.session.add(ServicePhoto(
            service_id=service.id, kind=kind, filename=filename, original_name=original,
            caption=request.form.get("caption", "").strip()
        ))
        saved += 1
    if saved:
        db.session.commit()
        flash(f"{saved} foto(s) adicionada(s).", "success")
    else:
        flash("Escolha uma foto JPG, PNG, WEBP ou HEIC.", "error")
    return redirect(url_for("service_detail", service_id=service.id) + "#fotos")


@app.route("/services/<int:service_id>/photos/<int:photo_id>/delete", methods=["POST"])
@admin_required
def service_photo_delete(service_id, photo_id):
    service = Service.query.get_or_404(service_id)
    photo = ServicePhoto.query.filter_by(id=photo_id, service_id=service.id).first_or_404()
    delete_upload(photo.filename)
    db.session.delete(photo)
    db.session.commit()
    flash("Foto removida.", "success")
    return redirect(url_for("service_detail", service_id=service.id) + "#fotos")


@app.route("/services/<int:service_id>/signature/save", methods=["POST"])
@login_required
def service_signature_save(service_id):
    service = Service.query.get_or_404(service_id)
    data_url = request.form.get("signature_data", "")
    signer_name = request.form.get("signer_name", "").strip() or service.client.name
    if not data_url.startswith("data:image/png;base64,"):
        flash("Faça a assinatura antes de salvar.", "error")
        return redirect(url_for("service_detail", service_id=service.id) + "#assinatura")
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
    except Exception:
        flash("Não foi possível salvar a assinatura.", "error")
        return redirect(url_for("service_detail", service_id=service.id) + "#assinatura")
    if len(raw) < 100:
        flash("A assinatura parece estar vazia.", "error")
        return redirect(url_for("service_detail", service_id=service.id) + "#assinatura")
    existing = ServiceSignature.query.filter_by(service_id=service.id).first()
    if existing:
        delete_upload(existing.filename)
        signature = existing
    else:
        signature = ServiceSignature(service_id=service.id)
        db.session.add(signature)
    filename = f"service_{service.id}_signature_{uuid.uuid4().hex}.png"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(raw)
    signature.filename = filename
    signature.signer_name = signer_name
    signature.signed_at = datetime.utcnow()
    db.session.commit()
    flash("Assinatura do cliente salva.", "success")
    return redirect(url_for("service_detail", service_id=service.id) + "#assinatura")


@app.route("/services/<int:service_id>/signature/delete", methods=["POST"])
@admin_required
def service_signature_delete(service_id):
    service = Service.query.get_or_404(service_id)
    signature = ServiceSignature.query.filter_by(service_id=service.id).first()
    if signature:
        delete_upload(signature.filename)
        db.session.delete(signature)
        db.session.commit()
        flash("Assinatura removida.", "success")
    return redirect(url_for("service_detail", service_id=service.id) + "#assinatura")


@app.route("/services/<int:service_id>/costs/add", methods=["POST"])
@admin_required
def service_cost_add(service_id):
    service = Service.query.get_or_404(service_id)
    amount = decimal_or_zero(request.form.get("amount"))
    if amount <= 0:
        flash("Informe um custo maior que zero.", "error")
        return redirect(url_for("service_detail", service_id=service.id) + "#lucro")
    category_name = request.form.get("cost_category", "Outro").strip() or "Outro"
    description = request.form.get("description", "").strip() or category_name
    status = request.form.get("status", "paid")
    cost_date = parse_date(request.form.get("cost_date"), date.today())
    entry = FinanceEntry(
        type="expense", service_id=service.id, client_id=service.client_id,
        description=f"Custo serviço #{service.id} - {description}",
        category=f"Custo do serviço / {category_name}", amount=amount, due_date=cost_date,
        status="paid" if status == "paid" else "pending",
        paid_date=cost_date if status == "paid" else None,
        payment_method=request.form.get("payment_method", "").strip(),
        notes=request.form.get("notes", "").strip()
    )
    db.session.add(entry)
    db.session.commit()
    flash("Custo lançado no serviço e no financeiro.", "success")
    return redirect(url_for("service_detail", service_id=service.id) + "#lucro")


@app.route("/services/<int:service_id>/costs/<int:entry_id>/delete", methods=["POST"])
@admin_required
def service_cost_delete(service_id, entry_id):
    service = Service.query.get_or_404(service_id)
    entry = FinanceEntry.query.filter_by(id=entry_id, service_id=service.id, type="expense").first_or_404()
    if EmployeeExpense.query.filter_by(finance_entry_id=entry.id).first():
        flash("Esse custo pertence ao ajudante. Exclua pela área da equipe.", "error")
        return redirect(url_for("service_detail", service_id=service.id) + "#lucro")
    db.session.delete(entry)
    db.session.commit()
    flash("Custo removido do serviço e do financeiro.", "success")
    return redirect(url_for("service_detail", service_id=service.id) + "#lucro")


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
        client_id = request.form.get("client_id", type=int)
        client = db.session.get(Client, client_id) if client_id else None
        if not client:
            flash("Selecione um cliente.", "error")
            return render_template("quote_form.html", quote=quote, clients=clients_list, selected_client=None)
        quote.client_id = client_id
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
@admin_required
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
    team_expense = EmployeeExpense.query.filter_by(finance_entry_id=entry.id).first()
    if team_expense:
        flash("Esse lançamento pertence ao controle da equipe. Edite pelo cadastro do ajudante para manter tudo sincronizado.", "error")
        return redirect(url_for("employee_detail", employee_id=team_expense.employee_id))
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
    if entry.type == "income" and entry.service_id:
        service = Service.query.get(entry.service_id)
        if service:
            if entry.status == "paid":
                service.amount_paid = service.total_value
                service.payment_status = "paid"
            elif service.payment_status == "paid":
                service.amount_paid = 0
                service.payment_status = "pending"
    team_expense = EmployeeExpense.query.filter_by(finance_entry_id=entry.id).first()
    if team_expense:
        team_expense.status = entry.status
    db.session.commit()
    flash("Situação financeira atualizada.", "success")
    return redirect(request.referrer or url_for("finance"))


@app.route("/finance/<int:entry_id>/delete", methods=["POST"])
@admin_required
def finance_delete(entry_id):
    entry = FinanceEntry.query.get_or_404(entry_id)
    team_expense = EmployeeExpense.query.filter_by(finance_entry_id=entry.id).first()
    if team_expense:
        flash("Esse lançamento pertence ao controle da equipe. Exclua pelo cadastro do ajudante.", "error")
        return redirect(url_for("employee_detail", employee_id=team_expense.employee_id))
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
@admin_required
def material_delete(material_id):
    material = Material.query.get_or_404(material_id)
    if ServiceMaterial.query.filter_by(material_id=material.id).first():
        flash("Esse material já foi usado em serviços e não pode ser excluído.", "error")
        return redirect(url_for("materials"))
    db.session.delete(material)
    db.session.commit()
    flash("Material excluído.", "success")
    return redirect(url_for("materials"))


# -------------------- Equipe / ajudantes --------------------
def employee_elapsed_seconds(employee_id, start=None, end=None):
    query = EmployeeTimeSession.query.filter_by(employee_id=employee_id)
    if start:
        query = query.filter(EmployeeTimeSession.started_at >= datetime.combine(start, datetime.min.time()))
    if end:
        query = query.filter(EmployeeTimeSession.started_at < datetime.combine(end + timedelta(days=1), datetime.min.time()))
    total = 0
    now_utc = datetime.utcnow()
    for item in query.all():
        finish = item.ended_at or now_utc
        total += max(0, int((finish - item.started_at).total_seconds()))
    return total


def employee_running_session(employee_id, task_id=None, service_id=None):
    query = EmployeeTimeSession.query.filter_by(employee_id=employee_id, ended_at=None)
    if task_id is not None:
        query = query.filter_by(task_id=task_id)
    if service_id is not None:
        query = query.filter_by(service_id=service_id)
    return query.order_by(EmployeeTimeSession.started_at.desc()).first()


def sync_employee_expense_finance(expense):
    description = f"Equipe - {expense.employee.name}: {dict(daily='Diária', meal='Alimentação', fuel='Combustível', advance='Adiantamento', payment='Pagamento', other='Outro').get(expense.category, expense.category)}"
    if expense.notes:
        description += f" - {expense.notes}"
    entry = db.session.get(FinanceEntry, expense.finance_entry_id) if expense.finance_entry_id else None
    if not entry:
        entry = FinanceEntry(type="expense", service_id=expense.service_id, description=description, category="Equipe / Ajudante", amount=expense.amount, due_date=expense.expense_date, status=expense.status)
        db.session.add(entry)
        db.session.flush()
        expense.finance_entry_id = entry.id
    entry.service_id = expense.service_id
    entry.description = description
    entry.category = "Equipe / Ajudante"
    entry.amount = expense.amount
    entry.due_date = expense.expense_date
    entry.status = expense.status
    entry.paid_date = expense.expense_date if expense.status == "paid" else None


@app.route("/team")
@admin_required
def team():
    employees = Employee.query.order_by(Employee.active.desc(), Employee.name).all()
    month_start = date.today().replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    cards = []
    for employee in employees:
        pending_tasks = EmployeeTask.query.filter(EmployeeTask.employee_id == employee.id, EmployeeTask.status.in_(["pending", "in_progress"])).count()
        month_expenses = db.session.query(func.coalesce(func.sum(EmployeeExpense.amount), 0)).filter(EmployeeExpense.employee_id == employee.id, EmployeeExpense.expense_date >= month_start, EmployeeExpense.expense_date < next_month).scalar() or 0
        pending_pay = db.session.query(func.coalesce(func.sum(EmployeeExpense.amount), 0)).filter(EmployeeExpense.employee_id == employee.id, EmployeeExpense.status == "pending").scalar() or 0
        cards.append({"employee": employee, "pending_tasks": pending_tasks, "month_expenses": month_expenses, "pending_pay": pending_pay, "seconds": employee_elapsed_seconds(employee.id, month_start, date.today())})
    return render_template("team.html", cards=cards)


@app.route("/team/new", methods=["GET", "POST"])
@admin_required
def employee_new():
    if request.method == "POST":
        employee = Employee(name=request.form.get("name", "").strip(), phone=request.form.get("phone", "").strip(), pay_type=request.form.get("pay_type", "daily"), rate=decimal_or_zero(request.form.get("rate")), notes=request.form.get("notes", "").strip(), active=True)
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not employee.name:
            flash("Informe o nome do ajudante.", "error")
            return render_template("employee_form.html", employee=employee)
        if username:
            if User.query.filter_by(username=username).first() or Employee.query.filter_by(username=username).first():
                flash("Esse usuário já está em uso.", "error")
                return render_template("employee_form.html", employee=employee)
            if len(password) < 4:
                flash("Para liberar o acesso do ajudante, informe uma senha com pelo menos 4 caracteres.", "error")
                return render_template("employee_form.html", employee=employee)
            employee.username = username
            employee.password_hash = generate_password_hash(password)
        db.session.add(employee)
        db.session.commit()
        flash("Ajudante cadastrado.", "success")
        return redirect(url_for("employee_detail", employee_id=employee.id))
    return render_template("employee_form.html", employee=None)


@app.route("/team/<int:employee_id>")
@admin_required
def employee_detail(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    start = parse_date(request.args.get("start"), date.today().replace(day=1))
    end = parse_date(request.args.get("end"), date.today())
    tasks = EmployeeTask.query.filter_by(employee_id=employee.id).order_by(EmployeeTask.task_date.desc(), EmployeeTask.id.desc()).limit(50).all()
    assignments = ServiceAssignment.query.filter_by(employee_id=employee.id).join(Service, Service.id == ServiceAssignment.service_id).order_by(Service.service_date.desc()).limit(30).all()
    expenses = EmployeeExpense.query.filter(EmployeeExpense.employee_id == employee.id, EmployeeExpense.expense_date >= start, EmployeeExpense.expense_date <= end).order_by(EmployeeExpense.expense_date.desc(), EmployeeExpense.id.desc()).all()
    total_expenses = sum((Decimal(x.amount or 0) for x in expenses), Decimal("0"))
    paid_expenses = sum((Decimal(x.amount or 0) for x in expenses if x.status == "paid"), Decimal("0"))
    pending_expenses = sum((Decimal(x.amount or 0) for x in expenses if x.status == "pending"), Decimal("0"))
    elapsed = employee_elapsed_seconds(employee.id, start, end)
    return render_template("employee_detail.html", employee=employee, tasks=tasks, assignments=assignments, expenses=expenses, total_expenses=total_expenses, paid_expenses=paid_expenses, pending_expenses=pending_expenses, elapsed=elapsed, start=start, end=end, services=Service.query.order_by(Service.service_date.desc()).limit(80).all(), clients=Client.query.order_by(Client.name).all())


@app.route("/team/<int:employee_id>/edit", methods=["GET", "POST"])
@admin_required
def employee_edit(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    if request.method == "POST":
        employee.name = request.form.get("name", "").strip()
        employee.phone = request.form.get("phone", "").strip()
        employee.pay_type = request.form.get("pay_type", "daily")
        employee.rate = decimal_or_zero(request.form.get("rate"))
        employee.notes = request.form.get("notes", "").strip()
        employee.active = request.form.get("active") == "1"
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username != (employee.username or ""):
            if username and (User.query.filter_by(username=username).first() or Employee.query.filter(Employee.username == username, Employee.id != employee.id).first()):
                flash("Esse usuário já está em uso.", "error")
                return render_template("employee_form.html", employee=employee)
            employee.username = username or None
            if not username:
                employee.password_hash = ""
        if password:
            if len(password) < 4:
                flash("A senha precisa ter pelo menos 4 caracteres.", "error")
                return render_template("employee_form.html", employee=employee)
            employee.password_hash = generate_password_hash(password)
        db.session.commit()
        flash("Cadastro da equipe atualizado.", "success")
        return redirect(url_for("employee_detail", employee_id=employee.id))
    return render_template("employee_form.html", employee=employee)


@app.route("/team/<int:employee_id>/delete", methods=["POST"])
@admin_required
def employee_delete(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    # Gastos da equipe geram lançamentos financeiros próprios. Ao excluir um
    # cadastro feito por engano, removemos também somente esses lançamentos.
    finance_ids = [x.finance_entry_id for x in employee.expenses if x.finance_entry_id]
    if finance_ids:
        FinanceEntry.query.filter(FinanceEntry.id.in_(finance_ids)).delete(synchronize_session=False)
    db.session.delete(employee)
    db.session.commit()
    flash("Ajudante e os registros vinculados a ele foram excluídos.", "success")
    return redirect(url_for("team"))


@app.route("/team/tasks/new", methods=["GET", "POST"])
@admin_required
def team_task_new():
    employee_id = request.args.get("employee_id", type=int) or request.form.get("employee_id", type=int)
    service_id = request.args.get("service_id", type=int) or request.form.get("service_id", type=int)
    selected_service = db.session.get(Service, service_id) if service_id else None
    if request.method == "POST":
        employee = db.session.get(Employee, employee_id) if employee_id else None
        if not employee:
            flash("Selecione o ajudante.", "error")
        else:
            client_id = request.form.get("client_id", type=int) or (selected_service.client_id if selected_service else None)
            client = db.session.get(Client, client_id) if client_id else None
            task = EmployeeTask(employee_id=employee.id, client_id=client_id, service_id=service_id, title=request.form.get("title", "").strip(), task_date=parse_date(request.form.get("task_date"), date.today()), task_time=parse_time(request.form.get("task_time")), description=request.form.get("description", "").strip(), address=request.form.get("address", "").strip() or (selected_service.address if selected_service else (client.address if client else "")), priority=request.form.get("priority", "normal"), status="pending")
            if task.title:
                db.session.add(task)
                db.session.commit()
                flash("Tarefa enviada para o ajudante.", "success")
                return redirect(url_for("employee_detail", employee_id=employee.id))
            flash("Informe a tarefa.", "error")
    return render_template("task_form.html", employees=Employee.query.filter_by(active=True).order_by(Employee.name).all(), clients=Client.query.order_by(Client.name).all(), services=Service.query.order_by(Service.service_date.desc()).limit(100).all(), employee_id=employee_id, service_id=service_id, selected_service=selected_service)


@app.route("/team/tasks/<int:task_id>/status", methods=["POST"])
@admin_required
def team_task_status(task_id):
    task = EmployeeTask.query.get_or_404(task_id)
    status = request.form.get("status", "pending")
    if status not in {"pending", "in_progress", "done", "cancelled"}:
        abort(400)
    task.status = status
    task.completed_at = datetime.utcnow() if status == "done" else None
    if status in {"done", "cancelled"}:
        for running in EmployeeTimeSession.query.filter_by(task_id=task.id, ended_at=None).all():
            running.ended_at = datetime.utcnow()
    db.session.commit()
    flash("Tarefa atualizada.", "success")
    return redirect(request.referrer or url_for("employee_detail", employee_id=task.employee_id))


@app.route("/team/tasks/<int:task_id>/delete", methods=["POST"])
@admin_required
def team_task_delete(task_id):
    task = EmployeeTask.query.get_or_404(task_id)
    employee_id = task.employee_id
    EmployeeTimeSession.query.filter_by(task_id=task.id).delete(synchronize_session=False)
    db.session.delete(task)
    db.session.commit()
    flash("Tarefa excluída.", "success")
    return redirect(url_for("employee_detail", employee_id=employee_id))


@app.route("/team/<int:employee_id>/expenses/new", methods=["POST"])
@admin_required
def employee_expense_new(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    amount = decimal_or_zero(request.form.get("amount"))
    if amount <= 0:
        flash("Informe um valor maior que zero.", "error")
        return redirect(url_for("employee_detail", employee_id=employee.id))
    expense = EmployeeExpense(employee_id=employee.id, service_id=request.form.get("service_id", type=int), expense_date=parse_date(request.form.get("expense_date"), date.today()), category=request.form.get("category", "daily"), amount=amount, status=request.form.get("status", "paid"), notes=request.form.get("notes", "").strip())
    db.session.add(expense)
    db.session.flush()
    sync_employee_expense_finance(expense)
    db.session.commit()
    flash("Gasto da equipe lançado no financeiro.", "success")
    return redirect(url_for("employee_detail", employee_id=employee.id))


@app.route("/team/expenses/<int:expense_id>/toggle", methods=["POST"])
@admin_required
def employee_expense_toggle(expense_id):
    expense = EmployeeExpense.query.get_or_404(expense_id)
    expense.status = "paid" if expense.status == "pending" else "pending"
    sync_employee_expense_finance(expense)
    db.session.commit()
    flash("Situação do gasto atualizada.", "success")
    return redirect(request.referrer or url_for("employee_detail", employee_id=expense.employee_id))


@app.route("/team/expenses/<int:expense_id>/delete", methods=["POST"])
@admin_required
def employee_expense_delete(expense_id):
    expense = EmployeeExpense.query.get_or_404(expense_id)
    employee_id = expense.employee_id
    if expense.finance_entry_id:
        entry = db.session.get(FinanceEntry, expense.finance_entry_id)
        if entry:
            db.session.delete(entry)
    db.session.delete(expense)
    db.session.commit()
    flash("Gasto excluído do controle da equipe e do financeiro.", "success")
    return redirect(url_for("employee_detail", employee_id=employee_id))


# -------------------- Área do ajudante --------------------
@app.route("/me")
@login_required
def helper_dashboard():
    employee = current_employee()
    if not employee:
        return redirect(url_for("dashboard"))
    today_ = date.today()
    tasks = EmployeeTask.query.filter(EmployeeTask.employee_id == employee.id, EmployeeTask.status != "cancelled", EmployeeTask.task_date <= today_ + timedelta(days=7)).order_by(EmployeeTask.task_date, EmployeeTask.task_time.asc().nullslast(), EmployeeTask.id).all()
    assignments = ServiceAssignment.query.filter_by(employee_id=employee.id).join(Service, Service.id == ServiceAssignment.service_id).filter(Service.status != "cancelled", Service.service_date >= today_ - timedelta(days=1), Service.service_date <= today_ + timedelta(days=14)).order_by(Service.service_date, Service.service_time.asc().nullslast()).all()
    running = EmployeeTimeSession.query.filter_by(employee_id=employee.id, ended_at=None).order_by(EmployeeTimeSession.started_at.desc()).first()
    today_seconds = employee_elapsed_seconds(employee.id, today_, today_)
    return render_template("helper_dashboard.html", employee=employee, tasks=tasks, assignments=assignments, running=running, today_seconds=today_seconds)


@app.route("/me/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def helper_task_status(task_id):
    employee = current_employee()
    task = EmployeeTask.query.filter_by(id=task_id, employee_id=employee.id if employee else -1).first_or_404()
    status = request.form.get("status", "pending")
    if status not in {"pending", "in_progress", "done"}:
        abort(400)
    task.status = status
    task.completed_at = datetime.utcnow() if status == "done" else None
    if status == "done":
        for running in EmployeeTimeSession.query.filter_by(employee_id=employee.id, task_id=task.id, ended_at=None).all():
            running.ended_at = datetime.utcnow()
    db.session.commit()
    flash("Tarefa atualizada.", "success")
    return redirect(url_for("helper_dashboard"))


@app.route("/me/tasks/<int:task_id>/timer/start", methods=["POST"])
@login_required
def helper_task_timer_start(task_id):
    employee = current_employee()
    task = EmployeeTask.query.filter_by(id=task_id, employee_id=employee.id if employee else -1).first_or_404()
    for running in EmployeeTimeSession.query.filter_by(employee_id=employee.id, ended_at=None).all():
        running.ended_at = datetime.utcnow()
    db.session.add(EmployeeTimeSession(employee_id=employee.id, task_id=task.id, service_id=task.service_id, started_at=datetime.utcnow()))
    task.status = "in_progress"
    db.session.commit()
    flash("Seu cronômetro foi iniciado.", "success")
    return redirect(url_for("helper_dashboard"))


@app.route("/me/tasks/<int:task_id>/timer/pause", methods=["POST"])
@login_required
def helper_task_timer_pause(task_id):
    employee = current_employee()
    task = EmployeeTask.query.filter_by(id=task_id, employee_id=employee.id if employee else -1).first_or_404()
    running = employee_running_session(employee.id, task_id=task.id)
    if running:
        running.ended_at = datetime.utcnow()
        db.session.commit()
        flash("Cronômetro pausado.", "success")
    return redirect(url_for("helper_dashboard"))


@app.route("/me/services/<int:service_id>")
@login_required
def helper_service(service_id):
    employee = current_employee()
    assignment = ServiceAssignment.query.filter_by(service_id=service_id, employee_id=employee.id if employee else -1).first_or_404()
    service = assignment.service
    tasks = EmployeeTask.query.filter_by(employee_id=employee.id, service_id=service.id).order_by(EmployeeTask.task_date, EmployeeTask.id).all()
    running = employee_running_session(employee.id, service_id=service.id)
    elapsed = 0
    now_utc = datetime.utcnow()
    for item in EmployeeTimeSession.query.filter_by(employee_id=employee.id, service_id=service.id).all():
        elapsed += max(0, int(((item.ended_at or now_utc) - item.started_at).total_seconds()))
    return render_template("helper_service.html", employee=employee, service=service, tasks=tasks, running=running, elapsed=elapsed)


@app.route("/me/services/<int:service_id>/timer/start", methods=["POST"])
@login_required
def helper_service_timer_start(service_id):
    employee = current_employee()
    assignment = ServiceAssignment.query.filter_by(service_id=service_id, employee_id=employee.id if employee else -1).first_or_404()
    for running in EmployeeTimeSession.query.filter_by(employee_id=employee.id, ended_at=None).all():
        running.ended_at = datetime.utcnow()
    db.session.add(EmployeeTimeSession(employee_id=employee.id, service_id=service_id, started_at=datetime.utcnow()))
    if assignment.service.status == "scheduled":
        assignment.service.status = "in_progress"
    db.session.commit()
    flash("Seu cronômetro foi iniciado.", "success")
    return redirect(url_for("helper_service", service_id=service_id))


@app.route("/me/services/<int:service_id>/timer/pause", methods=["POST"])
@login_required
def helper_service_timer_pause(service_id):
    employee = current_employee()
    ServiceAssignment.query.filter_by(service_id=service_id, employee_id=employee.id if employee else -1).first_or_404()
    running = employee_running_session(employee.id, service_id=service_id)
    if running:
        running.ended_at = datetime.utcnow()
        db.session.commit()
        flash("Cronômetro pausado.", "success")
    return redirect(url_for("helper_service", service_id=service_id))


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
@admin_required
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
            exists = User.query.filter(User.username == username, User.id != user.id).first() or Employee.query.filter_by(username=username).first()
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
@admin_required
def backup_download():
    db.session.commit()
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = os.path.join(DATA_DIR, f"backup_guilherme_eletrica_{stamp}.zip")
    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(DB_PATH, arcname="guilherme_eletrica.db")
        if os.path.isdir(UPLOAD_DIR):
            for root, _, files in os.walk(UPLOAD_DIR):
                for filename in files:
                    full = os.path.join(root, filename)
                    rel = os.path.relpath(full, UPLOAD_DIR)
                    zf.write(full, arcname=os.path.join("uploads", rel))
    return send_file(backup_path, as_attachment=True, download_name=os.path.basename(backup_path))


@app.route("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat() + "Z"}


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
