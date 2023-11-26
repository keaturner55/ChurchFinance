import os, sys
from intuitlib.client import AuthClient
from quickbooks import QuickBooks
import pandas as pd
import calendar
import yaml
import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')


SRC_DIR = Path(__file__).parents[0]


def get_auth_client(client_id, client_secret, refresh_token, company_id):
    auth_client = AuthClient(
            client_id=client_id,
            client_secret=client_secret,
            access_token=None,
            environment='production',
            redirect_uri='https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl',
        )
    client = QuickBooks(
            auth_client=auth_client,
            refresh_token=refresh_token,
            company_id=company_id,
        )
    return client


def proc_rows(rows:list, category:str = "", level:int=0):
    row_list = []
    for row in rows:
        if "Header" in row:
            header_col = row['Header']['ColData'][0]['value']
            if category == "":
                current_category = header_col
            else:
                current_category = f"{category}:{header_col}"
            row_list.extend(proc_rows(row['Rows']['Row'], category = current_category, level = level+1))
        else:
            col_data = row['ColData']
            if len(col_data)==len(cols):
                cur_row = {cols[i]:col_data[i]['value'] for i in range(len(cols))}
                cur_row.update({"category":category})
                cur_row.update({"category_level":level})
                row_list.append(cur_row)
    return row_list

def pre_proc_df(qbdf):
    # preprocessing/data manipulation
    qbdf['item'] = qbdf['category'].apply(lambda x: x.split(':')[-1])
    qbdf['Amount'] = qbdf['Amount'].astype(float)
    qbdf['Account_Type'] = qbdf['category'].apply(lambda x: x.split(':')[0])
    return qbdf



def load_yaml(yaml_file:str):
    with open(yaml_file, "r") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logger.error()
            print(exc)
            sys.exit(1)


credentials = load_yaml(os.path.join(SRC_DIR,"config","credential.yaml"))

if __name__=="__main__":
    year = 2023
    print("Generating auth client")
    client = get_auth_client(credentials['client_id'],credentials['client_secret'],
                             credentials['refresh_token'],credentials['company_id'])
    df_list = []
    for month in range(1,13):
        days = calendar.monthrange(year,month)[1]
        month_name = calendar.month_name[month]
        print(f"Grabbing report details for {month_name}")
        json_resp = client.get_report("ProfitAndLossDetail", {"start_date":f"{year}-{month}-01", "end_date":f"{year}-{month}-{days}"})
        cols = [i["ColTitle"] for i in json_resp['Columns']['Column']]
        report_info = json_resp['Header']
        if "Row" not in json_resp["Rows"]:
            print("No data for this month...skipping")
            continue
        row_list = proc_rows(json_resp["Rows"]["Row"][0]['Rows']['Row'])
        df_list.append(pd.DataFrame(row_list))

    qbdf = pd.concat(df_list)
    qbdf = pre_proc_df(qbdf)
    dbname = "quickbooks.db"
    dbpath = os.path.join(SRC_DIR,"db",dbname)
    conn = sqlite3.connect(dbpath) 
    print(f"Saving results to sqlite DB: {dbpath}")
    qbdf.to_sql('categorized_items', conn, if_exists='replace', index=False)



