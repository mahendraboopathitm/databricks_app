import os
import pandas as pd
import streamlit as st
from databricks import sql

st.set_page_config(
    page_title="Food Delivery Analytics",
    page_icon="🍔",
    layout="wide"
)

st.title("🍔 Food Delivery Analytics Dashboard")
st.caption("Built using Databricks Apps, Unity Catalog, and SQL Warehouse")

WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID")

@st.cache_data(ttl=300)
def run_query(query):
    connection = sql.connect(
        server_hostname=os.getenv("DATABRICKS_HOST"),
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: sql.oauth_service_principal(
            os.getenv("DATABRICKS_CLIENT_ID"),
            os.getenv("DATABRICKS_CLIENT_SECRET")
        )
    )

    with connection.cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchall_arrow().to_pandas()

    connection.close()
    return result


orders_query = """
SELECT
  get_json_object(value, '$.order_id') AS order_id,
  get_json_object(value, '$.customer_id') AS customer_id,
  get_json_object(value, '$.restaurant') AS restaurant,
  get_json_object(value, '$.city') AS city,
  CAST(get_json_object(value, '$.amount') AS DOUBLE) AS amount,
  get_json_object(value, '$.status') AS order_status,
  CAST(get_json_object(value, '$.timestamp') AS TIMESTAMP) AS order_timestamp
FROM dqx.producer.orders
"""

payments_query = """
SELECT
  get_json_object(value, '$.payment_id') AS payment_id,
  get_json_object(value, '$.order_id') AS order_id,
  get_json_object(value, '$.customer_id') AS customer_id,
  CAST(get_json_object(value, '$.amount') AS DOUBLE) AS payment_amount,
  get_json_object(value, '$.payment_method') AS payment_method,
  get_json_object(value, '$.status') AS payment_status,
  CAST(get_json_object(value, '$.timestamp') AS TIMESTAMP) AS payment_timestamp
FROM dqx.producer.payments
"""

delivery_query = """
SELECT
  get_json_object(value, '$.delivery_id') AS delivery_id,
  get_json_object(value, '$.order_id') AS order_id,
  get_json_object(value, '$.driver_id') AS driver_id,
  get_json_object(value, '$.restaurant') AS restaurant,
  get_json_object(value, '$.city') AS city,
  get_json_object(value, '$.status') AS delivery_status,
  CAST(get_json_object(value, '$.distance_km') AS DOUBLE) AS distance_km,
  CAST(get_json_object(value, '$.delivery_time_mins') AS DOUBLE) AS delivery_time_mins,
  CAST(get_json_object(value, '$.timestamp') AS TIMESTAMP) AS delivery_timestamp
FROM dqx.producer.delhivery_status
"""

try:
    orders_df = run_query(orders_query)
    payments_df = run_query(payments_query)
    delivery_df = run_query(delivery_query)

    total_orders = len(orders_df)
    total_revenue = orders_df["amount"].sum()
    successful_payments = len(
        payments_df[payments_df["payment_status"] == "SUCCESS"]
    )
    avg_delivery_time = delivery_df["delivery_time_mins"].mean()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Orders", f"{total_orders:,}")
    col2.metric("Total Revenue", f"₹ {total_revenue:,.2f}")
    col3.metric("Successful Payments", f"{successful_payments:,}")
    col4.metric("Avg Delivery Time", f"{avg_delivery_time:.1f} mins")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Revenue by Restaurant")

        restaurant_revenue = (
            orders_df.groupby("restaurant")["amount"]
            .sum()
            .sort_values(ascending=False)
        )

        st.bar_chart(restaurant_revenue)

    with right:
        st.subheader("Orders by City")

        city_orders = (
            orders_df.groupby("city")["order_id"]
            .count()
            .sort_values(ascending=False)
        )

        st.bar_chart(city_orders)

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Payment Method Distribution")

        payment_method_count = (
            payments_df["payment_method"]
            .value_counts()
        )

        st.bar_chart(payment_method_count)

    with right:
        st.subheader("Delivery Status")

        delivery_status_count = (
            delivery_df["delivery_status"]
            .value_counts()
        )

        st.bar_chart(delivery_status_count)

    st.divider()

    st.subheader("Latest Orders")

    latest_orders = orders_df.sort_values(
        by="order_timestamp",
        ascending=False
    )

    st.dataframe(
        latest_orders[
            [
                "order_id",
                "customer_id",
                "restaurant",
                "city",
                "amount",
                "order_status",
                "order_timestamp"
            ]
        ],
        use_container_width=True
    )

except Exception as e:
    st.error("Unable to load data from Unity Catalog tables.")
    st.exception(e)
