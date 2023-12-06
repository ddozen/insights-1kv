#!/usr/bin/env python3

# Copyright 2022-23 https://www.math-crypto.com -- GNU General Public License

from pathlib import Path
import pandas as pd
import logging
import time
import random
import json
import pickle
from joblib import Parallel, delayed
import sys
from substrateinterface import SubstrateInterface
import os
import time

from scores_1kv import *

PATH_JSON  = Path.cwd() / "../1kv_json"
PATH_ONCHAIN = Path.cwd() / "../onchain"
PATH_NEWFIGS = Path.cwd() / "../new_figs"
PATH_INFO = Path.cwd() / "../info"
PATH_TMP = Path.cwd() / "../tmp"

NB_ERAS_TO_PROCESS = 200


def calculate_oldest_datetime(chain):
    cur_time = int(time.time()) # in seconds
    if chain=="kusama":
        # 6 hours
        secs_in_one_era = 6*60*60
    elif chain=="polkadot":
        # 1 day
        secs_in_one_era = 24*60*60
    return cur_time - NB_ERAS_TO_PROCESS * secs_in_one_era
        
    
def merge_dumps(chain):
    # 1kv json files
    logging.info("Reading 1kv json files...")
    df_1kv = read_1kv_json(PATH_JSON / chain, oldest_datetime=calculate_oldest_datetime(chain))    
    df_1kv.to_feather(PATH_TMP / chain / "df_1kv.feather")
    stash_1kv = df_1kv.stash.unique()
    pickle.dump(stash_1kv, open(PATH_TMP / chain/ "stash_1kv.p", "wb"))  
    
    # era points
    logging.info("Reading on chain files...")
    start_era_onchain = read_onchain_era_start_file(PATH_ONCHAIN / chain / "on_chain_era_start.feather")
    # Select only 1kv validators
    logging.info("--- 1 Reading on chain files...")
    df_era_reward_onchain = read_onchain_erareward_files(PATH_ONCHAIN / chain / "all" ).query("address in @stash_1kv").reset_index(drop=True)    
    logging.info("--- 2 Reading on chain files...")
    df_era_reward_onchain.to_feather(PATH_TMP / chain / "df_era_reward_onchain.feather")

    logging.info("  Done with merging dumped files.")

def compute_scores(chain):  
    # Load files  
    df_1kv = pd.read_feather(PATH_TMP / chain / "df_1kv.feather")
    df_era_reward_onchain = pd.read_feather(PATH_TMP / chain / "df_era_reward_onchain.feather")
    stash_1kv = pickle.load(open(PATH_TMP / chain / "stash_1kv.p", "rb"))
    start_era_onchain = read_onchain_era_start_file(PATH_ONCHAIN / chain / "on_chain_era_start.feather")
    

    ## Simple extraction of scores and stats 
    # 28 Oct 2022: Valid is always None for recent. With drop na they get all removed!
    fields = ["stash", "name", "score.datetime", "score.session", "dump.datetime", "rank", "faults", "commission", "location", "provider"] + list(descr_scores[chain].keys())
    last_1kv = df_1kv[fields].dropna()      
    last_1kv = last_1kv.sort_values('dump.datetime').drop_duplicates(["stash"], keep='last').reset_index(drop=True)
    last_1kv.to_json(PATH_INFO / chain / "last_info_1kv.json")
    last_1kv.to_feather(PATH_INFO / chain / "last_info_1kv.feather")    
    
    # score csv file for big dashboard table on landing page 
    last_score = last_1kv[["name", "stash", "rank", "score.total"]].copy()
    last_score["score"] = round(last_score["score.total"],2)
    last_score = last_score.drop(columns={"score.total"})
    last_score = last_score.sort_values('score', ascending=False)
    last_score = last_score.reset_index(drop=True)
    last_score.to_csv(PATH_INFO / chain / "last_score.csv")

    # only stash
    df_stash = df_1kv[["stash"]].drop_duplicates().reset_index(drop=True)
    df_stash.to_feather(PATH_INFO / chain / "stash_1kv.feather")
    df_stash.to_json(PATH_INFO / chain / "stash_1kv.json")
    logging.info(f"   Number of 1kv validators: {len(stash_1kv)}")
            
    ## Era points
    # turn into wide for easier visual
    era_reward_onchain = df_era_reward_onchain.pivot(index="address", columns="era", values="points").replace(np.nan, 0)

    # Calculate time stamps of eras so we can compare with data reported by 1kv json
    if chain=="kusama":
        DURATION_ERA = pd.to_timedelta("6 hours")
    elif chain=="polkadot":
        DURATION_ERA = pd.to_timedelta("24 hours")
    
    eras = era_reward_onchain.columns.values
    # take earliest known era (is 0 since sorted)
    known_era = start_era_onchain.index[0]
    known_time = start_era_onchain.iloc[0]["datetime"]
    eras_start = known_time + (eras  - known_era)*DURATION_ERA

    eras = pd.DataFrame({"era": eras, "start": eras_start}).reset_index(drop=True)      
    eras["end"] = eras["start"] + DURATION_ERA - pd.to_timedelta("1 ms")    
    df_eras_start_end = eras.copy()
    pickle.dump(df_eras_start_end, open(PATH_TMP / chain / "df_eras_start_end.p", "wb")) 

    # check errors
    intersect = start_era_onchain[["datetime"]].join(eras[["era","start"]].set_index("era"), how="inner")
    intersect["diff"] = intersect["datetime"] - intersect["start"]
    # intersect["diff_sec"] = intersect["diff"].apply(pd.Timedelta.total_seconds)
    avg_err = intersect["diff"].abs().mean().total_seconds()
    logging.info(f"    Avg abs error of era start times compared to on chain list with {intersect.shape[0]} eras is {avg_err} seconds.")  

    ## Align score to era
    logging.info("Aligning 1kv score to era")        
    scores_1kv_era = {}
    scores_1kv_era_update = {}
    for score in descr_scores[chain].keys():
        scores_1kv_era[score], scores_1kv_era_update[score] = align_score_1kv_to_era(df_1kv, score, df_eras_start_end, stash_1kv)
    pickle.dump(scores_1kv_era, open(PATH_TMP / chain/ "scores_1kv_era.p", "wb"))
    pickle.dump(scores_1kv_era_update, open(PATH_TMP / chain / "scores_1kv_era_update.p", "wb"))    
    
