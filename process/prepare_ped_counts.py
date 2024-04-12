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

# lightweight_gdf = gdf.drop_duplicates(subset='identifier')
# lightweight_gdf.to_file("../temp/ped_counts_single_only.gpkg")

# %%
# allocate counting stations to appropriate nodes in the dual network
alloc_map = {
    "PERM_PEA02_PM01": 'x440517.809-y4474758.042_x440549.026-y4474893.653_k0',
    "PERM_PEA03_PM01": 'x439984.449-y4474992.468_x439988.773-y4475049.491_k0',
    "PERM_PEA04_PM01": 'x440563.685-y4474719.804_x440622.449-y4474820.005_k0',
    "PERM_PEA05_PM01": 'x440471.682-y4474244.036_x440556.38-y4474235.348_k0',
    "PERM_PEA06_PM01": 'x440874.043-y4473631.349_x440968.09-y4473570.47_k0',
    "PERM_PEA07_PM01": 'x440018.785-y4474200.428_x440122.191-y4474217.16_k0',
    "PERM_PEA08_PM01": 'x440205.425-y4474639.521_x440279.457-y4474632.141_k0',
    "PERM_PEA08_PM02": 'x440205.425-y4474639.521_x440279.457-y4474632.141_k0',
    "PERM_PEA09_PM01": 'x441219.289-y4474563.999_x441251.911-y4474672.194_k0',
    "PERM_PEA10_PM01": 'x441064.298-y4475401.158_x441134.78-y4475354.513_k0',
    "PERM_PEA11_PM01": 'x440764.468-y4473885.577_x440865.054-y4473860.77_k0',
    "PERM_PEA12_PM01": 'x438588.393-y4473963.679_x438799.254-y4473341.958_k0',
    "PERM_PEA13_PM01": 'x439558.791-y4475220.698_x439618.931-y4475107.403_k0',
    "PERM_PEA14_PM01": 'x439457.756-y4475771.408_x439613.08-y4475749.53_k0',
    "PERM_PEA15_PM01": 'x439969.641-y4473818.295_x439976.65-y4473877.293_k0',
    "PERM_PEA16_PM01": 'x441221.663-y4473426.529_x441259.159-y4473406.046_k0',
    "PERM_PEA17_PM01": 'x440425.399-y4472967.182_x440456.751-y4472976.772_k0',
    "PERM_PEA18_PM01": 'x440730.947-y4474400.987_x440909.644-y4474465.422_k0',
    "PERM_PEA19_PM01": 'x439465.043-y4474070.704_x439468.389-y4474123.23_k0',
}
gdf['network_key'] = df['identifier'].map(alloc_map)

# %%
gdf.to_file("../temp/ped_counts.gpkg")
