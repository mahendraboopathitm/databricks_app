import os
import json
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
        access_token=os.getenv("DATABRICKS_TOKEN")
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
    successful_payments = len(payments_df[payments_df["payment_status"] == "SUCCESS"])
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
            .sum().sort_values(ascending=False)
        )
        st.bar_chart(restaurant_revenue)

    with right:
        st.subheader("Orders by City")
        city_orders = (
            orders_df.groupby("city")["order_id"]
            .count().sort_values(ascending=False)
        )
        st.bar_chart(city_orders)

    st.divider()

    left, right = st.columns(2)
    with left:
        st.subheader("Payment Method Distribution")
        st.bar_chart(payments_df["payment_method"].value_counts())

    with right:
        st.subheader("Delivery Status")
        st.bar_chart(delivery_df["delivery_status"].value_counts())

    st.divider()

    st.subheader("Latest Orders")
    st.dataframe(
        orders_df.sort_values("order_timestamp", ascending=False)[
            ["order_id", "customer_id", "restaurant", "city", "amount", "order_status", "order_timestamp"]
        ],
        use_container_width=True
    )

    # ─────────────────────────────────────────────
    # CHATBOT — powered by Databricks ai_query()
    # ─────────────────────────────────────────────
    st.divider()
    st.subheader("🤖 Dashboard Assistant")
    st.caption("Powered by Databricks AI Functions — no external API needed!")

    def build_data_context() -> str:
        order_status_counts   = orders_df["order_status"].value_counts().to_dict()
        top_restaurants       = orders_df.groupby("restaurant")["amount"].sum().sort_values(ascending=False).head(5).to_dict()
        top_cities            = orders_df.groupby("city")["order_id"].count().sort_values(ascending=False).head(5).to_dict()
        avg_order_value       = orders_df["amount"].mean()
        payment_method_dist   = payments_df["payment_method"].value_counts().to_dict()
        payment_status_dist   = payments_df["payment_status"].value_counts().to_dict()
        failed_payments       = len(payments_df[payments_df["payment_status"] != "SUCCESS"])
        delivery_status_dist  = delivery_df["delivery_status"].value_counts().to_dict()
        avg_distance          = delivery_df["distance_km"].mean()

        return f"""
ORDERS: total={total_orders}, revenue=₹{total_revenue:,.2f}, avg_order=₹{avg_order_value:,.2f}
Order statuses: {json.dumps(order_status_counts)}
Top restaurants by revenue: {json.dumps({k: round(v,2) for k,v in top_restaurants.items()})}
Top cities by orders: {json.dumps(top_cities)}

PAYMENTS: successful={successful_payments}, failed={failed_payments}
Payment methods: {json.dumps(payment_method_dist)}
Payment statuses: {json.dumps(payment_status_dist)}

DELIVERIES: avg_time={avg_delivery_time:.1f} mins, avg_distance={avg_distance:.2f} km
Delivery statuses: {json.dumps(delivery_status_dist)}
""".strip()

    def get_ai_query_response(user_question: str, data_context: str) -> str:
        """
        Uses Databricks ai_query() SQL function to call an LLM inside the warehouse.
        This is completely free — it uses your existing Databricks workspace AI credits.
        Requires: Databricks Runtime 13.1+ and a workspace with AI functions enabled.
        """
        prompt = (
            f"You are a food delivery analytics assistant. "
            f"Answer ONLY based on this data snapshot:\\n{data_context}\\n\\n"
            f"Question: {user_question}\\n"
            f"Be concise, use ₹ for currency, format numbers with commas."
        )
        # Escape single quotes in the prompt for SQL safety
        safe_prompt = prompt.replace("'", "\\'")

        ai_sql = f"""
        SELECT ai_query(
            'databricks-meta-llama-3-3-70b-instruct',
            '{safe_prompt}'
        ) AS response
        """
        try:
            result_df = run_query(ai_sql)
            return result_df["response"].iloc[0]
        except Exception as e:
            err = str(e)
            if "ai_query" in err.lower() or "not found" in err.lower():
                return (
                    "⚠️ `ai_query()` is not enabled in your Databricks workspace. "
                    "Ask your admin to enable **Databricks AI Functions** (requires DBR 13.1+). "
                    "Until then, switch to the fuzzy-match version (app_v2_fuzzy.py)."
                )
            return f"❌ Error calling ai_query: {err}"

    DATA_CONTEXT = build_data_context()

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hi! I'm your Food Delivery Assistant 🍔 Ask me anything about your data!"}
        ]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask about your data..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Querying Databricks AI..."):
                reply = get_ai_query_response(prompt, DATA_CONTEXT)
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})

except Exception as e:
    st.error("Unable to load data from Unity Catalog tables.")
    st.exception(e)
