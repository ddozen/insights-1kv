# Copyright 2022-23 https://www.math-crypto.com -- GNU Affero General Public License v3.0

import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
from matplotlib.ticker import MaxNLocator
from matplotlib.ticker import ScalarFormatter
from scores_1kv_config import *

def read_1kv_json(json_dir, oldest_datetime=-1):
    """
    Read dumped json files from the 1kv backend. All date is from json except datetime is the exact datetime of the dump.
    
    Only use json files that are newer than oldest_datetime (if not -1)
    """
    df_s = []
    for f in list(json_dir.glob('*.feather')):
        datetime = f.stem
        if int(datetime)>=oldest_datetime:
            # print(f"Reading {datetime}")                    
            df = pd.read_feather(f)
            df['dump.datetime'] = pd.to_datetime(datetime, unit='s')
            # df['dump.datetime'] = datetime
            df = df.reset_index(drop=True)
            df_s.append(df)
        # else:
        #     print(f"Skipped {datetime}")
            
    df_all = pd.concat(df_s).reset_index(drop=True)
    df_all['score.datetime'] = pd.to_datetime(df_all['score.updated'], unit='ms')
    return df_all 

def read_onchain_erareward_files(era_tmp_dir):
    """
    Read on-chain reward points that were dumped as feather files by active_eras.py
    """
    first = True    
    for f in sorted(era_tmp_dir.glob("*.feather")):    
        df_f = pd.read_feather(f)
        if first:
            df_all = df_f
            first = False
        else:
            df_all = pd.concat([df_all, df_f], ignore_index=True).drop_duplicates().reset_index(drop=True)
            # Detect same era address and take max (this can happen if era was not finished yet when querying chain)
            # From https://stackoverflow.com/a/40629420 - cool trick to select only max points 
            df_all = df_all.sort_values('points', ascending=False).drop_duplicates(['address','era'], keep="first")
            
            df_all = df_all.sort_values(["address", "era"])
            # print(f"Number of rows: {len(df_all)}")
    return df_all

def read_onchain_era_start_file(era_start_file):
    """
    The ActiveEra storage function returns the start of the era.
    This gets dumped together with the era points when calling active_eras.py
    """
    df_start = pd.read_feather(era_start_file).set_index("era").sort_index()
    df_start["datetime"] = pd.to_datetime(df_start["start"], unit="ms")    
    return df_start    


def calc_inclusion_percentage(df_all, delta):
    """
    Calculate the percentage when validator was active for delta eras.
    Done for all eras in a sliding window [era-delta+1, era].    
    """
    # TODO: can be faster - calc from df_era and slice over all addresses (replace > = by True, and sum in window)
    eras = df_all['era'].unique()
    max_era = np.max(eras) 
    min_era = np.min(eras)     
    addr = df_all['address'].unique()
        
    pcts = []
    for address in addr:
        pct_cur = {"address": address}
        df_cur = df_all[df_all['address'] == address]        
        for end_era in range(max_era, min_era+delta-1, -1):          
            pct_cur[end_era] = len( df_cur[(df_cur['era'] <= end_era) & (df_cur['era'] >= end_era-delta+1)] ) / delta
        pcts.append(pct_cur)

    return pd.DataFrame(pcts).set_index("address", verify_integrity=True)


def calc_inclusion_scores(df_incl, LOW_Q=0.20, UPP_Q=0.75, SCORE_WEIGHT=100):
    """
    Calculate the scores from the inclusion percentage
    """
    quant = df_incl.quantile([LOW_Q, UPP_Q])

    df_score = (df_incl - quant.loc[LOW_Q])/(quant.loc[UPP_Q] - quant.loc[LOW_Q])
    filt_low = df_incl<=quant.loc[LOW_Q]
    filt_high = df_incl>=quant.loc[UPP_Q]
    df_score[filt_low] = 0
    df_score[filt_high] = 1
    return (1-df_score) * SCORE_WEIGHT

def replace_era_by_timestamp(df, known_era, known_time, DURATION_EPOCH):
    """
    Calculate time stamps of the eras in df by a reference value.
    The columns of df should be eras (hence a df is wide).
    """
    eras = pd.to_numeric(df.columns).values
    eras_start = known_time + (eras  - known_era)*DURATION_EPOCH
    df_new = df.copy()
    df_new.columns = eras_start
    return df_new


