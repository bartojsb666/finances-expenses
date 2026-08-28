from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from pydantic import BaseModel
from datetime import datetime
import re
import os

# Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./expenses_v4.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AccountDB(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    account_type = Column(String) # debit, credit
    balance = Column(Float, default=0.0)

class ExpenseDB(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(String, default="gasto") # gasto, ingreso
    amount = Column(Float, nullable=True)
    card_type = Column(String, nullable=True) # TDD, TDC, Manual
    account_name = Column(String, nullable=True)
    category_path = Column(String, default="Sin clasificar")
    comment = Column(String, nullable=True)
    date = Column(DateTime, default=datetime.utcnow)
    raw_text = Column(String)
    status = Column(String, default="pending") # pending, categorized

class SubscriptionDB(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    amount = Column(Float)
    account_name = Column(String)
    category_path = Column(String)
    periodicity = Column(String) # mensual, anual
    billing_day = Column(Integer) # 1-31
    billing_month = Column(Integer, default=1, nullable=True) # 1-12
    is_variable = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_processed = Column(DateTime, nullable=True)

Base.metadata.create_all(bind=engine)

# Seed Accounts
def seed_accounts():
    db = SessionLocal()
    accounts = [
        {"name": "TDD BBVA", "type": "debit"},
        {"name": "TDC BBVA", "type": "credit"},
        {"name": "Vales de Despensa", "type": "debit"},
        {"name": "Vales de Gasolina", "type": "debit"}
    ]
    for acc in accounts:
        if not db.query(AccountDB).filter(AccountDB.name == acc["name"]).first():
            db.add(AccountDB(name=acc["name"], account_type=acc["type"], balance=0.0))
    db.commit()
    db.close()

seed_accounts()

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Expense Tracker API V3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic Models
class WebhookPayload(BaseModel):
    title: str
    text: str
    package_name: str = ""

class CategoryUpdate(BaseModel):
    category_path: str
    account_name: str
    comment: str = ""
    amount: float = None

class ManualEntry(BaseModel):
    transaction_type: str
    amount: float
    account_name: str
    category_path: str
    comment: str = ""

class SubscriptionCreate(BaseModel):
    name: str
    amount: float
    account_name: str
    category_path: str
    periodicity: str
    billing_day: int
    billing_month: int = 1
    is_variable: bool

class AccountUpdate(BaseModel):
    balance: float

def parse_notification(text: str):
    amount_match = re.search(r'\$?\s*([\d,]+(?:\.\d{1,2})?)', text)
    amount = 0.0
    if amount_match:
        clean_amount = amount_match.group(1).replace(',', '')
        try:
            amount = float(clean_amount)
        except ValueError:
            pass
    
    text_upper = text.upper()
    card_type = "Desconocido"
    account_name = "TDD BBVA"
    
    if "TDC" in text_upper or "CREDITO" in text_upper or "CRÉDITO" in text_upper:
        card_type = "TDC"
        account_name = "TDC BBVA"
    elif "TDD" in text_upper or "DEBITO" in text_upper or "DÉBITO" in text_upper or "CUENTA" in text_upper:
        card_type = "TDD"
        account_name = "TDD BBVA"
    elif "VALE" in text_upper or "DESPENSA" in text_upper or "SI VALE" in text_upper:
        card_type = "Vales"
        account_name = "Vales de Despensa"
        if "GASOLINA" in text_upper:
            account_name = "Vales de Gasolina"
            
    transaction_type = "gasto"
    if "RECIBISTE" in text_upper or "TRANSFERENCIA A TU FAVOR" in text_upper or "ABONO" in text_upper:
        transaction_type = "ingreso"
        
    return amount, card_type, transaction_type, account_name

def apply_balance(db, account_name, amount, transaction_type):
    acc = db.query(AccountDB).filter(AccountDB.name == account_name).first()
    if acc:
        if acc.account_type == "debit":
            acc.balance += amount if transaction_type == "ingreso" else -amount
        elif acc.account_type == "credit":
            acc.balance += -amount if transaction_type == "ingreso" else amount
        db.commit()

def process_subscriptions(db):
    today = datetime.utcnow()
    subs = db.query(SubscriptionDB).filter(SubscriptionDB.is_active == True).all()
    for sub in subs:
        should_charge = False
        if sub.periodicity == 'mensual' and today.day == sub.billing_day:
            if not sub.last_processed or (today - sub.last_processed).days > 20:
                should_charge = True
        elif sub.periodicity == 'anual' and today.month == (sub.billing_month or 1) and today.day == sub.billing_day:
            if not sub.last_processed or (today - sub.last_processed).days > 330:
                should_charge = True
                
        if should_charge:
            status = "pending" if sub.is_variable else "categorized"
            new_exp = ExpenseDB(
                transaction_type="gasto",
                amount=sub.amount,
                card_type="Domiciliado",
                account_name=sub.account_name,
                category_path=sub.category_path,
                comment=f"Cobro domiciliado: {sub.name}",
                raw_text=f"Domiciliado: {sub.name}" + (" (Por Confirmar)" if sub.is_variable else ""),
                status=status
            )
            db.add(new_exp)
            sub.last_processed = today
            if status == "categorized":
                apply_balance(db, sub.account_name, sub.amount, "gasto")
    db.commit()

@app.get("/api/accounts")
def get_accounts():
    db = SessionLocal()
    accounts = db.query(AccountDB).all()
    db.close()
    return accounts

@app.put("/api/accounts/{account_id}")
def update_account(account_id: int, update: AccountUpdate):
    db = SessionLocal()
    acc = db.query(AccountDB).filter(AccountDB.id == account_id).first()
    if acc:
        acc.balance = update.balance
        db.commit()
        db.close()
        return {"message": "Success"}
    db.close()
    return {"error": "Not found"}

@app.post("/api/webhook")
async def receive_webhook(payload: WebhookPayload):
    amount, card_type, transaction_type, account_name = parse_notification(payload.text)
    db = SessionLocal()
    new_expense = ExpenseDB(
        transaction_type=transaction_type,
        amount=amount,
        card_type=card_type,
        account_name=account_name,
        raw_text=payload.text,
        status="pending"
    )
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    db.close()
    return {"message": "Success", "id": new_expense.id}

@app.post("/api/expenses/manual")
async def add_manual_entry(entry: ManualEntry):
    db = SessionLocal()
    new_expense = ExpenseDB(
        transaction_type=entry.transaction_type,
        amount=entry.amount,
        card_type="Manual",
        account_name=entry.account_name,
        category_path=entry.category_path,
        comment=entry.comment,
        raw_text=f"Registro Manual: {entry.comment}",
        status="categorized"
    )
    db.add(new_expense)
    apply_balance(db, entry.account_name, entry.amount, entry.transaction_type)
    db.commit()
    db.close()
    return {"message": "Success"}

@app.get("/api/expenses")
def get_expenses():
    db = SessionLocal()
    process_subscriptions(db) 
    expenses = db.query(ExpenseDB).order_by(ExpenseDB.date.desc()).all()
    db.close()
    return expenses

@app.put("/api/expenses/{expense_id}")
def update_expense_category(expense_id: int, update: CategoryUpdate):
    db = SessionLocal()
    expense = db.query(ExpenseDB).filter(ExpenseDB.id == expense_id).first()
    if expense:
        was_pending = expense.status == "pending"
        expense.category_path = update.category_path
        expense.comment = update.comment
        expense.account_name = update.account_name
        if update.amount is not None:
            expense.amount = update.amount
        expense.status = "categorized"
        
        # Apply to balance only when transitioning from pending to categorized
        if was_pending:
            apply_balance(db, expense.account_name, expense.amount, expense.transaction_type)
            
        db.commit()
        db.close()
        return {"message": "Updated"}
    db.close()
    return {"error": "Not found"}

@app.get("/api/subscriptions")
def get_subscriptions():
    db = SessionLocal()
    subs = db.query(SubscriptionDB).all()
    db.close()
    return subs

@app.post("/api/subscriptions")
def add_subscription(sub: SubscriptionCreate):
    db = SessionLocal()
    new_sub = SubscriptionDB(
        name=sub.name,
        amount=sub.amount,
        account_name=sub.account_name,
        category_path=sub.category_path,
        periodicity=sub.periodicity,
        billing_day=sub.billing_day,
        billing_month=sub.billing_month,
        is_variable=sub.is_variable
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    db.close()
    return new_sub

@app.put("/api/subscriptions/{sub_id}")
def update_subscription(sub_id: int, update: SubscriptionCreate):
    db = SessionLocal()
    sub = db.query(SubscriptionDB).filter(SubscriptionDB.id == sub_id).first()
    if sub:
        sub.name = update.name
        sub.amount = update.amount
        sub.account_name = update.account_name
        sub.category_path = update.category_path
        sub.periodicity = update.periodicity
        sub.billing_day = update.billing_day
        sub.billing_month = update.billing_month
        sub.is_variable = update.is_variable
        db.commit()
        db.close()
        return {"message": "Updated"}
    db.close()
    return {"error": "Not found"}

@app.delete("/api/subscriptions/{sub_id}")
def delete_subscription(sub_id: int):
    db = SessionLocal()
    sub = db.query(SubscriptionDB).filter(SubscriptionDB.id == sub_id).first()
    if sub:
        db.delete(sub)
        db.commit()
        db.close()
        return {"message": "Deleted"}
    db.close()
    return {"error": "Not found"}

@app.get("/", response_class=HTMLResponse)
def index():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Frontend not built yet</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
