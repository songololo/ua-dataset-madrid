# %%
"""
Extracts:
- population density
- network centralities in metric, angular, segment, and length weighted forms
- landuse access in metric, angular, mixed use form from premises data
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
from cityseer.metrics import layers, networks
from cityseer.tools import graphs, io, util
from rasterio import MemoryFile
from rasterstats import point_query
from shapely import geometry, wkt
from tqdm import tqdm

from process import premises_lu_schema

# update the paths to correspond to your file locations if different to below
# create a temp folder if not existing before running
PATH_STREETS = "./data/street_network.gpkg"
PATH_NEIGHBOURHOODS = "./data/neighbourhoods.gpkg"
PATH_OUT_DATASET = "./temp/dataset.gpkg"
PATH_OUT_DATASET_SUBSET = "./temp/dataset_subset.gpkg"
PATH_PREMISES = "./data/premises_activities.gpkg"
PATH_OUT_PREMISES = "./data/premises_clean.gpkg"
PATH_POPULATION = "./data/population_clipped.tif"

CENT_DISTANCES = [200, 500, 1000, 2000, 5000, 10000]
LU_DISTANCES = [100, 200, 500, 1000, 2000]

# %%
# open streets
edges_gdf = gpd.read_file(PATH_STREETS)
# convert multipart geoms to single
edges_gdf_singles = edges_gdf.explode(drop=True)
# generate networkx
G_nx = io.nx_from_generic_geopandas(edges_gdf_singles)
# removes degree 2 if found
G_nx = graphs.nx_remove_filler_nodes(G_nx)
G_nx = graphs.nx_remove_dangling_nodes(G_nx)

# %%
# city boundary
bounds = gpd.read_file(PATH_NEIGHBOURHOODS)
bounds_union_geom = bounds.buffer(10).geometry.unary_union

# %%
# decided not to decompose
# prepare dual
G_nx_dual = graphs.nx_to_dual(G_nx)

# %%
# computations only run for live nodes
for nd_key, nd_data in tqdm(G_nx_dual.nodes(data=True), total=G_nx_dual.number_of_nodes()):
    point = geometry.Point(nd_data["x"], nd_data["y"])
    # set live nodes for nodes within boundary
    if not bounds_union_geom.contains(point):
        G_nx_dual.nodes[nd_key]["live"] = False
    # extract edge bearings for visualisation
    primal_edge = nd_data["primal_edge"]
    G_nx_dual.nodes[nd_key]["bearing"] = util.measure_bearing(
        list(primal_edge.coords)[0], list(primal_edge.coords)[-1]
    )

# %%
# extract unweighted structure
_nodes_gdf, _edges_gdf, network_structure = io.network_structure_from_nx(
    G_nx_dual,
)

# %%
# create separate network structure with length weighted data
for nd_key, nd_data in tqdm(G_nx_dual.nodes(data=True), total=G_nx_dual.number_of_nodes()):
    # set node weight accord to primal edge lengths
    primal_edge = nd_data["primal_edge"]
    G_nx_dual.nodes[nd_key]["weight"] = primal_edge.length

# extract length weighted structure
nodes_gdf, edges_gdf, network_structure_len_wt = io.network_structure_from_nx(
    G_nx_dual,
)


# %%
# copy bearing info for primal
def copy_primal_bearings(row):
    return G_nx_dual.nodes[row.name]["bearing"]


nodes_gdf["bearing"] = nodes_gdf.apply(copy_primal_bearings, axis=1)
# copy neighbourhood identifiers to nodes
nodes_centroids = nodes_gdf.geometry.centroid
nodes_centroids_gdf = gpd.GeoDataFrame(geometry=nodes_centroids, crs=nodes_gdf.crs)
joined_gdf = gpd.sjoin(nodes_centroids_gdf, bounds, how="left", predicate="intersects")
nodes_gdf["district"] = joined_gdf["NOMDIS"]
nodes_gdf["neighb"] = joined_gdf["NOMBRE"]

# %%
# population data
with open(PATH_POPULATION, "rb") as f:
    memfile = MemoryFile(f.read())
    with memfile.open() as dataset:
        pop_raster = dataset.read()
        for node_idx, node_row in tqdm(nodes_gdf.iterrows(), total=len(nodes_gdf)):
            pop_val = point_query(
                wkt.loads(node_row["dual_node"]),
                pop_raster,
                interpolate="nearest",
                nodata=-200,
                affine=dataset.transform,
            )[0]
            if pop_val is None:
                pop_val = 0
            nodes_gdf.at[node_idx, "pop_dens"] = np.clip(pop_val, 0, np.inf)
# convert from 100m2 to 1km2
nodes_gdf["pop_dens"] = nodes_gdf["pop_dens"] * 100

# %%
# run shortest path centrality
nodes_gdf = networks.node_centrality_shortest(
    network_structure_len_wt,
    nodes_gdf,
    distances=CENT_DISTANCES,
)
# run simplest path centrality
nodes_gdf = networks.node_centrality_simplest(
    network_structure_len_wt,
    nodes_gdf,
    distances=CENT_DISTANCES,
    angular_scaling_unit=90,  # to match Space Syntax convention of 0 - 180 = 0 - 2
    farness_scaling_offset=0,  # to match Space Syntax convention of 0 - 180 = 0 - 2
)

# %%
# rename length weighted columns for saving (prevents overwriting)
for col_extract in [
    "cc_density",
    "cc_beta",
    "cc_farness",
    "cc_harmonic",
    "cc_hillier",
    "cc_betweenness",
    "cc_betweenness_beta",
]:
    new_col_extract = col_extract.replace("cc_", "cc_lw_")
    nodes_gdf.columns = [col.replace(col_extract, new_col_extract) for col in nodes_gdf.columns]


# %%
# rerun without length weightings - renamed lw columns won't be overwritten
# run shortest path centrality
nodes_gdf = networks.node_centrality_shortest(
    network_structure,
    nodes_gdf,
    distances=CENT_DISTANCES,
)
# run simplest path centrality
nodes_gdf = networks.node_centrality_simplest(
    network_structure,
    nodes_gdf,
    distances=CENT_DISTANCES,
    angular_scaling_unit=90,  # to match Space Syntax convention of 0 - 180 = 0 - 2
    farness_scaling_offset=0,  # to match Space Syntax convention of 0 - 180 = 0 - 2
)

# %%
# run segment path centrality
nodes_gdf = networks.segment_centrality(
    network_structure,
    nodes_gdf,
    distances=CENT_DISTANCES,
)

# %%
# load premises
premises = gpd.read_file(PATH_PREMISES)

# %%
# rename columns to english
premises_eng = premises.rename(
    columns={
        "id_local": "local_id",
        "id_distrito_local": "local_distr_id",
        "desc_distrito_local": "local_distr_desc",
        "id_barrio_local": "local_neighb_id",
        "desc_barrio_local": "local_neighb_desc",
        "cod_barrio_local": "local_neighb_code",
        "id_seccion_censal_local": "local_census_section_id",
        "desc_seccion_censal_local": "local_census_section_desc",
        "id_seccion": "section_id",
        "desc_seccion": "section_desc",
        "id_division": "division_id",
        "desc_division": "division_desc",
        "id_epigrafe": "epigraph_id",
        "desc_epigrafe": "epigraph_desc",
        "geometry": "geometry",
    }
)
# cast index to string
premises_eng.index = premises_eng.index.astype(str)
# map section descriptions to english
premises_eng["section_desc"] = premises_eng["section_desc"].replace(
    premises_lu_schema.section_schema
)
# map division descriptions to english
premises_eng["division_desc"] = premises_eng["division_desc"].replace(
    premises_lu_schema.division_schema
)
# remove none / null
premises_eng = premises_eng[~premises_eng["section_desc"].str.contains("none|null", na=False)]
premises_eng = premises_eng[
    ~premises_eng["division_desc"].str.contains("Null Value at Origin|No Activity", na=False)
]
# %%
# save cleaned version
premises_eng.to_file(PATH_OUT_PREMISES)

# %%
# compute mixed uses
nodes_gdf, premises_eng = layers.compute_mixed_uses(
    premises_eng,
    landuse_column_label="division_desc",
    nodes_gdf=nodes_gdf,
    network_structure=network_structure,
    distances=LU_DISTANCES,
    compute_hill=False,
    compute_hill_weighted=True,
)
# compute mixed uses using simplest paths
nodes_gdf, premises_eng = layers.compute_mixed_uses(
    premises_eng,
    landuse_column_label="division_desc",
    nodes_gdf=nodes_gdf,
    network_structure=network_structure,
    distances=LU_DISTANCES,
    compute_hill=False,
    compute_hill_weighted=True,
    angular=True,
)
# compute accessibility
nodes_gdf, premises_eng = layers.compute_accessibilities(
    premises_eng,
    landuse_column_label="division_desc",
    accessibility_keys=[
        "food_bev",
        "creat_entert",
        "retail",
        "services",
        "education",
        "accommod",
        "sports_rec",
        "health",
    ],
    nodes_gdf=nodes_gdf,
    network_structure=network_structure,
    distances=LU_DISTANCES,
)
# compute accessibility using simplest paths
nodes_gdf, premises_eng = layers.compute_accessibilities(
    premises_eng,
    landuse_column_label="division_desc",
    accessibility_keys=[
        "food_bev",
        "creat_entert",
        "retail",
        "services",
        "education",
        "accommod",
        "sports_rec",
        "health",
    ],
    nodes_gdf=nodes_gdf,
    network_structure=network_structure,
    distances=LU_DISTANCES,
    angular=True,
)

# %%
# save only live nodes
nodes_gdf_live = nodes_gdf[nodes_gdf.live]
# filter out non located per districts
nodes_gdf_live = nodes_gdf[~nodes_gdf.district.isna()]
# simplify geom if necessary
nodes_gdf_live.geometry = nodes_gdf_live.geometry.simplify(2)
# pare back data types to reduce size
for col in nodes_gdf_live.select_dtypes(include=["int64"]).columns:
    nodes_gdf_live[col] = nodes_gdf_live[col].astype("int32")
for col in nodes_gdf_live.select_dtypes(include=["float64"]).columns:
    nodes_gdf_live[col] = nodes_gdf_live[col].astype("float32")
# save
nodes_gdf_live.to_file(PATH_OUT_DATASET)

# %%
# save subset
nodes_gdf_subset = nodes_gdf_live[
    nodes_gdf_live["district"].isin(
        [
            "Centro",
            "Arganzuela",
            "Retiro",
            "Salamanca",
            "Chamartín",
            "Tetuán",
            "Chamberí",
        ]
    )
]
nodes_gdf_subset.to_file(PATH_OUT_DATASET_SUBSET)
