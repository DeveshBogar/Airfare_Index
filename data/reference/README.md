# Reference data

## `dgca_city_pair_traffic.csv`

Real, government-sourced domestic city-pair passenger traffic data from the
Directorate General of Civil Aviation (DGCA), India — "City pair wise
monthly domestic passenger traffic statistics"
(https://www.dgca.gov.in/digigov-portal/?page=monthlyStatistics/259/4751/html).

Retrieved via the open-source mirror
[`Vonter/india-aviation-traffic`](https://github.com/Vonter/india-aviation-traffic)
(commit `306ff9085`, 2026-07-06), which scrapes the same DGCA monthly
releases (plus the Wayback Machine for older months no longer hosted live)
into clean CSV. Licensed **ODbL-1.0** — attribution preserved here per the
license's terms.

Columns: `Year, Month, City1, City2, PaxToCity2, PaxFromCity2,
FreightToCity2, FreightFromCity2, MailToCity2, MailFromCity2`.

This is the sole input to `backend/app/index/weights.py`, which derives each
route's share of the Airfare Price Index basket from real passenger volumes
— exactly what the problem statement asks for ("selected on the basis of
DGCA passenger-traffic data").

Refresh with:

```bash
python scripts/download_dgca_data.py
```
