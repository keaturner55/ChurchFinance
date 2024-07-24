import panel as pn
import param
pn.extension('tabulator')
import pandas as pd
import sqlite3
import os
from pathlib import Path
import calendar
from dateutil import parser
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource
from jinja2 import Environment, FileSystemLoader
import math
import numpy as np


SRC_DIR = Path(__file__).parent

@pn.cache
def get_db_data(db_file):
    conn = sqlite3.connect(db_file)
    qbdf = pd.read_sql("select * from categorized_items", conn)
    
    return qbdf

@pn.cache
def get_budget_data(budget_csv):
    
    budgetdf = pd.read_csv(budget_csv)
    
    return budgetdf

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

@pn.cache            
def merge_budget_expenses(budgetdf, expenses):
    # merge qb items with budget items
    item_totals = expenses.groupby('item').aggregate({"Amount":"sum","Date":'count'}).reset_index()
    item_totals.columns = ['item','Amount','Transactions']
    all_totals = pd.merge(budgetdf,item_totals, left_on='QB_Item', right_on="item", how = 'left')
    subcategory_totals = all_totals.groupby("Subcategory").aggregate({"Budget":"sum","Amount":"sum"}).reset_index()
    subcategory_totals.reset_index(drop = True, inplace=True)
    return subcategory_totals

@pn.cache
def get_month_data(year, month, qbdf):
    month_name = calendar.month_name[month]
    days = calendar.monthrange(year,month)[1]
    print(f"Generating plot for {year}-{month_name}")
    interval = (f"{year}-{month}-01",f"{year}-{month}-{days}")
    interval_dates = (parser.parse(interval[0]),parser.parse(interval[1]))
    
    # trim all dataframes
    month_df = qbdf.loc[(qbdf['Date']>=interval_dates[0]) &
                  (qbdf['Date']<=interval_dates[1])]
    
    return month_df


