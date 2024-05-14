#!/usr/bin/env python3

# Copyright 2022-23 https://www.math-crypto.com -- GNU General Public License

# pip3 install substrate-interface
from substrateinterface import SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException
import sys
import pandas as pd
import numpy as np
from pathlib import Path
import logging
import time
import random

PATH_ONCHAIN = Path.cwd() / "../onchain"

def get_on_chain_era_points(chain):
    """
    Get a dataframe of the on chain era points over the last 84 eras (kusama) for all validators.
    The points can be NaN; find them by df['points'].isnull().

    If the API complains about too many requests, we can also fetch only the new eras based on 
    what is in "on_chain_era_points.feather".
    """
    # TODO put in .env
    if chain=='kusama':
        url = "wss://rpc.ibp.network/kusama"
    elif chain=='polkadot':    
        url = "wss://rpc.ibp.network/polkadot"

    try:
        substrate = SubstrateInterface(url=url)
    except ConnectionRefusedError:
        sys.exit("⚠️ Remote RPC server didn't respond")

    result = substrate.query(module='Staking', storage_function='ActiveEra')
    cur_era = result['index'].decode()
    cur_time = result['start'].decode()

    era_start_file = PATH_ONCHAIN / chain / "on_chain_era_start.feather"
    if Path.exists(era_start_file):
        df_start = pd.read_feather(era_start_file)        
        if not cur_era in df_start["era"].values:
            df_start = pd.concat([df_start, pd.DataFrame({"era": [cur_era], "start": [cur_time]})]).reset_index(drop=True)            
            df_start.to_feather(era_start_file)
    else:
        df_start = pd.DataFrame({"era": [cur_era], "start": [cur_time]})    
        df_start.to_feather(era_start_file)
           
    dfs = []    
    era = cur_era    
    logging.info(f"Fetch started from era {era}. Should be finished in < 1 min.")
    while True:        
        result = substrate.query(module='Staking', storage_function='ErasRewardPoints', params=[era])
        if result['total'] == 0:
            if era == cur_era:  # The current era might now have started yet?          
                era = era - 1            
            else:
                start_era = era+1
                logging.info(f"Fetch ended at era {era}")
                break
                
        else:            
            new_list = []
            for i in result['individual']:
                new_list.append([i[0].decode(), i[1].decode()])
            
            df_i = pd.DataFrame.from_records(new_list, columns=['address', 'points'])
            df_i['era'] = era
            dfs.append(df_i)
            era = era - 1        

    df_pts = pd.concat(dfs).reset_index(drop=True)

    start_era = np.min(df_pts['era'])
    end_era = np.max(df_pts['era'])
    df_pts.to_feather(PATH_ONCHAIN / chain / "all" / f"from_{start_era}_to_{end_era}.feather")
    
    return df_pts


def get_on_chain_activity(chain):
    if chain == 'kusama':
        url = "wss://rpc.ibp.network/kusama"
    elif chain == 'polkadot':
        url = "wss://rpc.ibp.network/polkadot"
    else:
        raise ValueError("Unsupported chain. Use 'polkadot' or 'kusama'.")

    # Define the WebSocket endpoint
    substrate = SubstrateInterface(
        url=url,
        type_registry_preset=chain
    )

    # Path to the Feather file
    feather_path = PATH_ONCHAIN / chain / 'eras_activity.feather'
    feather_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing data
    if feather_path.exists():
        df_existing = pd.read_feather(feather_path)
        if 'index' not in df_existing.columns:
            df_existing = pd.DataFrame(columns=['index'])
        else:
            existing_eras = df_existing.columns[1:].astype(str).tolist()
            df_existing.set_index('index', inplace=True)
    else:
        df_existing = pd.DataFrame(columns=['index'])
        existing_eras = []

    try:
        # Fetch the active era
        active_era = substrate.query(
            module='Staking',
            storage_function='ActiveEra'
        ).value['index']

        # Define the range of eras to check (last 200 eras)
        eras_to_check = list(range(active_era - 200, active_era+1))

        # Eras that need to be fetched
        missing_eras = [era for era in eras_to_check if str(era) not in existing_eras]

        if not missing_eras:
            print("No new eras to fetch.")
            return

        # Initialize a set to collect all unique validator addresses
        validators_set = set()

        # Dictionary to hold the activity data
        activity_data = {era: {} for era in missing_eras}

        for era in missing_eras:
            # Fetch the era stakers overview for the given era
            era_stakers_overview = substrate.query_map(
                module='Staking',
                storage_function='ErasStakersOverview',
                params=[era]
            )

            # Collect active validators in this era
            for record in era_stakers_overview:
                validator = record[0].value
                validators_set.add(validator)
                activity_data[era][validator] = 1

        # Create a DataFrame to store the new activity data
        validators_list = sorted(validators_set.union(df_existing.index))
        df_new = pd.DataFrame(index=validators_list, columns=[str(era) for era in missing_eras]).fillna(0)

        # Update the DataFrame with the actual activity data
        for era, validators in activity_data.items():
            for validator, active in validators.items():
                df_new.at[validator, str(era)] = active

        # Combine with existing data
        df_combined = pd.concat([df_existing, df_new], axis=1).fillna(0)

        # Keep only the last 200 eras
        if len(df_combined.columns) > 200:
            df_combined = df_combined.iloc[:, -200:]

        # Save to Feather file
        df_combined.reset_index(inplace=True)
        df_combined.to_feather(feather_path)

        # Print the resulting DataFrame

    except SubstrateRequestException as e:
        print(f"An error occurred: {e}")




# def merge_era_points(df_pts, chain):
#     """
#     Join the given df into the dataframe stored on disk.

#     ERROR: Does not take the new values! See inclusion_score.ipynb for better merge method
#     """
#     df_all = pd.read_feather(Path.cwd() / chain / "on_chain_era_points.feather")

#     df_tmp = df_all.merge(df_pts, how="outer", on=["address", "era"])
#     inconsistent = df_tmp[df_tmp['points_x']!=df_tmp['points_y']].dropna()    
#     if len(inconsistent)>0:
#         print("Inconsistent data was found in merge of on chain era points.")
#         print(inconsistent)
#         print("Keeping the old value (points_x).")

#     print(f"Original length = {len(df_all)}. New length = {len(df_tmp)}")
#     print(f"  Number of added rows = {len(df_tmp) - len(df_all)}")
    
#     df_all = df_tmp.drop(columns="points_y").rename(columns={"points_x": "points"})
#     df_all.to_feather(Path.cwd() / chain / "on_chain_era_points.feather")

#     eras = df_all['era'].unique()
#     eras = np.sort(eras)
#     diff = eras[1:]-eras[:-1]
#     if sum(diff!=1) > 0:
#         print("Warning: there is a gap in the eras.")

#     return df_all
    


def main_loop():       
    while(True):
        get_on_chain_activity('kusama')
        time.sleep((5.0+random.random())*2)
        get_on_chain_era_points('kusama')                
        time.sleep((5.0+random.random())*2)

        get_on_chain_activity('polkadot')
        time.sleep((5.0+random.random())*2)
        get_on_chain_era_points('polkadot')
        time.sleep((5.0+random.random())*2)
        
        time.sleep(4*60*60.0 + (5.0+random.random())*2) # every 4h

                
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main_loop()


