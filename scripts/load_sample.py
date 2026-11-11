"""Generate a synthetic churn dataset and load it into Postgres.

    python scripts/load_sample.py

Only for rehearsing the pipeline. Replaced by the real challenge database.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import Date, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db import engine  # noqa: E402

CUSTOMERS = 3000
REFERENCE_DATE = pd.Timestamp("2026-11-01")
rng = np.random.default_rng(42)


def build():
    ids = np.arange(1, CUSTOMERS + 1)
    plan = rng.choice(["Basico", "Padrao", "Premium"], CUSTOMERS, p=[0.5, 0.35, 0.15])
    tenure = rng.integers(1, 72, CUSTOMERS)
    fee = pd.Series(plan).map({"Basico": 89.0, "Padrao": 179.0, "Premium": 349.0}).to_numpy()

    late_propensity = rng.beta(1.2, 6, CUSTOMERS)
    inactive_days = rng.exponential(25, CUSTOMERS).astype(int)
    orders_per_customer = rng.poisson(8, CUSTOMERS)
    tickets_per_customer = rng.poisson(1.2, CUSTOMERS)

    order_owner = np.repeat(ids, orders_per_customer)
    order_age = rng.integers(0, 330, order_owner.size) + np.repeat(inactive_days, orders_per_customer)
    orders = pd.DataFrame(
        {
            "order_id": np.arange(1, order_owner.size + 1),
            "customer_id": order_owner,
            "order_date": (REFERENCE_DATE - pd.to_timedelta(order_age, unit="D")).date,
            "amount": rng.gamma(2.0, 120.0, order_owner.size).round(2),
            "paid_late": rng.random(order_owner.size)
            < np.repeat(late_propensity, orders_per_customer),
        }
    )

    ticket_owner = np.repeat(ids, tickets_per_customer)
    tickets = pd.DataFrame(
        {
            "ticket_id": np.arange(1, ticket_owner.size + 1),
            "customer_id": ticket_owner,
            "opened_at": (
                REFERENCE_DATE - pd.to_timedelta(rng.integers(0, 365, ticket_owner.size), unit="D")
            ).date,
            "category": rng.choice(["Cobranca", "Tecnico", "Cadastro"], ticket_owner.size),
            "resolved": rng.random(ticket_owner.size) < 0.75,
        }
    )

    late_count = orders.groupby("customer_id")["paid_late"].sum().reindex(ids, fill_value=0)
    unresolved = (
        tickets[~tickets["resolved"]].groupby("customer_id").size().reindex(ids, fill_value=0)
    )
    logit = (
        -2.2
        + 0.55 * late_count.to_numpy()
        + 0.9 * unresolved.to_numpy()
        + 0.02 * inactive_days
        - 0.025 * tenure
        + np.where(plan == "Basico", 0.4, 0.0)
    )
    churned = rng.random(CUSTOMERS) < 1 / (1 + np.exp(-logit))

    customers = pd.DataFrame(
        {
            "customer_id": ids,
            "segment": rng.choice(["PF", "PME", "Corporativo"], CUSTOMERS, p=[0.6, 0.3, 0.1]),
            "state": rng.choice(["SP", "RJ", "MG", "PR", "RS", "BA"], CUSTOMERS),
            "plan": plan,
            "monthly_fee": fee,
            "tenure_months": tenure,
            "churned": churned,
        }
    )
    return customers, orders, tickets


def load(customers, orders, tickets):
    with engine().begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS support_tickets, orders, customers CASCADE"))
        customers.to_sql("customers", conn, index=False)
        orders.to_sql("orders", conn, index=False, dtype={"order_date": Date})
        tickets.to_sql("support_tickets", conn, index=False, dtype={"opened_at": Date})
        conn.execute(text("ALTER TABLE customers ADD PRIMARY KEY (customer_id)"))
        conn.execute(text("ALTER TABLE orders ADD PRIMARY KEY (order_id)"))
        conn.execute(text("ALTER TABLE support_tickets ADD PRIMARY KEY (ticket_id)"))
        conn.execute(
            text("ALTER TABLE orders ADD FOREIGN KEY (customer_id) REFERENCES customers")
        )
        conn.execute(
            text("ALTER TABLE support_tickets ADD FOREIGN KEY (customer_id) REFERENCES customers")
        )


if __name__ == "__main__":
    customers, orders, tickets = build()
    load(customers, orders, tickets)
    print(
        f"customers={len(customers)} orders={len(orders)} support_tickets={len(tickets)} "
        f"churn_rate={customers['churned'].mean():.1%}"
    )
