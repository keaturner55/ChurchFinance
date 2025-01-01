import dash
from dash import dcc, html
from dash import dash_table
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash.dependencies import Input, Output
import pandas as pd
import plotly.express as px
import calendar
from dateutil import parser
from datetime import datetime
import sqlite3
import os
from pathlib import Path
import numpy as np

# Load data functions
def get_db_data(db_file):
    conn = sqlite3.connect(db_file)
    qbdf = pd.read_sql("select * from categorized_items", conn)
    return qbdf

def get_budget_data(budget_csv):
    budgetdf = pd.read_csv(budget_csv)
    return budgetdf

def calc_ytd_totals(qbdf, year):
    # Your existing calculation logic for YTD
    expenses = qbdf.loc[qbdf['Account_Type'] == "Expenses"]
    income = qbdf.loc[qbdf['Account_Type'] == "Income"]
    start_time = parser.parse(f'{year}-01-01')
    end_time = parser.parse(f'{year+1}-01-01')

    period_expenses = expenses.loc[(expenses['Date'] >= start_time)]
    period_income = income.loc[(income['Date'] >= start_time)]

    expense_per_day = period_expenses['Amount'].sum() / (expenses['Date'].max() - start_time).days
    income_per_day = period_income['Amount'].sum() / (income['Date'].max() - start_time).days

    remaining_expenses = expense_per_day * (end_time - expenses['Date'].max()).days
    remaining_income = income_per_day * (end_time - income['Date'].max()).days

    projected_expense_total = remaining_expenses + expenses['Amount'].sum()
    projected_income_total = remaining_income + income['Amount'].sum()

    return expenses, income, projected_expense_total, projected_income_total

# Data and layout initialization
SRC_DIR = Path(__file__).parent
dbname = "quickbooks.db"
dbpath = os.path.join(SRC_DIR, "db", dbname)
qbdf = get_db_data(dbpath)
qbdf['Date'] = pd.to_datetime(qbdf['Date'])

budget_csv = os.path.join(SRC_DIR, 'config', 'qb_to_budget_map.csv')
budgetdf = get_budget_data(budget_csv)

ytd_expenses, ytd_income, ytd_projected_expenses, ytd_projected_income = calc_ytd_totals(qbdf, 2024)

# Initialize Dash app
app = dash.Dash(__name__)

# Layout of the Dashboard
app.layout = dbc.Container([
    # Dropdown for Year and Month selection
    dbc.Row([
        dbc.Col(dcc.Dropdown(id='year-dropdown',
                             options=[{'label': str(year), 'value': year} for year in [2023, 2024]],
                             value=2024,
                             style={'width': '100%'}),
                width=6),
        dbc.Col(dcc.Dropdown(id='month-dropdown',
                             options=[{'label': month, 'value': idx} for idx, month in enumerate(calendar.month_name) if month],
                             value=2,
                             style={'width': '100%'}),
                width=6)
    ], style={'padding': 20}),

    # Display Total Expenses and Income
    dbc.Row([
        dbc.Col(html.Div(id='total-expenses'), width=4),
        dbc.Col(html.Div(id='total-income'), width=4),
        dbc.Col(html.Div(id='net-profit'), width=4),
    ], style={'padding': 20}),

    # Bar Plot of Subcategory Expenses vs. Budget
    dbc.Row([
        dbc.Col(dcc.Graph(id='subcategory-bar-plot'), width=12)
    ], style={'padding': 20}),

    # Transactions Table
    dbc.Row([
        dbc.Col(dag.AgGrid(id='transactions-table'), width=12)
    ], style={'padding': 20}),

    # YTD Report Chart
    dbc.Row([
        dbc.Col(dcc.Graph(id='ytd-line-chart'), width=12)
    ], style={'padding': 20}),

    # YTD Table
    dbc.Row([
        dbc.Col(dag.AgGrid(id='ytd-table'), width=12)
    ], style={'padding': 20}),

    # Projected Expenses and Income
    dbc.Row([
        dbc.Col(html.Div(id='projected-expenses-income'), width=12)
    ], style={'padding': 20}),
], fluid=True)

# Callbacks
@app.callback(
    [Output('total-expenses', 'children'),
     Output('total-income', 'children'),
     Output('net-profit', 'children'),
     Output('subcategory-bar-plot', 'figure'),
     Output('transactions-table', 'rowData'),
     Output('ytd-line-chart', 'figure'),
     Output('ytd-table', 'rowData'),
     Output('projected-expenses-income', 'children')],
    [Input('year-dropdown', 'value'),
     Input('month-dropdown', 'value')]
)
def update_dashboard(year, month):
    # Filter the month data
    month_name = calendar.month_name[month]
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)
    
    # Filter the data for the selected month
    month_df = qbdf[(qbdf['Date'] >= start_date) & (qbdf['Date'] < end_date)]
    expenses = month_df[month_df['Account_Type'] == 'Expenses']
    income = month_df[month_df['Account_Type'] == 'Income']

    # Calculate totals
    total_expenses = round(expenses['Amount'].sum(), 2)
    total_income = round(income['Amount'].sum(), 2)
    net_profit = round(total_income - total_expenses, 2)

    # Create bar plot for subcategories
    subcategory_totals = expenses.groupby('item')['Amount'].sum().reset_index()
    subcategory_totals = subcategory_totals.sort_values('Amount', ascending=False)

    bar_fig = px.bar(subcategory_totals, x='item', y='Amount', title=f'{month_name} Expenses vs. Budget')
    bar_fig.update_layout(xaxis_tickangle=-45)

    # Transaction table
    transactions_data = month_df[['Date', 'Account_Type', 'category', 'item', 'Memo/Description', 'Amount']].to_dict('records')

    # YTD line chart
    ytd_fig = px.line(x=ytd_expenses['Date'], y=ytd_expenses['Amount'].cumsum(), title="YTD Expenses vs Income")
    ytd_fig.add_scatter(x=ytd_income['Date'], y=ytd_income['Amount'].cumsum(), mode='lines', name="Income")

    # YTD Table
    ytd_table_data = pd.merge(budgetdf, ytd_expenses.groupby('item')['Amount'].sum().reset_index(), 
                              left_on='QB_Item', right_on='item', how='left')[['Item', 'Budget', 'Amount']]

    # Projected expenses and income
    projected_income = round(ytd_projected_income, 2)
    projected_expenses = round(ytd_projected_expenses, 2)
    projected_net_profit = round(projected_income - projected_expenses, 2)

    projected_text = f"Projected Income: ${projected_income}\nProjected Expenses: ${projected_expenses}\nProjected Net Profit: ${projected_net_profit}"

    return (f"Total Expenses: ${total_expenses}",
            f"Total Income: ${total_income}",
            f"Net Profit: ${net_profit}",
            bar_fig,
            transactions_data,
            ytd_fig,
            ytd_table_data.to_dict('records'),
            projected_text)

# Run the server
if __name__ == '__main__':
    app.run_server(debug=True)
