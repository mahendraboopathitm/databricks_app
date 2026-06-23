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

    # ---- CHATBOT SECTION ----
    st.divider()
    st.subheader("🤖 Dashboard Assistant")
    st.caption("Ask me anything about your food delivery data!")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hi! I'm your Food Delivery Assistant 🍔 Ask me about orders, revenue, deliveries, or payments!"}
        ]

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    def get_bot_response(user_input):
        text = user_input.lower().strip()

        # Total orders
        if any(k in text for k in ["total orders", "how many orders", "order count"]):
            return f"📦 Total orders placed: **{total_orders:,}**"

        # Total revenue
        elif any(k in text for k in ["total revenue", "how much revenue", "revenue"]):
            return f"💰 Total revenue generated: **₹ {total_revenue:,.2f}**"

        # Average delivery time
        elif any(k in text for k in ["average delivery", "avg delivery", "delivery time", "how long"]):
            return f"🚴 Average delivery time: **{avg_delivery_time:.1f} minutes**"

        # Successful payments
        elif any(k in text for k in ["successful payments", "payment success", "success payments"]):
            return f"✅ Successful payments: **{successful_payments:,}**"

        # Top restaurant by revenue
        elif any(k in text for k in ["top restaurant", "best restaurant", "highest revenue restaurant"]):
            top = restaurant_revenue.idxmax()
            val = restaurant_revenue.max()
            return f"🏆 Top restaurant by revenue: **{top}** with ₹ {val:,.2f}"

        # Top city by orders
        elif any(k in text for k in ["top city", "best city", "most orders city", "city"]):
            top_city = city_orders.idxmax()
            val = city_orders.max()
            return f"🏙️ City with most orders: **{top_city}** with {val:,} orders"

        # Payment methods
        elif any(k in text for k in ["payment method", "how do people pay", "popular payment"]):
            top_method = payments_df["payment_method"].value_counts().idxmax()
            return f"💳 Most popular payment method: **{top_method}**"

        # Delivery status
        elif any(k in text for k in ["delivery status", "delivered", "pending delivery"]):
            status_counts = delivery_df["delivery_status"].value_counts()
            response = "📊 Delivery Status Breakdown:\n"
            for status, count in status_counts.items():
                response += f"- **{status}**: {count:,}\n"
            return response

        # Failed payments
        elif any(k in text for k in ["failed payment", "payment failed", "unsuccessful"]):
            failed = len(payments_df[payments_df["payment_status"] != "SUCCESS"])
            return f"❌ Failed/Pending payments: **{failed:,}**"

        # Average order value
        elif any(k in text for k in ["average order", "avg order", "order value"]):
            avg_order = orders_df["amount"].mean()
            return f"🧾 Average order value: **₹ {avg_order:,.2f}**"

        # Help
        elif any(k in text for k in ["help", "what can you do", "commands"]):
            return """🤖 I can answer questions like:
- "What is the total revenue?"
- "How many orders were placed?"
- "What is the average delivery time?"
- "Which is the top restaurant?"
- "Which city has the most orders?"
- "What is the most popular payment method?"
- "How many successful payments?"
- "What is the delivery status breakdown?"
- "What is the average order value?"
"""

        # Greeting
        elif any(k in text for k in ["hi", "hello", "hey"]):
            return "👋 Hello! Ask me anything about your food delivery data!"

        # Default
        else:
            return "🤔 I didn't understand that. Type **help** to see what I can answer!"

    # Chat input
    if prompt := st.chat_input("Ask about your data..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get and display bot response
        response = get_bot_response(prompt)
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

except Exception as e:
    st.error("Unable to load data from Unity Catalog tables.")
    st.exception(e)
