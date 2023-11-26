#!/usr/bin/env python
# coding: utf-8

# In[8]:


import panel as pn
pn.extension('tabulator')
import hvplot.pandas
import pandas as pd
import sqlite3
import os
from pathlib import Path
import calendar
from dateutil import parser

SRC_DIR = Path(__file__).parent


def get_db_data(db_file):
    conn = sqlite3.connect(db_file)
    qbdf = pd.read_sql("select * from categorized_items", conn)
    
    return qbdf

def get_budget_data(budget_csv):
    
    budgetdf = pd.read_csv(budget_csv)
    
    return budgetdf


def merge_budget_expenses(budgetdf, expenses):
    # merge qb items with budget items
    item_totals = expenses.groupby('item').aggregate({"Amount":"sum","Date":'count'}).reset_index()
    item_totals.columns = ['item','Amount','Transactions']
    all_totals = pd.merge(budgetdf,item_totals, left_on='QB_Item', right_on="item", how = 'left')
    subcategory_totals = all_totals.groupby("Subcategory").aggregate({"Budget":"sum","Amount":"sum"}).reset_index()
    subcategory_totals.reset_index(drop = True, inplace=True)
    return subcategory_totals


def check_fields(qbdf,budgetdf):
    # preprocessing/data manipulation
    budget_items = budgetdf['QB_Item'].unique()
    expenses = qbdf.loc[qbdf['Account_Type']=="Expenses"]
    
    # check for unrecognized types and categories
    types = qbdf["Transaction Type"].unique()
    expected_types = ['Check','Expense','Deposit']
    for t in types:
        if t not in expected_types:
            print(f"Warning: {t} not a recognized type")

    # expenses not in a budget category will not show up in the bugdet bar plots
    # BUT they will show up in profit/loss calculations
    for item in expenses['item'].unique():
        if item not in budget_items:
            print(f"Warning: {item} not in any budget category.. consider\
                  generating specific report.")
            

def generate_month_plot(year, month, qbdf, budgetdf):
    
    month_name = calendar.month_name[month]
    days = calendar.monthrange(year,month)[1]
    print(f"Generating plot for {month_name}")
    interval = (f"{year}-{month}-01",f"{year}-{month}-{days}")
    interval_dates = (parser.parse(interval[0]),parser.parse(interval[1]))
    
    # trim all dataframes
    qbdf = qbdf.loc[(qbdf['Date']>=interval_dates[0]) &
                  (qbdf['Date']<=interval_dates[1])]
    
    if len(qbdf)==0:
        return pn.pane.Markdown("**No Data**")
    
    expenses = qbdf.loc[qbdf['Account_Type']=="Expenses"]
    income = qbdf.loc[qbdf['Account_Type']=="Income"]
    
    subcategory_totals = merge_budget_expenses(budgetdf, expenses)
    
    budget_bar = subcategory_totals.hvplot.bar(x='Subcategory',
                                           y=['Budget','Amount'],
                                          ylabel="Expenses",
                                          rot=90,
                                          title = month_name,
                                          width = 800,
                                          height = 550,
                                          legend="top_right").opts(multi_level=False,
                                                                  
                                                                  fontsize={
                                                                    'title': 15, 
                                                                    'labels': 14, 
                                                                    'xticks': 10, 
                                                                    'yticks': 10})
    
    table_widget = pn.widgets.Tabulator(subcategory_totals)
    
    return budget_bar


def render_month_pane(element_list):
    pn.template.FastListTemplate(element_list)

    return

def main():
    
    # QB data stored in the DB-comes from qb_etl.py
    dbname = "quickbooks.db"
    dbpath = os.path.join(SRC_DIR,"db",dbname)
    print(f"Getting QuickBooks data from database: {dbpath}")
    qbdf = get_db_data(dbpath)
    qbdf['Date'] = pd.to_datetime(qbdf['Date'])
    
    budget_csv = os.path.join(SRC_DIR,'config','qb_to_budget_map.csv')
    print(f"Getting budget data from file: {budget_csv}")
    budgetdf = get_budget_data(budget_csv)
    
    check_fields(qbdf, budgetdf)
    
    #total_expense = expenses['Amount'].sum()
    #total_income = income['Amount'].sum()
    #net_profit = total_income - total_expense
    
    print("Generating plot")
    month_options = pn.widgets.Select(name="Month Selection",
                                      options={"January":1,"Februrary":2,"March":3,
                                               "April":4,"May":5,"June":6,"July":7,"August":8,
                                               "Septempter":9,"October":10,"November":11,
                                               "December":12}
                                      )
    init_plot = pn.bind(generate_month_plot,2023,month_options, qbdf, budgetdf)
    #init_table = pn.bind()
    row = pn.Row(init_plot)
    template = pn.template.FastListTemplate(title = "Budget Reports",
                                            main = [month_options,row])
    template.servable(target='main')


main()