def align_score_1kv_to_era(df_1kv, score_field, df_eras_start_end, stash_1kv):
    """
    Extract one score field from df_1kv dataframe, align to an era and forward fill the gaps.
    Performed for all addresses in stash_1kv.
    """
    score_1kv = df_1kv[["stash", score_field, "score.datetime"]].drop_duplicates().sort_values("score.datetime") 
    score_1kv = score_1kv.rename(columns={score_field: "SCORE", "score.datetime": "datetime"})

    # the eras that we want to match with
    tmp_eras_end = df_eras_start_end.rename(columns={"end": "datetime"})
    tmp_eras_end = tmp_eras_end.sort_values(by="datetime")

    tmp_eras = df_eras_start_end["era"].sort_values().values
    tmp_eras = pd.DataFrame({"era": tmp_eras}).set_index("era")
    tmp_eras["score"] = -1

    pcts = []
    updates= []
    for address in stash_1kv:
        
        tmp_1kv = score_1kv.query("stash==@address").dropna().sort_values(by="datetime")
        tmp_1kv_era = pd.merge_asof(tmp_1kv, tmp_eras_end, on="datetime", direction="forward")    
        
        # fill in blanks in eras for each score by using last updated entry
        tmp = tmp_1kv_era[["SCORE", "era"]].set_index("era")        
        tmp = tmp[~tmp.index.duplicated(keep='last')] # take most recent value in era when multiple values      
        tmp = tmp_eras.join(tmp).drop(columns=["score"])
        tmp2 = tmp.copy()
        tmp2["updated"] = ~tmp2["SCORE"].isna()
        tmp2 = tmp2.drop(columns=["SCORE"])
        tmp2["address"] = address
        tmp = tmp.fillna(method="ffill")    
        tmp["address"] = address
        tmp = tmp.reset_index().pivot(index="address", columns="era", values="SCORE")
        tmp2 = tmp2.reset_index().pivot(index="address", columns="era", values="updated")

        pcts.append(tmp)
        updates.append(tmp2)

    return pd.concat(pcts), pd.concat(updates)

def recompute_score_from_quantile(chain, last_1kv, field, with_blacklist):
    """
    Recompute existing scores for a field based on quantile info.

    Field can be location, provider

    Add to last_1kv as new columns th-score.field. Also output simple count csv.
    """
    ##     
    
    # Location quantile information
    # https://github.com/w3f/1k-validators-be/blob/master/packages/common/src/constraints.ts#L334   
    # 1) Location
    # The score for location is based on the frequency of that location. 
    # We thus first count them and these counts are in the quantile calculation.
    # The table last_location is nice to have (and to put on the website) 
    # but we also want to put the theoretical score in the original dataframe.
    # For that, we will replace the location name with the count & score.

    last_field = pd.DataFrame()
    tmp = last_1kv[["stash", field, "provider.blacklist"]].copy()
    tmp = tmp.replace('', '(empty)')
    # THIS DOES NOT WORK - the string 'provider' gets placed in the provider.count column below!
    # if field=="provider":
    #     tmp = tmp.replace('provider', '(unspecified)')
    
    last_field["count"] = tmp[field].value_counts()
    last_field["score"] = round(calc_inclusion_scores(last_field["count"], LOW_Q=quantile_bounds[chain][field][0], UPP_Q=quantile_bounds[chain][field][1], SCORE_WEIGHT=score_weights[chain][field]),2)

    if with_blacklist:
        # each stash address has a  "provider.blacklist", if at least one is blacklisted, the field will be blacklist and get zero score
        last_field["blacklist"] = tmp[[field,"provider.blacklist"]].groupby(field).min()
        # provider score is zero if blacklisted
        # for others (location city), there can be other providers, so in the summary, we do not state 0 score
        if field=="provider":
            last_field.loc[last_field["blacklist"], "score"] = 0.0

    last_field = last_field.reset_index().rename(columns={"index": field})

    loc_to_count = dict(zip(last_field[field], last_field["count"]))
    loc_to_score = dict(zip(last_field[field], last_field["score"]))
    last_1kv[f"{field}.count"] = last_1kv[field].replace(loc_to_count)
    last_1kv[f"th-score.{field}"] = last_1kv[field].replace(loc_to_score)    

    return (last_field, last_1kv) 


### FIGURES    

