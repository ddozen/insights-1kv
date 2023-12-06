#!/usr/bin/env python3

# Copyright 2022-2023 https://www.math-crypto.com -- GNU General Public License

from os import lseek
import requests
import pandas
import numpy
import random
from pathlib import Path
import time
import logging

TIME_DELTA_SEC = 1*60*60 # 1 hour
PATH_JSON  = Path.cwd() / "../1kv_json"

def dump(url, feather_path):    
    files = list(feather_path.glob("*.feather"))

    if files:
        latest_file = max([f for f in files], key=lambda item: item.stat().st_ctime)
        latest_time = int(latest_file.stem)
        delta = time.time() - latest_time
        print(delta)
        if(delta < TIME_DELTA_SEC):
            logging.info("Recent dump exist")
            return

    try:
        req = requests.get(url=url, timeout=10)
    except requests.exceptions.ReadTimeout:
        logging.info("Timeout")
        return

    print(req.status_code)
    if req.status_code != 200:
        logging.info("Website did not return valid file")
        return
    
    # TODO: Write JSON

    df = pandas.json_normalize(req.json())
    # Contains integers and 'None' field. Save as string for now
    df['openGovDelegations.track'] = df['openGovDelegations.track'].astype('str')
    
    cur_time = int(time.time())
    file_name = str(cur_time) + ".feather"
    df.to_feather(feather_path / file_name)
        
    logging.info("Wrote JSON")        



def main_loop():    
    kusama_url = "https://kusama.w3f.community/candidates"
    polkadot_url = "https://polkadot.w3f.community/candidates"

    feather_path_ksm = PATH_JSON /  "kusama"
    feather_path_dot = PATH_JSON /  "polkadot"
    
    while(True):                        
        dump(kusama_url, feather_path_ksm)
        time.sleep((5.0+random.random())*2)
                
        dump(polkadot_url, feather_path_dot)
        time.sleep(10*60.0 + (5.0+random.random())*2)

        
        
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main_loop()
