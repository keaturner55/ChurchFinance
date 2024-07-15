import panel as pn
import param
pn.extension('tabulator')
import plotly.express as px
import pandas as pd
import sqlite3
import os
from pathlib import Path
import calendar
from dateutil import parser
import hvplot.pandas
from jinja2 import Environment, FileSystemLoader



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

    def __init__(self, qb_df = None, budget_df = None, **params):
        super().__init__(**params)

        self.qb_df = qb_df
        self.budget_df = budget_df
        self.parameter_pane = pn.Param(self,parameters = ['year', 'month'],
                                       default_layout=pn.Row, show_name=False)
        self.month=1
        

    @pn.depends("year", "month", watch=True)
    def generate_month_report(self):
        print("fire... generate month reports")
    
        self.month_df = get_month_data(self.year, self.month, self.qb_df)
        self.expenses = self.month_df.loc[self.month_df['Account_Type']=="Expenses"]
        self.subcategory_totals = merge_budget_expenses(self.budget_df, self.expenses)
    
    @pn.depends('subcategory_totals')
    def gen_bar_plot(self):
        print("fire... gen bar plot")
        if self.subcategory_totals is None or len(self.subcategory_totals)==0:
            return pn.pane.Markdown("No Data")
        month_name = calendar.month_name[self.month]
        budget_bar = self.subcategory_totals.hvplot.bar(x='Subcategory',y=['Budget','Amount'],
                                            ylabel="Expenses",
                                            rot=60,
                                            title = month_name,
                                            legend="top_right").opts(multi_level=False,
                                                                    fontsize={
                                                                        'title': 15, 
                                                                        'labels': 14, 
                                                                        'xticks': 12, 
                                                                        'yticks': 10},
                                                                    cmap=[(44,160,44),(31,119,180)])
        return budget_bar
    
    @pn.depends('expenses')
    def gen_table(self):
        if self.expenses is None or len(self.expenses)==0:
            return "No Data"
        item_totals = self.expenses.groupby('item').aggregate({"Amount":"sum","Date":'count'}).reset_index()
        item_totals.columns = ['item','Amount','Transactions']
        item_totals["Transactions"] = item_totals["Transactions"].apply(int)
        all_totals = pd.merge(self.budget_df,item_totals, left_on='QB_Item', right_on="item", how = 'left')
        report_totals = all_totals[~all_totals['item'].isin(['Lead Pastor','Associate Pastor'])][['Item', 'Transactions','Budget', 'Amount']].sort_values(['Amount'],ascending=False)
        expense_table = pn.widgets.Tabulator(report_totals, fit='stretch_width',
                                            layout='fit_data_table',
                                            show_index=False, theme='bootstrap')
        return expense_table

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
    env = Environment(loader=FileSystemLoader('.'))
    template = pn.Template(env.get_template('template.html'))

    dashboard = FinanceDashboard(qbdf, budgetdf)
    template.add_panel('parameters',dashboard.parameter_pane)
    template.add_panel('barplot',dashboard.gen_bar_plot)
    template.add_panel('table', dashboard.gen_table)
    template.servable()


main()






