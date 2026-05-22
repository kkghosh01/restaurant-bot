from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime, timezone
import os

# ─── Engine ──────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///orders.db")

# PostgreSQL URL fix (Render দেয় postgres://, SQLAlchemy চায় postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ─── Models ──────────────────────────────────────────
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
