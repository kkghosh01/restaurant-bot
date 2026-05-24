from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime, timezone, timedelta
import os
import json

# ─── Engine ──────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///orders.db")

# PostgreSQL URL fix (Render provides postgres://; ensure SQLAlchemy uses psycopg driver)
# postgres:// -> postgresql+psycopg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
# postgresql:// -> postgresql+psycopg:// (also convert if already postgresql)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Use different engine settings for SQLite vs other DBs (PostgreSQL)
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ─── Models ──────────────────────────────────────────


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String, nullable=False)  # pizza/burger/drinks
    name = Column(String, nullable=False)
    bangla = Column(String, nullable=False)  # JSON string
    aliases = Column(String, nullable=True)  # JSON string list of aliases
    price = Column(Integer, nullable=False)
    active = Column(Integer, default=1)  # 1=active, 0=hidden


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    trx_id = Column(String, nullable=False)
    phone_last4 = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, default="pending")  # pending/confirmed/rejected
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)

    order = relationship("Order", back_populates="payment")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    address = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    total = Column(Integer, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Order #{self.id} | ৳{self.total} | {self.status}>"

    payment = relationship(
        "Payment", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    qty = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")

    def __repr__(self):
        return f"<OrderItem {self.name} x{self.qty}>"


# ─── Create Tables ───────────────────────────────────
def init_db():
    Base.metadata.create_all(engine)
    print("✅ Database ready!")


# ─── Save Order ──────────────────────────────────────
def save_order(user_id: int, items: list, address: str, phone: str, total: int) -> int:
    """
    Order database-এ save করো।
    Returns: order ID
    """
    db = SessionLocal()
    try:
        order = Order(
            user_id=user_id,
            address=address,
            phone=phone,
            total=total,
            status="pending",
        )
        db.add(order)
        db.flush()  # ID পাওয়ার জন্য

        for item in items:
            db.add(
                OrderItem(
                    order_id=order.id,
                    name=item["name"],
                    price=item["price"],
                    qty=item["qty"],
                )
            )

        db.commit()
        print(f"💾 Order #{order.id} saved!")
        return order.id

    except Exception as e:
        db.rollback()
        print(f"❌ DB Error: {e}")
        return -1
    finally:
        db.close()


# ─── Get All Orders ──────────────────────────────────
def get_all_orders() -> list:
    db = SessionLocal()
    try:
        orders = db.query(Order).order_by(Order.created_at.desc()).all()
        return orders
    finally:
        db.close()


# ─── Update Order Status ─────────────────────────────
def update_order_status(order_id: int, status: str):
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            order.status = status
            db.commit()
    finally:
        db.close()


def get_pending_order_by_user(user_id: int):
    """
    User-এর pending order খোঁজো।
    Condition:
    - order status = pending
    - payment নেই অথবা payment rejected
    """
    db = SessionLocal()
    try:
        orders = (
            db.query(Order)
            .filter(Order.user_id == user_id, Order.status == "pending")
            .order_by(Order.created_at.desc())
            .all()
        )

        for order in orders:
            # Payment আছে কিনা check করো
            payment = (
                db.query(Payment)
                .filter(
                    Payment.order_id == order.id,
                    Payment.status.in_(["pending", "confirmed"]),
                )
                .first()
            )

            # Payment নেই → এই order-টাই show করো
            if not payment:
                return order

        return None
    finally:
        db.close()


def get_order_by_id(order_id: int):
    """Order ID দিয়ে order খোঁজো"""
    db = SessionLocal()
    try:
        return db.query(Order).filter(Order.id == order_id).first()
    finally:
        db.close()


def has_pending_payment(order_id: int) -> bool:
    """Order-এ already pending/confirmed payment আছে কিনা"""
    db = SessionLocal()
    try:
        payment = (
            db.query(Payment)
            .filter(
                Payment.order_id == order_id,
                Payment.status.in_(["pending", "confirmed"]),
            )
            .first()
        )
        return payment is not None
    finally:
        db.close()


# ─── Save Payment ─────────────────────────────────────
def save_payment(order_id: int, trx_id: str, phone_last4: str, amount: int) -> bool:
    db = SessionLocal()
    try:
        payment = Payment(
            order_id=order_id,
            trx_id=trx_id,
            phone_last4=phone_last4,
            amount=amount,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.add(payment)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"❌ Payment save error: {e}")
        return False
    finally:
        db.close()


def cancel_order(order_id: int):
    """Order cancel করো — DB status update"""
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            order.status = "cancelled"
            db.commit()
    finally:
        db.close()


# ─── Menu Cache ──────────────────────────────────────
MENU_CACHE: dict = {}


def load_menu_cache():
    """Startup-এ একবার load করো"""
    global MENU_CACHE
    MENU_CACHE = get_menu_from_db()
    print(f"✅ Menu cache loaded! ({sum(len(v) for v in MENU_CACHE.values())} items)")


def refresh_menu_cache():
    """Admin menu edit করলে call করো"""
    global MENU_CACHE
    MENU_CACHE = get_menu_from_db()
    print("🔄 Menu cache refreshed!")


def seed_menu():
    """প্রথমবার menu DB-তে insert করো"""
    db = SessionLocal()
    try:
        # Already data আছে কিনা check করো
        existing = db.query(MenuItem).first()
        if existing:
            return

        items = [
            # Pizza
            MenuItem(
                category="pizza",
                name="Margherita Pizza",
                bangla=json.dumps(["মার্গারিটা", "মার্গারিতা", "margherita"]),
                aliases=json.dumps(
                    [
                        "margherita",
                        "margherita pizza",
                        "cheese pizza",
                        "margherita pizza",
                    ]
                ),
                price=350,
            ),
            MenuItem(
                category="pizza",
                name="Chicken BBQ Pizza",
                bangla=json.dumps(["চিকেন বিবিকিউ", "বিবিকিউ", "bbq", "বারবেকু"]),
                aliases=json.dumps(["chicken bbq", "bbq pizza", "chicken barbecue"]),
                price=450,
            ),
            MenuItem(
                category="pizza",
                name="Veggie Delight",
                bangla=json.dumps(["ভেজি", "veggie", "সবজি"]),
                aliases=json.dumps(["veggie", "veggie pizza", "vegetarian pizza"]),
                price=320,
            ),
            # Burger
            MenuItem(
                category="burger",
                name="Classic Beef Burger",
                bangla=json.dumps(["বিফ বার্গার", "বিফ", "beef"]),
                aliases=json.dumps(["beef burger", "classic burger", "beef"]),
                price=220,
            ),
            MenuItem(
                category="burger",
                name="Chicken Crispy Burger",
                bangla=json.dumps(["চিকেন ক্রিস্পি", "ক্রিস্পি", "crispy"]),
                aliases=json.dumps(
                    ["chicken crispy", "crispy burger", "chicken burger"]
                ),
                price=180,
            ),
            # Drinks
            MenuItem(
                category="drinks",
                name="Coke",
                bangla=json.dumps(["কোক", "কোলা"]),
                aliases=json.dumps(["coke", "cola"]),
                price=60,
            ),
            MenuItem(
                category="drinks",
                name="Fresh Juice",
                bangla=json.dumps(["রস", "জুস", "juice"]),
                aliases=json.dumps(["juice", "fresh juice"]),
                price=80,
            ),
            MenuItem(
                category="drinks",
                name="Water",
                bangla=json.dumps(["পানি", "water"]),
                aliases=json.dumps(["water"]),
                price=20,
            ),
        ]

        db.add_all(items)
        db.commit()
        print("✅ Menu seeded!")
    finally:
        db.close()


def get_menu_from_db() -> dict:
    """DB থেকে menu load করো"""
    db = SessionLocal()
    try:
        items = db.query(MenuItem).filter(MenuItem.active == 1).all()

        menu = {}
        for item in items:
            if item.category not in menu:
                menu[item.category] = []
            menu[item.category].append(
                {
                    "id": item.id,
                    "name": item.name,
                    "bangla": json.loads(item.bangla),
                    "aliases": json.loads(item.aliases) if item.aliases else [],
                    "price": item.price,
                }
            )
        return menu
    finally:
        db.close()


def cleanup_expired_payments() -> int:
    """Mark pending payments that have expired as 'expired'. Returns number of updated rows."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired = (
            db.query(Payment)
            .filter(Payment.status == "pending", Payment.expires_at < now)
            .all()
        )
        count = 0
        for p in expired:
            p.status = "expired"
            count += 1
        if count:
            db.commit()
        return count
    except Exception as e:
        db.rollback()
        print(f"❌ cleanup_expired_payments error: {e}")
        return 0
    finally:
        db.close()