def recompute_scores(chain):
    ## Recompute existing scores as th-score.XX and add to last_1kv
    last_1kv = pd.read_feather(PATH_INFO / chain / "last_info_1kv.feather") 

    logging.info("Recomputing scores")    
    # First take care of blacklisted providers
    last_1kv["provider.blacklist"] = last_1kv["provider"].isin(blacklist_provider[chain])

    for field in ["location", "provider"]:
        (last_field, last_1kv) = recompute_score_from_quantile(chain, last_1kv, field, True)
        last_field.to_csv(PATH_INFO / chain / f"last_{field}.csv")
    
    last_1kv.to_json(PATH_INFO / chain / "last_info_1kv.json")
    last_1kv.to_feather(PATH_INFO / chain / "last_info_1kv.feather")    
    logging.info("   Done with scores")

    # # Location quantile information
    # last_location = pd.DataFrame()
    # tmp = last_1kv[["stash", "location"]].copy()
    # tmp = tmp.replace('', '(empty)')
    # last_location["count"] = tmp["location"].value_counts()
    # last_location["score"] = round(calc_inclusion_scores(last_location["count"], LOW_Q=quantile_bounds["location"][0], UPP_Q=quantile_bounds["location"][1], SCORE_WEIGHT=score_weights["location"]),2)
    # last_location = last_location.reset_index().rename(columns={"index": "location"})
    # last_location.to_csv(PATH_INFO / chain / "last_location.csv")
    # loc_to_count = dict(zip(last_location["location"], last_location["count"]))
    # loc_to_score = dict(zip(last_location["location"], last_location["score"]))
    # last_1kv["location.count"] = last_1kv["location"].replace(loc_to_count)
    # last_1kv["th-score.location"] = last_1kv["location"].replace(loc_to_score)
    # last_1kv[["th-score.location", "score.location"]]

    # last_1kv.to_json(PATH_INFO / chain / "last_info_1kv.json")
    # last_1kv.to_feather(PATH_INFO / chain / "last_info_1kv.feather")    

    # # 2) Provider
    
    logging.info("   Done with scores")


def save_new_scores(chain):
    """
    An extra function that stores current latest stats & scores with era & timestamp.
    We can compare later if data is consistent
    """
    logging.info("Saving last info with era information.")
    stash_1kv = pickle.load(open(PATH_TMP /chain / "stash_1kv.p", "rb"))
    scores_1kv_era = pickle.load(open(PATH_TMP / chain / "scores_1kv_era.p", "rb"))
    scores_1kv_era_update = pickle.load(open(PATH_TMP / chain / "scores_1kv_era_update.p", "rb"))
    last_1kv = pd.read_feather(PATH_INFO / chain / "last_info_1kv.feather") 

    # TODO: factor out from active_eras.py
    # get current era
    # https://substrate.stackexchange.com/questions/5165/what-is-the-difference-between-currentera-and-activeera
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
    cur_era_start = result['start'].decode()
    cur_time = time.time()
    last_1kv["era"] = cur_era
    last_1kv["analysis.datetime"] = cur_time

    if os.path.isfile(PATH_INFO / chain / "all_last_info_1kv.feather"):
        all_last_1kv = pd.read_feather(PATH_INFO / chain / "all_last_info_1kv.feather") 
        all_last_1kv = pd.concat([all_last_1kv, last_1kv]).reset_index(drop=True)       
    else:
        all_last_1kv = last_1kv.copy().reset_index(drop=True)
    all_last_1kv.to_feather(PATH_INFO / chain / "all_last_info_1kv.feather") 

    logging.info("   Done!")

