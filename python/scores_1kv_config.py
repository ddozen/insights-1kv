# Copyright 2022-23 https://www.math-crypto.com -- GNU Affero General Public License v3.0

import pandas as pd
import numpy as np
import requests
import matplotlib
import os
import json
import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
from matplotlib.ticker import MaxNLocator
from matplotlib.ticker import ScalarFormatter
def fetch_data():
    url = "https://kusama.w3f.community/scoremetadata"
    try:
        response = requests.get(url, timeout=10)  # added a timeout for the request
        if response.status_code == 200:
            return response.json()
        else:
            print("Failed to retrieve data: Status code", response.status_code)
            return None
    except requests.exceptions.RequestException as e:
        print("Request failed:", e)
        return None


def save_data_to_disk(data):
    with open('weights_data.json', 'w') as file:
        json.dump(data, file, indent=4)

def load_data_from_disk():
    try:
        with open('weights_data.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("No local copy of weights data found.")
        return {}

def format_data(data):
    if data:
        _score_tmp = {
            "inclusion": str(data.get("inclusionWeight", 0)),
            "spanInclusion": str(data.get("spanInclusionWeight", 0)),
            "discovered": str(data.get("discoveredAtWeight", 0)),
            "nominated": str(data.get("nominatedAtWeight", 0)),
            "rank": str(data.get("rankWeight", 0)),
            "bonded": str(data.get("bondedWeight", 0)),
            "faults": "5",  # Placeholder value
            "offline": str(data.get("offlineWeight", 0)),
            "location": str(data.get("locationWeight", 0)),
            "aggregate": "0",  # Placeholder value
            "randomness": "1.15",
            "total": "0",  # Placeholder value
            "nominatorStake": str(data.get("nominatorStakeWeight", 0)),
            "region": str(data.get("regionWeight", 0)),
            "country": str(data.get("countryWeight", 0)),
            "provider": str(data.get("providerWeight", 0))
        }
        return _score_tmp
    else:
        return {}

# TODO: 👥 means it is shared over all identities
_descr_scores = {
        "score.inclusion": "Inclusion: Active for last 84 eras", 
        "score.spanInclusion": "Span inclusion: Active for last 28 eras",
        "score.discovered": "Discovered: Join date in 1kv",
        "score.nominated": "Nominated: Last time nominated by 1kv",
        "score.rank": "Rank: Rank in 1kv",        
        "score.bonded": "Bonded: Amount of self bond",
        "score.faults": "Faults: Number of on chain faults",
        "score.offline": "Offline: Offline during this week", 
        "score.location": "Location: Location shared by other validators",
        # "score.democracy": "Gov 1 democracy: Consistency in referenda voting",
        # "score.openGov": "OpenGov democracy: Consistency in referenda voting",        
        # "score.delegations": "Gov 1 delegations to you",
        # "score.councilStake": "Council: Bond for council elections",
        "score.aggregate": "Aggregate: Total of all scores",
        "score.randomness": "Randomness: Random multiplicative factor",
        "score.total": "Total score: Score with random factor",
        "score.nominatorStake": "Nominations: Total except 1kv",        
        "score.region": "Region: Region shared by other validators",
        "score.country": "Country: Country shared by other validators",
        "score.provider": "Provider: Provider shared by other validators",
        # "score.openGovDelegations": "OpenGov delegations to any of your identities",
        }
descr_scores = {}
descr_scores['kusama'] = _descr_scores.copy()
descr_scores['polkadot'] = _descr_scores.copy()

# TODO get this from github and parse automatically. Some fields need to be renamed:   
#  council ->    councilStake  and   nominators -> nominatorStake
# From constraints.tx    -> new: https://github.com/w3f/1k-validators-be/blob/master/packages/gateway/config/main.sample.json
# https://github.com/w3f/1k-validators-be/blob/master/helmfile.d/config/kusama/otv-backend-prod.yaml.gotmpl#L55


data = fetch_data()
if data:
    # Format the data
    _score_tmp = format_data(data)
    # Save the data to disk
    save_data_to_disk(_score_tmp)
else:
    # Load data from disk if API fails
    _score_tmp = load_data_from_disk()

score_tmp = {}
score_tmp['kusama'] = _score_tmp.copy()
score_tmp['polkadot'] = _score_tmp.copy()

def compute_score_weights(score_tmp):
    # weight for computing the total score
    score_weights = {key: float(value) for (key, value) in score_tmp.items()}
    tmp = score_weights.copy()
    tmp.pop('aggregate')
    tmp.pop('randomness')
    tmp.pop('total')

    max_score = sum(tmp.values())
    score_weights['aggregate'] = max_score
    score_weights['total'] = max_score * float(score_tmp['randomness'])
    return score_weights

score_weights = {}
score_weights['kusama'] = compute_score_weights(score_tmp['kusama'])
score_weights['polkadot'] = compute_score_weights(score_tmp['polkadot'])

def compute_bound_scores(score_weights):
    # for plotting
    bound_scores = {f"score.{key}": np.array([0., value]) for (key, value) in score_weights.items()}
    bound_scores["score.randomness"] = np.array([1., score_weights["randomness"]])
    return bound_scores

bound_scores = {}
bound_scores['kusama'] = compute_bound_scores(score_weights['kusama'])
bound_scores['polkadot'] = compute_bound_scores(score_weights['polkadot'])

# quantile constants: hard-coded in https://github.com/w3f/1k-validators-be/blob/master/packages/common/src/constraints.ts#L334
# If not specified, using the default values in https://github.com/w3f/1k-validators-be/blob/master/packages/common/src/score.ts#L53
LQ_DFT = 0.1
UQ_DFT = 0.9
    
_quantile_bounds =  {
"inclusion": np.array([0.05, 0.95]),
"spanInclusion": np.array([0.05, 0.95]),
"discovered": np.array([LQ_DFT, UQ_DFT]), 
"nominated": np.array([LQ_DFT, UQ_DFT]), 
"rank": np.array([LQ_DFT, UQ_DFT]), 
"bonded": np.array([0.05, 0.85]),
"faults": np.array([LQ_DFT, UQ_DFT]), 
"offline": np.array([LQ_DFT, UQ_DFT]), 
"location": np.array([0, 1]),
"councilStake": np.array([LQ_DFT, UQ_DFT]),  # very special rule
"democracy": np.array([LQ_DFT, UQ_DFT]), # special rule
"aggregate": "0", # TODO CALC
"randomness": "1.15", # TODO random uniform or Gaussian?  const randomness = 1 + Math.random() * 0.15; https://github.com/w3f/1k-validators-be/blob/1ff144c96c7105d102a8206e982dea3a8f405615/packages/common/src/constraints.ts
"total": "0",
"nominatorStake": np.array([0.05, 0.95]), # special rule: active and inactive as sqrt https://github.com/w3f/1k-validators-be/blob/master/packages/common/src/constraints.ts#L436
"delegations": np.array([0.1, 0.95]), # also sqrt
"region": np.array([0, 1]),
"country": np.array([0, 1]),
"provider": np.array([0, 1]),
"openGov": np.array([LQ_DFT, UQ_DFT])
}

quantile_bounds = {}
quantile_bounds['kusama'] = _quantile_bounds.copy()
quantile_bounds['polkadot'] = _quantile_bounds.copy()

# https://github.com/w3f/1k-validators-be/blob/47c1dbd4924d91c430b931d222d37ec90b1c9045/helmfile.d/config/polkadot/otv-backend-prod.yaml.gotmpl#L1309
_blacklist_provider = ["Hetzner Online GmbH", "Contabo Inc.", "Contabo GmbH"]
blacklist_provider = {}
blacklist_provider['kusama'] = _blacklist_provider.copy()
blacklist_provider['polkadot'] = _blacklist_provider.copy()

