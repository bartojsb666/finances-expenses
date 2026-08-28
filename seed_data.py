from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import random

# Import models from main
from main import AccountDB, ExpenseDB, SubscriptionDB, Base

SQLALCHEMY_DATABASE_URL = "sqlite:///./expenses_v4.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed():
    db = SessionLocal()
    
    # 1. Reset everything
    db.query(ExpenseDB).delete()
    db.query(SubscriptionDB).delete()
    db.commit()
    
    # 2. Reset Accounts Balances
    accounts = db.query(AccountDB).all()
    for acc in accounts:
        if acc.name == "TDD BBVA":
            acc.balance = 25400.50
        elif acc.name == "TDC BBVA":
            acc.balance = 8350.00 # Deuda
        elif acc.name == "Vales de Despensa":
            acc.balance = 3200.00
        elif acc.name == "Vales de Gasolina":
            acc.balance = 1500.00
    db.commit()

    # 3. Create Subscriptions
    subs = [
        {"name": "Netflix", "amount": 299.00, "account": "TDC BBVA", "cat": "Entretenimiento y Ocio/Suscripciones/Suscripciones", "day": 15, "month": 1, "periodicity": "mensual", "var": False},
        {"name": "CFE Luz", "amount": 450.00, "account": "TDD BBVA", "cat": "Vivienda/Gran Reserva/Luz", "day": 5, "month": 1, "periodicity": "mensual", "var": True},
        {"name": "Internet", "amount": 600.00, "account": "TDC BBVA", "cat": "Vivienda/Gran Reserva/Internet", "day": 20, "month": 1, "periodicity": "mensual", "var": False},
        {"name": "Seguro Mazda CX5", "amount": 12000.00, "account": "TDC BBVA", "cat": "Transporte/Mazda CX5/Seguro", "day": 12, "month": 10, "periodicity": "anual", "var": False},
    ]
    
    for s in subs:
        db.add(SubscriptionDB(
            name=s["name"], amount=s["amount"], account_name=s["account"],
            category_path=s["cat"], periodicity=s["periodicity"], billing_day=s["day"],
            billing_month=s["month"], is_variable=s["var"]
        ))
    db.commit()

    # 4. Create Historical Expenses (Categorized)
    today = datetime.utcnow()
    
    historical_data = [
        # Comida y Vales
        ("gasto", 1250.00, "Vales", "Vales de Despensa", "Comida/Súper / Despensa/Súper", "Walmart Mensual"),
        ("gasto", 350.00, "Vales", "Vales de Despensa", "Comida/Tiendita / Antojos/Antojos", "Oxxo botanas"),
        ("gasto", 850.00, "TDC", "TDC BBVA", "Comida/Restaurantes/Restaurantes", "Cena aniversario"),
        # Transporte
        ("gasto", 800.00, "Vales", "Vales de Gasolina", "Transporte/Mazda CX5/Gasolina", "Tanque lleno Mazda"),
        ("gasto", 400.00, "TDD", "TDD BBVA", "Transporte/Geely EX2/Luz", "Recarga auto eléctrico"),
        # Ingresos
        ("ingreso", 15000.00, "TDD", "TDD BBVA", "Ingresos/Sueldo/Quincena", "Pago Quincena"),
        ("ingreso", 3000.00, "Vales", "Vales de Despensa", "Ingresos/Vales/Despensa", "Recarga Sí Vale"),
        # Pagos Tarjeta
        ("gasto", 5000.00, "TDD", "TDD BBVA", "Otros/Varios/Pago de Tarjeta", "Pago mensual TDC"),
        ("ingreso", 5000.00, "TDC", "TDC BBVA", "Otros/Varios/Abono a Tarjeta", "Abono recibido TDC"),
        # Otros
        ("gasto", 550.00, "TDC", "TDC BBVA", "Mascotas/Alimento/Alimento", "Croquetas Perro"),
        ("gasto", 1200.00, "TDD", "TDD BBVA", "Compras/Ropa/Ropa", "Camisas Zara"),
    ]

    for i in range(25): # Generate 25 historical records
        data = random.choice(historical_data)
        days_ago = random.randint(1, 60) # Past 2 months
        
        db.add(ExpenseDB(
            transaction_type=data[0], amount=data[1], card_type=data[2], account_name=data[3],
            category_path=data[4], comment=data[5], raw_text=f"Compra autorizada: {data[5]} por ${data[1]}",
            status="categorized", date=today - timedelta(days=days_ago)
        ))
    db.commit()

    # 5. Create Pending Expenses (Not Categorized yet)
    db.add(ExpenseDB(
        transaction_type="gasto", amount=450.50, card_type="TDD", account_name="TDD BBVA",
        raw_text="Retiro por $450.50 en AMAZON MEXICO con tu TDD terminacion 1234",
        status="pending", date=today - timedelta(hours=2)
    ))
    db.add(ExpenseDB(
        transaction_type="gasto", amount=120.00, card_type="TDC", account_name="TDC BBVA",
        raw_text="Compra autorizada por $120.00 en STARBUCKS con TDC 5678",
        status="pending", date=today - timedelta(hours=5)
    ))
    
    db.commit()
    db.close()
    print("Datos ficticios generados exitosamente!")

if __name__ == "__main__":
    seed()
