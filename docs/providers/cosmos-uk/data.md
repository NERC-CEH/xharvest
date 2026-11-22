# About the COSMOS-UK data

## Timestamps

A value stamped `2025-01-01T00:00` covers the GMT day 2025-01-01.
This was checked against the API's 30-minute data, whose values cover the 30 minutes *ending* at their stamps (`12:30` covers `12:00`–`12:30`): under these readings, 30-minute precipitation summed over each day matches the daily totals to within rounding.

## Snow days

When there is snow on the ground the neutron counts no longer reflect soil moisture alone.
On those days (`snow == 1`), COSMOS-UK reports a `cosmos_vwc` estimated from the counts before the snow, which shows up as a constant run of values.
Use the [`cosmos_vwc_snow_masked`](catena.md#xharvest.cosmos.nodes.cosmos_vwc_snow_masked) catena node to drop them.
The API's 30-minute data has neither `snow` nor `cosmos_vwc`, checked against the parameters returned for ALIC1 on 2025-01-04, so the node will stay daily-only once 30-minute data is supported.

## What the API does not provide

The EIDC release of the same data has per-value flags (missing, infilled, estimated, unchecked) and quality-control flags.
The API has neither, so a value from the API may be infilled or estimated without saying so.