class FinanceDashboard(param.Parameterized):
    """
    Main render view class for dashboard
    """
    year = param.ObjectSelector(default = 2024, label = "Year Selection", objects = [2023,2024])
    month = param.ObjectSelector(default = 2, label="Month Selection",
                                      objects={"January":1,"Februrary":2,"March":3,
                                               "April":4,"May":5,"June":6,"July":7,"August":8,
                                               "Septempter":9,"October":10,"November":11,
                                               "December":12})

    # dataframes
    qb_df = param.DataFrame()
    month_df = param.DataFrame()
    budget_df = param.DataFrame()
    subcategory_totals = param.DataFrame()
    expenses = param.DataFrame()
    income = param.DataFrame()

    def __init__(self, qb_df = None, budget_df = None, **params):
        super().__init__(**params)

        self.qb_df = qb_df
        self.budget_df = budget_df
        self.parameter_pane = pn.Param(self,parameters = ['year', 'month'],
                                       default_layout=pn.Column, show_name=False)
        self.month=1
        

    @pn.depends("year", "month", watch=True)
    def generate_month_report(self):
        self.month_df = get_month_data(self.year, self.month, self.qb_df)
        self.expenses = self.month_df.loc[self.month_df['Account_Type']=="Expenses"]
        self.income = self.month_df.loc[self.month_df['Account_Type']=="Income"]
        self.subcategory_totals = merge_budget_expenses(self.budget_df, self.expenses)
    
    @pn.depends('subcategory_totals')
    def gen_bar_plot(self):
        if self.subcategory_totals is None or len(self.subcategory_totals)==0:
            return pn.pane.Markdown("No Data")
        month_name = calendar.month_name[self.month]
        tempdf = self.subcategory_totals.copy()
        tempdf["RG"] = np.where((tempdf.Amount > tempdf.Budget), 'red', 'green')
        source = ColumnDataSource(tempdf)
        p = figure(x_range=tempdf['Subcategory'],title=month_name, height=500)
        p.yaxis.axis_label = 'Amount'
        p.xaxis.major_label_orientation=math.pi/4
        p.xaxis.major_label_text_font_size = "12pt"
        p.vbar(x = 'Subcategory', top='Amount', source=source, width=.5, legend_label="Amount", color = 'RG')
        p.dash(x='Subcategory',y='Budget', source=source, legend_label="Budget", color='black', size=23, line_width=3)
        return pn.pane.Bokeh(p, height=500, sizing_mode='stretch_width')
    
    @pn.depends('expenses')
    def gen_table(self):
        if self.expenses is None or len(self.expenses)==0:
            return pn.pane.Markdown("## No Data")
        item_totals = self.expenses.groupby('item').aggregate({"Amount":"sum","Date":'count'}).reset_index()
        item_totals.columns = ['item','Amount','Transactions']
        item_totals["Transactions"] = item_totals["Transactions"].apply(int)
        all_totals = pd.merge(self.budget_df,item_totals, left_on='QB_Item', right_on="item", how = 'left')
        report_totals = all_totals[~all_totals['item'].isin(['Lead Pastor','Associate Pastor'])][['Item', 'Transactions','Budget', 'Amount']].sort_values(['Amount'],ascending=False)
        expense_table = pn.widgets.Tabulator(report_totals, height=500, page_size=10,
                                             pagination='remote',
                                            show_index=False, theme='bootstrap',
                                            layout='fit_columns',sizing_mode='stretch_width')
        return expense_table

    @pn.depends('expenses')
    def get_expenses(self):
        if self.expenses is None or len(self.expenses)==0:
            return pn.pane.Markdown("## No Data")
        else:
            return pn.pane.HTML(f"<h1> ${round(self.expenses['Amount'].sum(),2)} </h2>")
        
    @pn.depends('expenses')
    def get_transactions(self):
        if self.expenses is None or len(self.expenses)==0:
            return pn.pane.HTML("<h1> No Data </h1>")
        else:
            mdf = self.month_df[["Date","Account_Type","category","item","Memo/Description","Amount"]]
            mdf.columns = ["Date","Type","Category","Item","Memo","Amount"]

            return pn.widgets.Tabulator(mdf, height=700, show_index=False,
                                        theme='bootstrap', layout='fit_columns',
                                        sizing_mode='stretch_width', header_filters=True)
        
    @pn.depends('income')
    def get_income(self):
        if self.income is None or len(self.income)==0:
            return pn.pane.HTML("<h1> No Data </h1>")
        else:
            return pn.pane.HTML(f"<h1> ${round(self.income['Amount'].sum(),2)} </h1>")
        
    @pn.depends('income')
    def get_net_profit(self):
        if self.month_df is None or len(self.month_df)==0:
            return pn.pane.HTML("<h1> No Data </h1>")
        else:
            net = self.income['Amount'].sum() - self.expenses['Amount'].sum()
            if net>=0:
                return pn.pane.HTML(f"<h1 style=\"color: green\"> ${round(net,2)} </h1>")
            else:
                return pn.pane.HTML(f"<h1 style=\"color: red\"> ${round(net,2)} </h1>")

def main():
    # QB data stored in the DB-comes from qb_etl.py
    dbname = "quickbooks.db"
    dbpath = os.path.join(SRC_DIR,"db",dbname)
    qbdf = get_db_data(dbpath)
    qbdf['Date'] = pd.to_datetime(qbdf['Date'])

    budget_csv = os.path.join(SRC_DIR,'config','qb_to_budget_map.csv')
    budgetdf = get_budget_data(budget_csv)

    check_fields(qbdf, budgetdf)
    env = Environment(loader=FileSystemLoader('.'))
    template = pn.Template(env.get_template('template.html'))

    dashboard = FinanceDashboard(qbdf, budgetdf)
    template.add_panel('parameters',dashboard.parameter_pane)
    template.add_panel('total_expenses',dashboard.get_expenses)
    template.add_panel('total_income',dashboard.get_income)
    template.add_panel('net_profit', dashboard.get_net_profit)
    template.add_panel('barplot',dashboard.gen_bar_plot)
    template.add_panel('table', dashboard.gen_table)
    template.add_panel('transactions',dashboard.get_transactions)
    template.servable()


main()