def calc_delay_score_backend(chain):
    logging.info("Calculating delay of scores.")
    all_last_1kv = pd.read_feather(PATH_INFO / chain / "all_last_info_1kv.feather")   

    tmp = all_last_1kv.copy()
    tmp["diff"] = pd.to_timedelta(tmp["dump.datetime"] - tmp["score.datetime"]) 
    eras = tmp["era"].unique()

    delay_score_backend = pd.DataFrame()
    delay_score_backend_quantiles = pd.DataFrame()
    for era in eras:
        # Multiple values per era. Take minimal one to get optimistic value.
        tmp_era_min = tmp[tmp["era"]==era].groupby("stash")["diff"].min()
        tmp_era = pd.DataFrame(tmp_era_min).reset_index()
        tmp_era["era"] = era
        cur_quant = {}
        cur_quant['quantiles.levels'] = np.array([0.9, 0.75, 0.5, 0.25, 0.1])
        cur_quant['quantiles.values'] = tmp_era_min.quantile(cur_quant['quantiles.levels']).values
        cur_quant = pd.DataFrame.from_dict(cur_quant)
        cur_quant["era"] = era
        delay_score_backend_quantiles = pd.concat([delay_score_backend_quantiles, cur_quant]).reset_index(drop=True)
        delay_score_backend = pd.concat([delay_score_backend, tmp_era]).reset_index(drop=True)
        
    delay_score_backend = delay_score_backend.reset_index(drop=True)
    delay_score_backend.to_feather(PATH_INFO / chain / "delay_score_backend.feather") 

    delay_score_backend_quantiles["hours"] = delay_score_backend_quantiles["quantiles.values"] / np.timedelta64(1, 'h') # trick to get hours
    delay_score_backend_quantiles = delay_score_backend_quantiles.reset_index(drop=True)
    delay_score_backend_quantiles.to_feather(PATH_INFO / chain / "delay_score_backend_quantiles.feather") 
    #return (delay_score_backend, delay_score_backend_quantiles)    
    logging.info("   Done!")


def make_figures(chain):
    stash_1kv = pickle.load(open(PATH_TMP /chain / "stash_1kv.p", "rb"))
    scores_1kv_era = pickle.load(open(PATH_TMP / chain / "scores_1kv_era.p", "rb"))
    scores_1kv_era_update = pickle.load(open(PATH_TMP / chain / "scores_1kv_era_update.p", "rb"))
    delay_score_backend_quantiles = pd.read_feather(PATH_INFO / chain / "delay_score_backend_quantiles.feather") 
    delay_score_backend = pd.read_feather(PATH_INFO / chain / "delay_score_backend.feather") 

    logging.info("Making figures")
    save_dir = PATH_NEWFIGS / chain
    t1 = time.time()
    # Parallel loop for
    # for addr in stash_1kv:    
    #    make_figs_all_scores(scores_1kv_era, scores_1kv_era_update, descr_scores, bound_scores, addr, save_dir)    
    Parallel(n_jobs=4)(delayed(make_figs_all_scores)(scores_1kv_era, scores_1kv_era_update, descr_scores[chain], bound_scores[chain], a, save_dir) for a in stash_1kv)    
    logging.info(f"   Done with big figures in {time.time()-t1} sec")
    
    save_dir_angel = PATH_NEWFIGS / chain / "angel"
    make_figs_delay_score_backend(delay_score_backend_quantiles, save_dir=save_dir_angel)
    make_hist_fig_delay_score_backend(delay_score_backend, save_dir=save_dir_angel)
    logging.info(f"   Done with histogram")

def main_loop():    
    logging.info("Starting main loop")    
    while(True):        
        
        for chain in ["kusama", "polkadot"]:
            logging.info(f" -- {chain} -- ")
            merge_dumps(chain)                
            compute_scores(chain)
            recompute_scores(chain)
            save_new_scores(chain)
            calc_delay_score_backend(chain)
            make_figures(chain) # takes 2 min on mac
            logging.info(f" DONE FOR -- {chain} -- ")
        
            time.sleep(10*random.random()) 
                        
        time.sleep(1.5*60*60.0+10*random.random())  # 1.5h
                
        
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main_loop()    
