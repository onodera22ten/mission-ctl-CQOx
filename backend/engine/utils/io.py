import os, pandas as pd
DATA_DIR=os.environ.get('CQO_DATA','./data'); os.makedirs(DATA_DIR, exist_ok=True)
def write_csv(dataset_id:str, raw:bytes): open(f"{DATA_DIR}/{dataset_id}.csv",'wb').write(raw)
def read_df(dataset_id:str)->pd.DataFrame: return pd.read_csv(f"{DATA_DIR}/{dataset_id}.csv")
