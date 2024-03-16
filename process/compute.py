""" """

# %%
from __future__ import annotations

import geopandas as gpd
import schema
from cityseer.metrics import layers, networks
from cityseer.tools import graphs, io, util
from shapely import geometry

# update the paths to correspond to your file locations
path_streets = "../data/street_network.gpkg"
path_neighbourhoods = "../data/neighbourhoods.gpkg"
path_out_dataset = "../temp/dataset.gpkg"
path_premises = "../data/premises_activities.gpkg"
path_out_premises = "../temp/premises_clean.gpkg"

# %%
# open streets
edges_gdf = gpd.read_file(path_streets)
# convert multipart geoms to single
edges_gdf_singles = edges_gdf.explode(drop=True)
# generate networkx
G_nx = io.nx_from_generic_geopandas(edges_gdf_singles)
# removes degree 2 if found
G_nx = graphs.nx_remove_filler_nodes(G_nx)
G_nx = graphs.nx_remove_dangling_nodes(G_nx)

# %%
# city boundary
bounds = gpd.read_file(path_neighbourhoods)
bounds_union_geom = bounds.buffer(10).geometry.unary_union
# prepare dual
G_nx_dual = graphs.nx_to_dual(G_nx)

# %%
# computations only run for live nodes
for nd_key, nd_data in G_nx_dual.nodes(data=True):
    point = geometry.Point(nd_data["x"], nd_data["y"])
    # set live nodes for nodes within boundary
    if not bounds_union_geom.contains(point):
        G_nx_dual.nodes[nd_key]["live"] = False
    # attach primal geometry
    primal_geom = G_nx[nd_data["primal_edge_node_a"]][nd_data["primal_edge_node_b"]][
        nd_data["primal_edge_idx"]
    ]["geom"]
    G_nx_dual.nodes[nd_key]["primal_geom"] = primal_geom
    # set node weight accord to primal edge lenghts
    G_nx_dual.nodes[nd_key]["weight"] = primal_geom.length
    # extract edge bearings for visualisation
    G_nx_dual.nodes[nd_key]["bearing"] = util.measure_bearing(
        list(primal_geom.coords)[0], list(primal_geom.coords)[-1]
    )

# %%
# extract structure
nodes_gdf, edges_gdf, network_structure = io.network_structure_from_nx(
    G_nx_dual, crs=edges_gdf.crs
)


# %%
# splice primal geom onto dual nodes for vis
def copy_primal_edges(row):
    return G_nx_dual.nodes[row.name]["primal_geom"]


# splice the primal edges onto the dual nodes
nodes_gdf["line_geometry"] = nodes_gdf.apply(copy_primal_edges, axis=1)


# copy bearing info for primal
def copy_primal_bearings(row):
    return G_nx_dual.nodes[row.name]["bearing"]


nodes_gdf["bearing"] = nodes_gdf.apply(copy_primal_bearings, axis=1)
# copy neighbourhood identifiers to nodes
joined_gdf = gpd.sjoin(nodes_gdf, bounds, how="left", predicate="intersects")
nodes_gdf["distr"] = joined_gdf["NOMDIS"]
nodes_gdf["neighb"] = joined_gdf["NOMBRE"]
# switch to line geoms
nodes_gdf.set_geometry("line_geometry", inplace=True)
nodes_gdf["line_geometry"].set_crs(edges_gdf.crs, inplace=True)
# geopackages can only handle a single geom column, so demote original geom to WKT
nodes_gdf["point_geom"] = nodes_gdf["geom"].to_wkt()
# and drop geom column
nodes_gdf = nodes_gdf.drop(columns=["geom"])

# %%
# run shortest path centrality
cent_distances = [500, 1000, 2000, 5000, 10000]
nodes_gdf = networks.node_centrality_shortest(
    network_structure,
    nodes_gdf,
    distances=cent_distances,
)
# run simplest path centrality
nodes_gdf = networks.node_centrality_simplest(
    network_structure,
    nodes_gdf,
    distances=cent_distances,
)

# %%
# load premises
premises = gpd.read_file(path_premises)

# %%
# rename columns to english
premises_eng = premises.rename(
    columns={
        "id_local": "local_id",
        "id_distrito_local": "local_distr_id",
        "desc_distrito_local": "local_distr_desc",
        "id_barrio_local": "local_neighb_id",
        "desc_barrio_local": "local_neighb_desc ",
        "cod_barrio_local": "local_neighb_code",
        "id_seccion_censal_local": "local_census_section_id",
        "desc_seccion_censal_local": "local_census_section_desc ",
        "id_seccion": "section_id",
        "desc_seccion": "section_desc",
        "id_division": "division_id",
        "desc_division": "division_desc",
        "id_epigrafe": "epigraph_id",
        "desc_epigrafe": "epigraph_desc ",
        "geometry": "geometry",
    }
)
# cast index to string
premises_eng.index = premises_eng.index.astype(str)
# map section descriptions to english
premises_eng["section_desc"] = premises_eng["section_desc"].replace(
    schema.section_schema
)
# map division descriptions to english
premises_eng["division_desc"] = premises_eng["division_desc"].replace(
    schema.division_schema
)
# remove none / null
premises_eng = premises_eng[
    ~premises_eng["section_desc"].str.contains("none|null", na=False)
]
premises_eng = premises_eng[
    ~premises_eng["division_desc"].str.contains(
        "Null Value at Origin|No Activity", na=False
    )
]
# %%
# save cleaned version
premises_eng.to_file(path_out_premises)

# %%
lu_distances = [500, 1000, 2000]
# compute mixed uses
nodes_gdf, premises_eng = layers.compute_mixed_uses(
    premises_eng,
    landuse_column_label="division_desc",
    nodes_gdf=nodes_gdf,
    network_structure=network_structure,
    distances=lu_distances,
    compute_hill=False,
    compute_hill_weighted=True,
)
# compute accessibility to
nodes_gdf, premises_eng = layers.compute_accessibilities(
    premises_eng,
    landuse_column_label="division_desc",
    accessibility_keys=[
        "food_bev",
        "creative_entert",
        "retail",
        "services",
        "education",
        "accommod",
        "sports_rec",
        "health",
    ],
    nodes_gdf=nodes_gdf,
    network_structure=network_structure,
    distances=lu_distances,
)

# %%
# save only live nodes
nodes_gdf_live = nodes_gdf[nodes_gdf.live]
nodes_gdf_live.to_file(path_out_dataset)
