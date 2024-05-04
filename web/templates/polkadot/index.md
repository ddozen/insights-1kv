---
title: "$TELEMETRY-NAME$"
date: DATETIME
draft: false
contributors: []
stash: "STASH"
telemetryname: "$TELEMETRY-NAME$"
---

Stash: STASH


{{< columns >}}

Rank: $RANK$

<--->

Commission: $COMMISSION$ %

<--->

Nb of faults: $NB-FAULTS$

{{< /columns >}}  


## Individual scores: latest

Your total score at 1kv is the sum of several individual scores, multiplied by a small random factor.

{{< alert icon="👉" text="Scores related to Gov 1 are decreasing in value over time since Gov 1 will (likely) be phased out on Polkadot. These scores are indicated with a 💤 below." />}}


| Score   | Explanation   | Points |
| ----------- | ----------- |---|
| SpanInclusion | Active for last 28 eras | $spanInclusion$ |
| Inclusion | Active for last 84 eras      | $inclusion$       |
| Nominators | Amount of nominations (except by 1kv) | $nominatorStake$ |
| Provider | Provider shared by other validators | $provider$ |
| Bonded | Amount of self bond | $bonded$ |
| Location | Location shared by other validators | $location$ |
| Nominated | Last time nominated by 1kv | $nominated$ |
| Region | Region shared by other validators   | $region$        |
| Country | Country shared by other validators | $country$ |
| Rank | Rank in 1kv | $rank$ |
| Discovered | Join date in 1kv   | $discovered$        |
| Faults | Number of on chain faults | $faults$ |
| Offline | Offline during this week | $offline$ |
| Aggregate | Sum of all scores | $aggregate$ |
| Randomness | Random positive multiplicative factor | $randomness$ |
| **Score** | **Final score in 1kv** | $total$ |

Score retrieved from 1kv backend on $DUMP_DATE_TIME$. 

Score last calculated by backend on $SCORE_DATE_TIME$.

## Individual scores: history over last 200 eras

Each dot is a new value given by the 1kv backend. Lines indicate no update. For all scores, higher is better. 

{{< columns >}}

![Inclusion](STASH_era_score-inclusion.png)

![Nominators](STASH_era_score-nominatorStake.png)

![Location](STASH_era_score-location.png)

![Region](STASH_era_score-region.png)





<--->
![Span inclusion](STASH_era_score-spanInclusion.png)

![Provider](STASH_era_score-provider.png)

![Bonded](STASH_era_score-bonded.png)

![Nominated](STASH_era_score-nominated.png)

![Country](STASH_era_score-country.png)


<!-- ![Rank](STASH_era_score-rank.png)

![Discovered](STASH_era_score-discovered.png)

![Faults](STASH_era_score-faults.png)

![Offline](STASH_era_score-offline.png) -->


{{< /columns >}}

<!-- 
{{< alert icon="👉" text="The scoring backend of 1kv underwent a redesign in the months around era 4300. This explains some of the unexpected behaviors in the score graphs above. For example, the maximal inclusion score was increased from 100 to 140. In addition, some scores were higher than their maximal value (this bug has been fixed)." />}} -->

## The 1kv angel

For some scores, it is possible to recompute the exact value based on the latest (and most up to date) information. This is listed as **theoretical score** in the table below. Small differences with the reported score are normal since the 1kv backend computes the scores with slightly older information. Big differences, however, indicate a bug.

| Type | Value | reported 1kv score | theoretical score
|----|--|--|-|
|Location|$ANGEL_LOCATION_VALUE$|$ANGEL_LOCATION_SCORE$|$ANGEL_LOCATION_TH_SCORE$|

Age of scores calculated by 1kv backend at the time of the latest data retrieval: $ANGEL_DELAY_SCORE$.