def make_figs_all_scores(scores_1kv_era, scores_1kv_era_update, descr_scores, bound_scores, address, save_dir=None):    
    plt.rcParams.update({'font.size': 16})
    if save_dir:
        matplotlib.use('agg')
    
    # mplstyle.use(['ggplot', 'fast']) # uglier on ggplot is uglier on screen

    for score in descr_scores.keys():        
        fig = plt.figure(figsize=(8,4.8))
        # fig, ax = plt.subplots(1, 1, figsize=(8,4.8))
        
        x = scores_1kv_era[score].loc[address].index.values
        y = scores_1kv_era[score].loc[address].values
        plt.plot(x,y,'b-')
        x_up = scores_1kv_era_update[score].loc[address].index.values
        y_up = scores_1kv_era_update[score].loc[address].values

        updated_era = x_up[y_up]
        updated_score = y[y_up]
        plt.plot(updated_era,updated_score,'bo')
        bnd = bound_scores[score]
        plt.ylim(bnd + np.array([-0.05, 0.05])*(bnd[1]-bnd[0]))
        plt.grid(True)

        plt.title(descr_scores[score])
        plt.tight_layout()
        if save_dir:
            tmp_score = score.replace(".", "-")
            fig.savefig(save_dir / f"{address}_era_{tmp_score}.png", dpi=75, facecolor='white', transparent=False)
            
            plt.close(fig)    


def format_time_delta(timedelta):
    """Timedelta formatter in hours / secs."""
    totsec = timedelta.total_seconds()
    h = totsec//3600
    m = (totsec%3600) // 60
    sec =(totsec%3600)%60 #just for reference
    if h==0:
        return f"{m:.0f} seconds"
    else:
        return f"{h} hours and {m:.0f} seconds"            


## new plotting histogram and delay - not on site yet
def make_figs_delay_score_backend(delay_score_backend_quantiles, save_dir=None):    
    plt.rcParams.update({'font.size': 16})
    if save_dir:
        matplotlib.use('agg')
        
    fig = plt.figure(figsize=(8,4.8))
    # we dump 1kv every hour and compute score every 1.5h
    # so we regard <=3h delay normal
    plt.axhline(y = 3, color = 'grey', linestyle = '-', label='1kv insight resolution')

    x = delay_score_backend_quantiles[delay_score_backend_quantiles["quantiles.levels"]==0.5]["era"]
    y = delay_score_backend_quantiles[delay_score_backend_quantiles["quantiles.levels"]==0.5]["hours"]
    plt.plot(x,y,'b-', label='Median (Q2)')
    x = delay_score_backend_quantiles[delay_score_backend_quantiles["quantiles.levels"]==0.25]["era"]
    y = delay_score_backend_quantiles[delay_score_backend_quantiles["quantiles.levels"]==0.25]["hours"]
    plt.plot(x,y,'b--', label='Q1 and Q3')
    x = delay_score_backend_quantiles[delay_score_backend_quantiles["quantiles.levels"]==0.75]["era"]
    y = delay_score_backend_quantiles[delay_score_backend_quantiles["quantiles.levels"]==0.75]["hours"]
    plt.plot(x,y,'b--')

    plt.legend()

    plt.grid(True)
    plt.title("Delay of score computed by 1kv backend")
    plt.xlabel("era")
    plt.ylabel("hours")
    plt.tight_layout()
    # only integers on axis
    # https://www.scivision.dev/matplotlib-force-integer-labeling-of-axis/
    ax = fig.gca()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    if save_dir:        
        fig.savefig(save_dir / f"delay_score_backend.png", dpi=75, facecolor='white', transparent=False)            
        plt.close(fig)  

def make_hist_fig_delay_score_backend(delay_score_backend, era=None, save_dir=None):
    plt.rcParams.update({'font.size': 16})
    if save_dir:
        matplotlib.use('agg')        

    fig = plt.figure(figsize=(8,4.8))

    if era is None: # take last
        era = delay_score_backend["era"].max()
        
    tmp_hours = delay_score_backend.query("era==@era")["diff"].values / np.timedelta64(1, 'h')
    
    # log histogram requires log binning
    hist, bins = np.histogram(tmp_hours, bins=16)
    # TODO scale explicitly for bin not too small
    logbins = np.logspace(np.log10(bins[0]+1e-99),np.log10(bins[-1]),len(bins))
    plt.hist(tmp_hours, bins=logbins)
    plt.xscale('log')

    # plt.grid(True)
    plt.xlabel("hours delay")
    plt.ylabel("number of validators")
    plt.title(f"Histogram of delay of score for era {era}")
    plt.tight_layout()
    # no powers
    # https://stackoverflow.com/questions/21920233/matplotlib-log-scale-tick-label-number-formatting
    # ax = fig.gca()    
    # ax.xaxis.set_major_formatter(ScalarFormatter())

    if save_dir:        
        fig.savefig(save_dir / f"delay_score_backend_hist_era_{era}.png", dpi=75, facecolor='white', transparent=False)            
        plt.close(fig)   

