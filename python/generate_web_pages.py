#!/usr/bin/env python3

# Copyright 2022-2023 https://www.math-crypto.com -- GNU General Public License

from distutils.dir_util import remove_tree
from pathlib import Path
from shutil import copy, copytree, rmtree

import pandas as pd
import logging
import time
import random
import json
import pickle
import fileinput
from datetime import datetime, timezone
import glob
import os
import subprocess
import sys

from scores_1kv import *
import timeit


PATH_JSON  = Path.cwd() / "../1kv_json"
PATH_ONCHAIN = Path.cwd() / "../onchain"
PATH_NEWFIGS = Path.cwd() / "../new_figs"
PATH_INFO = Path.cwd() / "../info"
PATH_TMP = Path.cwd() / "../tmp"
PATH_WEB = Path.cwd() / "../web"
PATH_DOKS_ROOT = Path.cwd() / "../doks"




def generate(chain):
    logging.info(f"Generating new pages for the stashes of {chain}.")
    last_1kv = pd.read_feather(PATH_INFO / chain / "last_info_1kv.feather")
    for index, row in last_1kv.iterrows():        
        addr = row["stash"]
        
        logging.debug(f"   {addr}")
        addr_path_web = PATH_WEB / chain / addr
        addr_path_web.mkdir(exist_ok=True)
        file_template = PATH_WEB / "templates" / chain  / "index.md"
        addr_file_index = addr_path_web / "index.md"
        copy(file_template, addr_file_index)

        # Do simple subs
        # with fileinput.FileInput(addr_file_index, inplace=True) as file:
        #     for line in file:
        #         print(line.replace("STASH", addr), end='')
        with fileinput.FileInput(addr_file_index, inplace=True) as file:
            for line in file:
                # Hugo wants the time in UTC if no offset.
                print(line.replace("DATETIME", f"{datetime.now(timezone.utc).isoformat()}"), end='')

        # Subs for header
        subs = {"stash": "STASH",
          "name": "$TELEMETRY-NAME$" ,
          "commission": "$COMMISSION$",
          "rank": "$RANK$",
          "faults": "$NB-FAULTS$"}     
        sys.stdout.reconfigure(encoding='utf-8')
        for key, value in subs.items():
            with fileinput.FileInput(addr_file_index, inplace=True, encoding='utf-8') as file:
                for line in file:
                    print(line.replace(value, f"{row[key]}"), end='')
        # Subs for Individual scores: statistics eg '$inclusion$': 'score.inclusion'
        subs = {f"${v.split('.')[-1]}$" : v  for v in list(descr_scores[chain].keys())}
        for key, value in subs.items():   
            if value=="score.randomness":
                score_str = f"{row[value]:.2f}" 
                max_str = f"{bound_scores[chain][value][1]:.2f}"
            else:
                score_str = f"{row[value]:.1f}" 
                max_str = f"{bound_scores[chain][value][1]:.0f}"
                                
            with fileinput.FileInput(addr_file_index, inplace=True, encoding='utf-8') as file:
                for line in file:           
                    print(line.replace(key, f"{score_str}/{max_str}"), end='')
        
        # Subs for Score retrieved from 1kv backend on $DUMP_DATETIME$. Score last calculated by backend on $SCORE_DATETIME$.
        ### DO NOT USE "DATETIME" SINCE USED ABOVE. INSTEAD USE "DATE_TIME"
        print( row["score.datetime"])

        
        subs = {
        "$DUMP_DATE_TIME$": row["dump.datetime"].strftime("%B %d, %Y at %I:%M:%S %p UTC").replace(' at 0', ' at '),
        "$SCORE_DATE_TIME$": row["score.datetime"].strftime("%B %d, %Y at %I:%M:%S %p UTC").replace(' at 0', ' at ')
        }

        for key, value in subs.items():   
            with fileinput.FileInput(addr_file_index, inplace=True, encoding='utf-8') as file:
                for line in file:
                    print(line.replace(key, value), end='')

        # Subs for the 1kv angel
        diff = pd.to_timedelta(row["dump.datetime"] - row["score.datetime"])
        
        subs = {"$ANGEL_LOCATION_VALUE$": f"{row['location']} (occurs {row['location.count']:.0f} times)" ,        
          "$ANGEL_LOCATION_SCORE$": f"{row['score.location']:.1f}" ,
          "$ANGEL_LOCATION_TH_SCORE$": f"{row['th-score.location']:.1f}",
          "$ANGEL_DELAY_SCORE$": format_time_delta(diff)}
        for key, value in subs.items():   
            with fileinput.FileInput(addr_file_index, inplace=True, encoding='utf-8') as file:
                for line in file:
                    print(line.replace(key, value), end='')
        
        # key = "commission"
        # value = subs[key]
        # with fileinput.FileInput(addr_file_index, inplace=True) as file:
        #     for line in file:
        #         print(line.replace(value, f"{row[key]}"), end='')

            
        # copy figures
        path_new_figs = PATH_NEWFIGS / chain
        for f in path_new_figs.glob(f"{addr}_*.png"):
            copy(f, addr_path_web)
    logging.info("   Generating new pages done.")

