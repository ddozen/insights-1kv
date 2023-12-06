---
title : "Polkadot - 1kv angel"
draft: false
---

The 1kv angel watches over the 1kv backend and 1kv insights. As *a true guardian angel* it warns about potential errors and bugs.


## Score delay

The 1kv backend updates the scores many times per day but sometimes the process is stuck. Here you can find the delay over time for each era. Since the scores are not all updated at the same time, we display the [three quartiles](https://en.wikipedia.org/wiki/Quartile). In addition, also a [histogram](https://en.wikipedia.org/wiki/Histogram) (in log scale) is visible for the last era. This allows to spot if the backend might be stuck for a subset of the validators.

{{< columns >}}

![Score delay time](delay_score_backend.png)

<--->

![Score delay histogram](delay_score_backend_hist_era_$ANGEL_LATEST_ERA$.png)

{{< /columns >}}

#####