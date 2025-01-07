import streamlit as st
import sqlite3
from datetime import datetime, date
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def init_db():
    conn = sqlite3.connect('farmer_loans.db')
    c = conn.cursor()
    
    # Create loans table with father_name column
    c.execute('''
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_name TEXT NOT NULL,
            father_name TEXT NOT NULL,
            loan_amount REAL NOT NULL,
            interest_rate REAL NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            status TEXT DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create loan history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS loan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER,
            action TEXT NOT NULL,
            action_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            FOREIGN KEY (loan_id) REFERENCES loans (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def calculate_interest(amount, rate, start_date, end_date):
    days = (end_date - start_date).days
    interest = (amount * rate * days) / (100 * 365)
    return round(interest, 2)

def calculate_days_remaining(end_date):
    remaining = (end_date - date.today()).days
    return max(remaining, 0)

def add_loan(farmer_name, father_name, amount, rate, start_date, end_date):
    conn = sqlite3.connect('farmer_loans.db')
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO loans (farmer_name, father_name, loan_amount, interest_rate, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (farmer_name, father_name, amount, rate, start_date, end_date))
        
        loan_id = c.lastrowid
        c.execute('''
            INSERT INTO loan_history (loan_id, action, details)
            VALUES (?, ?, ?)
        ''', (loan_id, 'CREATE', f'Loan created for {farmer_name} (s/o {father_name}) with amount ₹{amount:,.2f}'))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error adding loan: {str(e)}")
        return False
    finally:
        conn.close()

def get_all_loans():
    conn = sqlite3.connect('farmer_loans.db')
    loans_df = pd.read_sql_query('''
        SELECT * FROM loans WHERE status = 'Active'
    ''', conn)
    conn.close()
    
    if not loans_df.empty:
        loans_df['start_date'] = pd.to_datetime(loans_df['start_date'])
        loans_df['end_date'] = pd.to_datetime(loans_df['end_date'])
        today = date.today()
        
        loans_df['current_interest'] = loans_df.apply(
            lambda x: calculate_interest(
                x['loan_amount'],
                x['interest_rate'],
                x['start_date'].date(),
                today
            ),
            axis=1
        )
        loans_df['total_amount'] = loans_df['loan_amount'] + loans_df['current_interest']
        loans_df['days_remaining'] = loans_df['end_date'].apply(
            lambda x: calculate_days_remaining(x.date())
        )
        loans_df['status_color'] = loans_df['days_remaining'].apply(
            lambda x: 'red' if x <= 30 else 'yellow' if x <= 90 else 'green'
        )
    return loans_df

def get_loan_history():
    conn = sqlite3.connect('farmer_loans.db')
    history_df = pd.read_sql_query('''
        SELECT 
            h.action_timestamp,
            l.farmer_name,
            l.father_name,
            h.action,
            h.details
        FROM loan_history h
        JOIN loans l ON h.loan_id = l.id
        ORDER BY h.action_timestamp DESC
    ''', conn)
    conn.close()
    return history_df

def delete_loan(loan_id, reason):
    conn = sqlite3.connect('farmer_loans.db')
    c = conn.cursor()
    try:
        c.execute("UPDATE loans SET status = 'Inactive' WHERE id = ?", (loan_id,))
        c.execute('''
            INSERT INTO loan_history (loan_id, action, details)
            VALUES (?, ?, ?)
        ''', (loan_id, 'DELETE', f'Loan marked as inactive. Reason: {reason}'))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error deleting loan: {str(e)}")
        return False
    finally:
        conn.close()

def update_loan_end_date(loan_id, new_end_date, reason):
    conn = sqlite3.connect('farmer_loans.db')
    c = conn.cursor()
    try:
        c.execute("UPDATE loans SET end_date = ? WHERE id = ?", (new_end_date, loan_id))
        c.execute('''
            INSERT INTO loan_history (loan_id, action, details)
            VALUES (?, ?, ?)
        ''', (loan_id, 'UPDATE', f'End date updated to {new_end_date}. Reason: {reason}'))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error updating loan: {str(e)}")
        return False
    finally:
        conn.close()

def main():
    st.set_page_config(
        page_title="Farmer Loan Management System",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.markdown("""
        <style>
        .main {
            padding: 2rem;
        }
        .stMetric {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 0.5rem;
        }
        .status-card {
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 0.5rem 0;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("🌾 Farmer Loan Management System")
    
    init_db()
    
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", [
        "Dashboard",
        "Add New Loan",
        "Manage Loans",
        "Loan History",
        "Analytics"
    ])
    
    if page == "Dashboard":
        st.header("📊 Dashboard")
        
        loans_df = get_all_loans()
        
        if not loans_df.empty:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_loans = loans_df['loan_amount'].sum()
                st.metric("Total Loan Amount", f"₹{total_loans:,.2f}")
                
            with col2:
                total_interest = loans_df['current_interest'].sum()
                st.metric("Total Interest Accrued", f"₹{total_interest:,.2f}")
                
            with col3:
                total_outstanding = loans_df['total_amount'].sum()
                st.metric("Total Outstanding", f"₹{total_outstanding:,.2f}")
            
            with col4:
                active_loans = len(loans_df)
                st.metric("Active Loans", active_loans)
            
            st.subheader("Loan Status Summary")
            status_cols = st.columns(3)
            
            with status_cols[0]:
                critical_loans = len(loans_df[loans_df['days_remaining'] <= 30])
                st.error(f"Critical (≤30 days): {critical_loans}")
                
            with status_cols[1]:
                warning_loans = len(loans_df[(loans_df['days_remaining'] > 30) & (loans_df['days_remaining'] <= 90)])
                st.warning(f"Warning (31-90 days): {warning_loans}")
                
            with status_cols[2]:
                healthy_loans = len(loans_df[loans_df['days_remaining'] > 90])
                st.success(f"Healthy (>90 days): {healthy_loans}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Loan Distribution")
                fig = px.pie(loans_df, values='loan_amount', names='farmer_name',
                           title='Loan Amount Distribution by Farmer')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Interest vs Principal")
                fig = px.bar(loans_df, x='farmer_name',
                           y=['loan_amount', 'current_interest'],
                           title='Loan Amount vs Interest by Farmer',
                           barmode='group')
                st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Loan Timeline")
            fig = go.Figure()
            
            for _, loan in loans_df.iterrows():
                fig.add_trace(go.Bar(
                    name=loan['farmer_name'],
                    x=[loan['farmer_name']],
                    y=[(loan['end_date'] - loan['start_date']).days],
                    text=f"{loan['days_remaining']} days remaining",
                    marker_color=loan['status_color']
                ))
            
            fig.update_layout(title="Loan Duration and Days Remaining")
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("No active loans in the system. Add some loans to see the dashboard.")
    
    elif page == "Add New Loan":
        st.header("➕ Add New Loan")
        
        with st.form("add_loan_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                farmer_name = st.text_input("Farmer Name")
                father_name = st.text_input("Father's Name")
                loan_amount = st.number_input("Loan Amount (₹)", min_value=0.0)
                interest_rate = st.number_input("Annual Interest Rate (%)", min_value=0.0, max_value=100.0)
            
            with col2:
                start_date = st.date_input("Start Date")
                end_date = st.date_input("End Date")
            
            submitted = st.form_submit_button("Add Loan", use_container_width=True)
            
            if submitted:
                if end_date <= start_date:
                    st.error("End date must be after start date!")
                elif loan_amount <= 0:
                    st.error("Loan amount must be greater than 0!")
                elif not farmer_name or not father_name:
                    st.error("Farmer name and father's name are required!")
                else:
                    if add_loan(farmer_name, father_name, loan_amount, interest_rate, start_date, end_date):
                        st.success("Loan added successfully!")
                        st.balloons()
    
    elif page == "Manage Loans":
        st.header("📝 Manage Loans")
        
        loans_df = get_all_loans()
        
        if not loans_df.empty:
            st.subheader("Active Loans")
            
            # Convert dates to more readable format
            loans_df['start_date'] = loans_df['start_date'].dt.strftime('%Y-%m-%d')
            loans_df['end_date'] = loans_df['end_date'].dt.strftime('%Y-%m-%d')
            
            # Create a display DataFrame with specific columns
            display_df = loans_df[[
                'id', 
                'farmer_name', 
                'father_name',
                'loan_amount',
                'start_date',
                'end_date',
                'current_interest',
                'days_remaining'
            ]].copy()
            
            # Rename columns for better display
            display_df.columns = [
                'Loan ID',
                'Farmer Name',
                'Father\'s Name',
                'Loan Amount (₹)',
                'Start Date',
                'End Date',
                'Interest Till Date (₹)',
                'Remaining Days'
            ]
            
            # Format numeric columns
            display_df['Loan Amount (₹)'] = display_df['Loan Amount (₹)'].apply(lambda x: f'₹{x:,.2f}')
            display_df['Interest Till Date (₹)'] = display_df['Interest Till Date (₹)'].apply(lambda x: f'₹{x:,.2f}')
            
            # Apply color coding based on remaining days
            def color_remaining_days(val):
                if val <= 30:
                    return 'color: red'
                elif val <= 90:
                    return 'color: orange'
                return 'color: green'
            
            # Display the styled table
            st.dataframe(
                display_df.style.applymap(
                    color_remaining_days,
                    subset=['Remaining Days']
                ),
                use_container_width=True
            )
            
            st.subheader("Loan Actions")
            
            tab1, tab2 = st.tabs(["Update Loan", "Delete Loan"])
            
            with tab1:
                col1, col2 = st.columns(2)
                with col1:
                    loan_id = st.selectbox("Select Loan to Update",
                                         loans_df['id'].tolist(),
                                         format_func=lambda x: f"Loan #{x} - {loans_df[loans_df['id'] == x]['farmer_name'].iloc[0]}")
                    new_end_date = st.date_input("New End Date")
                with col2:
                    update_reason = st.text_area("Reason for Update")
                    if st.button("Update End Date", use_container_width=True):
                        if update_loan_end_date(loan_id, new_end_date, update_reason):
                            st.success("Loan end date updated successfully!")
                            st.experimental_rerun()
            
            with tab2:
                col1, col2 = st.columns(2)
                with col1:
                    delete_loan_id = st.selectbox("Select Loan to Delete",
                                                loans_df['id'].tolist(),
                                                format_func=lambda x: f"Loan #{x} - {loans_df[loans_df['id'] == x]['farmer_name'].iloc[0]}",
                                                key="delete_loan")
                with col2:
                    delete_reason = st.text_area("Reason for Deletion")
                    if st.button("Delete Loan", use_container_width=True):
                        if delete_loan(delete_loan_id, delete_reason):
                            st.success("Loan deleted successfully!")
                            st.experimental_rerun()
        else:
            st.info("No active loans to manage.")
    
    elif page == "Loan History":
        st.header("📜 Loan History")
        
        history_df = get_loan_history()
        
        if not history_df.empty:
            history_df['action_timestamp'] = pd.to_datetime(history_df['action_timestamp'])
            
            col1, col2 = st.columns(2)
            with col1:
                selected_actions = st.multiselect(
                    "Filter by Action",
                    options=history_df['action'].unique(),
                    default=history_df['action'].unique()
                )
            
            with col2:
                selected_farmers = st.multiselect(
                    "Filter by Farmer",
                    options=history_df['farmer_name'].unique(),
                    default=history_df['farmer_name'].unique()
                )
            
            filtered_df = history_df[
                (history_df['action'].isin(selected_actions)) &
                (history_df['farmer_name'].isin(selected_farmers))
            ]
            
            for idx, row in filtered_df.iterrows():
                with st.container():
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        st.write(row['action_timestamp'].strftime('%Y-%m-%d %H:%M'))
                    with col2:
                        action_colors = {
                            'CREATE': 'success',
                            'UPDATE': 'warning',
                            'DELETE': 'error'
                        }
                        st.markdown(
                            f"**{row['farmer_name']}** (s/o {row['father_name']}) - "
                            f":{action_colors[row['action']]}: {row['action']}\n\n"
                            f"{row['details']}"
                        )
        else:
            st.info("No loan history available.")
    
    elif page == "Analytics":
        st.header("📈 Advanced Analytics")
        
        loans_df = get_all_loans()
        
        if not loans_df.empty:
            # Monthly Interest Analysis
            st.subheader("Monthly Interest Analysis")
            col1, col2 = st.columns(2)
            
            with col1:
                monthly_interest = loans_df.copy()
                monthly_interest['monthly_interest'] = monthly_interest.apply(
                    lambda x: x['loan_amount'] * (x['interest_rate']/100) / 12,
                    axis=1
                )
                
                fig = px.bar(
                    monthly_interest,
                    x='farmer_name',
                    y='monthly_interest',
                    title='Monthly Interest Accrual by Farmer',
                    labels={'monthly_interest': 'Monthly Interest (₹)'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Loan Duration Analysis
                loans_df['loan_duration'] = (loans_df['end_date'] - loans_df['start_date']).dt.days
                fig = px.scatter(
                    loans_df,
                    x='loan_amount',
                    y='loan_duration',
                    size='interest_rate',
                    color='farmer_name',
                    title='Loan Amount vs Duration',
                    labels={
                        'loan_amount': 'Loan Amount (₹)',
                        'loan_duration': 'Duration (Days)',
                        'interest_rate': 'Interest Rate (%)'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Risk Analysis
            st.subheader("Risk Analysis")
            risk_cols = st.columns(3)
            
            with risk_cols[0]:
                high_risk = len(loans_df[loans_df['days_remaining'] <= 30])
                high_risk_amount = loans_df[loans_df['days_remaining'] <= 30]['total_amount'].sum()
                st.metric(
                    "High Risk Loans (≤30 days)",
                    f"{high_risk}",
                    f"₹{high_risk_amount:,.2f}"
                )
            
            with risk_cols[1]:
                medium_risk = len(loans_df[(loans_df['days_remaining'] > 30) & (loans_df['days_remaining'] <= 90)])
                medium_risk_amount = loans_df[(loans_df['days_remaining'] > 30) & (loans_df['days_remaining'] <= 90)]['total_amount'].sum()
                st.metric(
                    "Medium Risk Loans (31-90 days)",
                    f"{medium_risk}",
                    f"₹{medium_risk_amount:,.2f}"
                )
            
            with risk_cols[2]:
                low_risk = len(loans_df[loans_df['days_remaining'] > 90])
                low_risk_amount = loans_df[loans_df['days_remaining'] > 90]['total_amount'].sum()
                st.metric(
                    "Low Risk Loans (>90 days)",
                    f"{low_risk}",
                    f"₹{low_risk_amount:,.2f}"
                )
            
            # Farmer-wise Analysis
            st.subheader("Farmer-wise Analysis")
            farmer_analysis = loans_df.groupby('farmer_name').agg({
                'loan_amount': 'sum',
                'current_interest': 'sum',
                'total_amount': 'sum',
                'father_name': 'first'  # Include father's name in analysis
            }).reset_index()
            
            # Display farmer-wise table
            st.dataframe(
                farmer_analysis.style.format({
                    'loan_amount': '₹{:,.2f}',
                    'current_interest': '₹{:,.2f}',
                    'total_amount': '₹{:,.2f}'
                }),
                use_container_width=True
            )
            
            # Export Data
            st.subheader("Export Data")
            if st.button("Download Loan Report"):
                # Prepare export data
                export_df = loans_df.copy()
                export_df['start_date'] = export_df['start_date'].dt.strftime('%Y-%m-%d')
                export_df['end_date'] = export_df['end_date'].dt.strftime('%Y-%m-%d')
                
                csv = export_df.to_csv(index=False)
                st.download_button(
                    label="Click to Download",
                    data=csv,
                    file_name=f"loan_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No active loans available for analysis.")

if __name__ == "__main__":
    main()
    