def generate_angel_pages(chain):
    logging.info(f"Generating new angel page for {chain}.")
    delay_score_backend = pd.read_feather(PATH_INFO / chain / "delay_score_backend.feather") 

    # figures are copied by copy_to_website 

    logging.info(f"  Making webpage")        
    addr_path_web = PATH_WEB / chain / "angel"
    addr_path_web.mkdir(exist_ok=True)
    file_template = PATH_WEB / "templates" / chain  / "angel.md"
    addr_file_index = addr_path_web / "index.md"
    print(file_template)
    print(addr_file_index)
    copy(file_template, addr_file_index)

    # copy figures
    path_new_figs = PATH_NEWFIGS / chain / "angel"
    for f in path_new_figs.glob("*.png"):
        copy(f, addr_path_web)

    latest_era = delay_score_backend["era"].max()
    subs = {"$ANGEL_LATEST_ERA$": f"{latest_era}"}
    for key, value in subs.items():   
        with fileinput.FileInput(addr_file_index, inplace=True) as file:
            for line in file:
                print(line.replace(key, value), end='')

    logging.info("   Generating angle page done.")
                


def copy_to_website(chain):
    """
    Copy website to a local folder, which can be build by doks later.
    """
    logging.info(f"Copy new pages for stashes to the doks content directory for {chain}.")
    # copy all the newly generated pages for the stashes (and figures) to doks
    doks_content_dir = PATH_DOKS_ROOT / "content/en/"
    # No longer backup since we have files like  _index.md that we want to keep with dirs_exist_ok=True below
    # # move original files in case we need to restore 
    # bak_dir = PATH_TMP / f"{chain}-doks-bak"
    # if os.path.exists(bak_dir) and os.path.isdir(bak_dir):
    #     rmtree(bak_dir)
    # os.rename(doks_content_dir / chain, PATH_TMP / f"{chain}-doks-bak")
    copytree(PATH_WEB / chain, doks_content_dir / chain, dirs_exist_ok=True)
    # copy(PATH_TMP / f"{chain}-doks-bak/_index.md", doks_content_dir / chain)

    # copytree(PATH_WEB / "polkadot", doks_content_dir / "polkadot")
    copy(PATH_INFO / chain / "last_score.csv", PATH_DOKS_ROOT / f"_data/{chain}/scores.csv")
    copy(PATH_INFO / chain / "last_location.csv", PATH_DOKS_ROOT / f"_data/{chain}/locations.csv")
    copy(PATH_INFO / chain / "last_provider.csv", PATH_DOKS_ROOT / f"_data/{chain}/providers.csv")

    logging.info("   Copy done.")
        
def build_website():
    """
    Build hugo website with nodejs.
    """
    logging.info("Building doks website.")
    # TODO: detect if something goes wrong and stop uploading?
    #  return code does not work
    my_env = os.environ.copy()
    # TODO: put in env option -> ask for a sym link to a standard location?
    my_env["PATH"] = "~/.nvm/versions/node/v19.1.0/bin:" + my_env["PATH"]
    out = subprocess.run("npm run build", shell=True, capture_output=True, cwd=PATH_DOKS_ROOT, env=my_env)
    if out.returncode==0:
        logging.info("   Building done.")
    else:
        logging.info("   Building failed. Quitting so we can gracefully restart...")
        logging.info(out.stdout)
        logging.info(out.stderr)
        # Failure means the doks build was using temp files. Restarting usually helps.
        # In a systemd deployment, this will restart a few times
        sys.exit(1)
        

def upload_website():
    """
    Upload website with rclone to "InsightWebsite". This should be configured before.
    """
    logging.info("Uploading website with rclone.")
    for filename in (PATH_DOKS_ROOT / "public/kusama" ).rglob("*.png"):        
        filename.unlink()
    for filename in (PATH_DOKS_ROOT / "public/polkadot" ).rglob("*.png"):        
        filename.unlink()    

    # does not seem to work ?!?
    #if ~os.path.exists(PATH_DOKS_ROOT / "public_html"):
    #    os.symlink(PATH_DOKS_ROOT / "public", PATH_DOKS_ROOT / "public_html", target_is_directory=True)    
    # TODO in config
    PATH_WEBSITE = (PATH_DOKS_ROOT / "public").resolve()
    t1 = time.time()
    my_env = os.environ.copy()
    my_env["PATH"] = "/usr/bin:" + my_env["PATH"]
    cmd_rclone = f"rclone sync --stats-log-level NOTICE --stats 5m {PATH_WEBSITE} InsightWebsite:./public_html"
    out = subprocess.run(cmd_rclone, shell=True, capture_output=True, cwd=PATH_DOKS_ROOT, env=my_env)
    logging.info(f"   Done with uploading in {time.time()-t1} sec")

    print(out.stdout)
    print(out.stderr)
    print(out.returncode)

    if out.returncode==0:
        logging.info("   Upload done.")
    else:
        logging.info("   Upload failed.")
        logging.info(out.stdout)

    # TODO remove old files since each webp is new. This can be done afterwards.



def main_loop():    
    while(True):                        
        logging.info("Starting with generation of doks website for stashes.")
        # all md pages and figures are first built locally under web/
        generate("kusama")  # 1 min
        generate("polkadot")  # 1 min        
        generate_angel_pages("kusama") 
        generate_angel_pages("polkadot")        
        # then the pages are copied over to the doks/content dir
        copy_to_website("kusama")
        copy_to_website("polkadot")
        # and build by hugo
        build_website()  # 5 min  
        upload_website() # 5 min
        logging.info("   Generation website done.")
        time.sleep(2*60*60.0 + (5.0+random.random())*2) # every 2h
                
        
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main_loop()