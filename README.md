# paper-centrality-normalisation

Reproducible code for paper on centralities and normalisation

## Installation

Clone this repository to a local working folder.

The PDM package manager is recommended and can be installed on mac per `brew install pdm`.

Packages can then be installed into a virtual environment per `pdm install`.

If using an IDE the `.venv` should be detected.

Create a `temp` folder inside the repository's root folder. This folder is ignored by `.gitignore` but is necessary for the script to output files from the processing steps.

The code is in `process/compute.py` file and can be run using code cells demarcated by the `# %%` lines (assuming an IDE such as vscode).

The file can otherwise be run directly, though the file paths to the `data` folder may need to be adjusted (e.g. changing `../` to `./`).

## Data Sources

### Madrid Data

The data sources are pre-processed as described below and saved to the `data` sub-folder in this repository.

#### Premises Data

- Source:
  - [Download activities dataset](https://datos.madrid.es/portal/site/egob/menuitem.c05c1f754a33a9fbe4b2e4b284f1a5a0/?vgnextoid=66665cde99be2410VgnVCM1000000b205a0aRCRD&vgnextchannel=374512b9ace9f310VgnVCM100000171f5a0aRCRD&vgnextfmt=default)
  - [License](https://datos.madrid.es/egob/catalogo/aviso-legal)
  - Cite: _Origin of the data: Madrid City Council (or, where appropriate, administrative body, body or entity in question)_
  - Description: _Microdata file of the census of premises and activities of the Madrid City Council, classified according to their type of access (street door or grouped), situation (open, closed...) and indication of the economic activity exercised and the hospitality and restaurant terraces that appear registered in said census._
- Premises pre-processing:
  - Import CSV and export as GPKG in EPSG:25830
  - Remove locations without eastings and northings
  - Delete attribute columns where not describing census units or landuse identifiers. (See `compute.py` column renaming for retained columns.)
  - Save as GPKG
  - Vacuum

#### Madrid Neighbourhoods

- Source:
  - [Download](https://datos.madrid.es/portal/site/egob/menuitem.c05c1f754a33a9fbe4b2e4b284f1a5a0/?vgnextoid=760e5eb0d73a7710VgnVCM2000001f4a900aRCRD&vgnextchannel=374512b9ace9f310VgnVCM100000171f5a0aRCRD&vgnextfmt=default)
  - [License](https://datos.madrid.es/egob/catalogo/aviso-legal)
  - Cite: _Origin of the data: Madrid City Council (or, where appropriate, administrative body, body or entity in question)_
  - Description: _Delimitation of the 131 neighborhoods of the municipality of Madrid. The names and codes of each neighborhood and the districts to which they belong are indicated. The initial delimitation corresponds to the territorial restructuring of 1987._
- Save to GPKG in EPSG:25830
- Create buffered boundary
  - Buffer by 20km and dissolve
  - Delete attribute columns
  - Export to GPKG

#### Street Network

- Source:
  - [Download](https://datos.comunidad.madrid/catalogo/dataset/spacm_callescm)
  - [Creative Commons Attribution License](https://creativecommons.org/licenses/by/4.0/legalcode.es)
  - Description: _Set of roads officially approved by the municipalities of the Community of Madrid, ordered by different characteristics._
- Street Network Pre-processing:
  - Download as shapefile
  - Lines split at intersections
  - Duplicate lines removed
  - Saved as GPKG in EPSG:25830
- Filtering:
  - Open 20km buffered bounds
  - Select and delete roads outside buffer
  - Save
  - Vacuum

#### Population Data

- Source:
  - [Download](https://ghsl.jrc.ec.europa.eu/download.php?ds=pop)
  - Citation: Schiavina M., Freire S., Carioli A., MacManus K. (2023): GHS-POP R2023A - GHS population grid multitemporal (1975-2030).European Commission, Joint Research Centre (JRC).
  - Description: _The spatial raster dataset depicts the distribution of residential population, expressed as the number of people per cell._
- Pre-processing:
  - `gdalwarp -cutline buffered_bounds.gpkg -crop_to_cutline -of GTiff -co "COMPRESS=LZW" -dstnodata -200 -t_srs EPSG:25830 population.tif population_clipped.tif`
