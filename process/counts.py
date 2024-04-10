# %%
import csv

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import geometry

with open("../data/2021_ped_counts.csv") as csv_file:
    csv_content = csv.reader(csv_file, delimiter=";")
    header = next(csv_content)
    rows = []
    for line in csv_content:
        rows.append(line)

headers_english = [
    "date",
    "time",
    "identifier",
    "pedestrians",
    "district_num",
    "district",
    "street_name",
    "number",
    "postal_code",
    "address_observations",
    "lat",
    "lng",
]
df = pd.DataFrame(rows, columns=headers_english)
df.replace("", np.nan, inplace=True)
df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y %H:%M")
df.drop(columns=["time"], inplace=True)
for col in ["district_num", "number"]:
    df[col] = df[col].astype(int)
for col in ["pedestrians", "lat", "lng"]:
    df[col] = df[col].str.replace(",", ".").astype(float)
    df[col] = df[col].astype(float)
df["geom"] = df.apply(lambda row: geometry.Point(row["lng"], row["lat"]), axis=1)
gdf = gpd.GeoDataFrame(df, geometry="geom")
gdf.set_crs(epsg=4326, inplace=True)
gdf.to_crs(3035, inplace=True)
gdf.to_file("../temp/ped_counts.gpkg")
