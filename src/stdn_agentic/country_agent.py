"""
Country Data Generation - Queries USGS database and LLM for top producer countries
"""

import json
import os
import pandas as pd
import duckdb
from datetime import datetime
from typing import Optional, List, Dict, Set

from stdn_agentic.models import ConfigModel
from stdn_agentic.agents import get_country_data_agent, CountryList


class CountryDataGenerator:
    """Generates top N countries data for all materials in the ontology"""
    
    def __init__(
        self,
        materials_hs_codes_file: str,
        materials_column_name: str,
        usgs_database: str,
        model: str,
        top_n: int = 5,
        years_to_query: Optional[List[Dict[str, int]]] = None
    ):
        self.materials_hs_codes_file = materials_hs_codes_file
        self.materials_column_name = materials_column_name
        self.usgs_database = usgs_database
        self.model = model
        self.top_n = top_n
        
        # Default years if not provided
        if years_to_query is None:
            self.years_to_query = [
                {"src_yr": 2025, "meas_yr": 2024},
                {"src_yr": 2025, "meas_yr": 2023},
                {"src_yr": 2024, "meas_yr": 2022},
                {"src_yr": 2023, "meas_yr": 2021},
                {"src_yr": 2022, "meas_yr": 2020}
            ]
        else:
            self.years_to_query = years_to_query
        
        # Load materials
        self.materials_df = pd.read_csv(materials_hs_codes_file)
        self.materials_df = self.materials_df.fillna("NA")
        
        # Connect to USGS database
        self.con = duckdb.connect(usgs_database)
        
        # Get the country data agent
        self.country_agent = get_country_data_agent()
        
        print(f"Connected to USGS database")
        print(f"Tables: {self.con.execute('show tables').fetchall()}")
    
    def _load_existing_data(self, output_file: str) -> Dict:
        """Load existing country data if it exists"""
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load existing file {output_file}: {e}")
                return {}
        return {}
    
    def _get_materials_to_process(
        self, 
        mode: str, 
        existing_materials: Set[str],
        specific_materials: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Determine which materials to process based on mode
        
        Modes:
        - 'full': Process all materials (ignore existing data)
        - 'incremental': Only process materials not in existing data
        - 'update': Only process specific materials (update existing)
        """
        
        if mode == 'full':
            print("Mode: FULL - Processing all materials")
            return self.materials_df
        
        elif mode == 'incremental':
            # Only process materials not in existing data
            new_materials = self.materials_df[
                ~self.materials_df[self.materials_column_name].isin(existing_materials)
            ]
            print(f"Mode: INCREMENTAL - Processing {len(new_materials)} new materials")
            print(f"Skipping {len(existing_materials)} existing materials")
            return new_materials
        
        elif mode == 'update':
            # Only process specific materials (for updates)
            if not specific_materials:
                print("Mode: UPDATE - No specific materials provided, processing all")
                return self.materials_df
            
            materials_to_update = self.materials_df[
                self.materials_df[self.materials_column_name].isin(specific_materials)
            ]
            print(f"Mode: UPDATE - Processing {len(materials_to_update)} specified materials")
            
            # List materials not found
            found_materials = set(materials_to_update[self.materials_column_name].tolist())
            not_found = set(specific_materials) - found_materials
            if not_found:
                print(f"Warning: Materials not found in ontology: {not_found}")
            
            return materials_to_update
        
        else:
            raise ValueError(f"Unknown mode: {mode}")
    
    def _query_usgs_top_countries(
        self,
        usgs_material: str,
        src_year: int,
        meas_year: int
    ) -> Optional[pd.DataFrame]:
        """Query USGS database for top producing countries"""
        
        query = f"""
        SELECT w.country 
        FROM world_mineral_commodity_report w 
        WHERE w.meas_yr IS NOT NULL 
            AND w.meas_yr = {meas_year}
            AND w.src_yr = {src_year}
            AND UPPER(w.commodity) = '{usgs_material.upper()}'
            AND value_type = 'Number'
            AND UPPER(meas_type) = 'PRODUCTION'
            AND UPPER(country) NOT LIKE 'WORLD%'
            AND UPPER(country) NOT LIKE 'OTHER%'
        GROUP BY w.country
        ORDER BY SUM(CAST(w.value AS NUMERIC)) DESC
        LIMIT {self.top_n}
        """
        
        try:
            results = self.con.sql(query).df()
            return results if len(results) > 0 else None
        except Exception as e:
            print(f"USGS query failed for {usgs_material}: {e}")
            return None
    
    def _query_usgs_world_totals(
        self,
        usgs_material: str,
        src_year: int,
        meas_year: int
    ) -> Dict:
        """Query USGS database for world totals by measure type"""
        
        query = f"""
        SELECT w.meas_unit, w.meas_type, SUM(CAST(w.value AS NUMERIC)) as value
        FROM world_mineral_commodity_report w
        WHERE w.meas_yr IS NOT NULL
            AND w.meas_yr = {meas_year}
            AND w.src_yr = {src_year}
            AND UPPER(w.commodity) = '{usgs_material.upper()}'
            AND value_type = 'Number'
            AND UPPER(country) = 'WORLD TOTAL (ROUNDED)'
        GROUP BY w.meas_unit, w.meas_type
        """
        
        try:
            results = self.con.sql(query).df()
            world_dict = {}
            for _, row in results.iterrows():
                world_dict[row["MEAS_TYPE"]] = {
                    "meas_unit": row["MEAS_UNIT"],
                    "value": row["value"]
                }
            return world_dict
        except Exception as e:
            print(f"World totals query failed for {usgs_material}: {e}")
            return {}
    
    def _query_usgs_country_details(
        self,
        usgs_material: str,
        country: str,
        src_year: int,
        meas_year: int,
        world_dict: Dict
    ) -> List[Dict]:
        """Query USGS database for all measure types for a specific country"""
        
        query = f"""
        SELECT w.meas_unit, w.meas_type, SUM(CAST(w.value AS NUMERIC)) as value
        FROM world_mineral_commodity_report w
        WHERE w.meas_yr IS NOT NULL
            AND w.meas_yr = {meas_year}
            AND w.src_yr = {src_year}
            AND UPPER(w.commodity) = '{usgs_material.upper()}'
            AND value_type = 'Number'
            AND UPPER(country) = '{country}'
        GROUP BY w.meas_unit, w.meas_type
        """
        
        try:
            results = self.con.sql(query).df()
            country_lines = []
            
            for _, line in results.iterrows():
                percentage = ""
                try:
                    world_value = world_dict[line["MEAS_TYPE"]]["value"]
                    meas_unit = world_dict[line["MEAS_TYPE"]]["meas_unit"]
                    if meas_unit == line["MEAS_UNIT"]:
                        percentage = round(100 * (line["value"] / world_value), 2)
                except:
                    percentage = ""
                
                line_dict = {
                    "meas_type": line["MEAS_TYPE"],
                    "meas_unit": line["MEAS_UNIT"],
                    "value": line["value"],
                    "percent": percentage
                }
                country_lines.append(line_dict)
            
            return country_lines
        except Exception as e:
            print(f"Country details query failed for {country}: {e}")
            return []
    
    async def _query_llm_for_countries(
        self,
        material: str,
        meas_year: int
    ) -> List[Dict]:
        """Use LLM to get country data when USGS doesn't have it"""
        
        prompt = f"""Return a list of the top {self.top_n} countries that produced {material} in {meas_year},
the amount and units of measure produced of material {material} in that year, and the percentage of
the total global supply for {material} each country produced in that year (based on the most recent numbers available).
Return a list that includes each country, the amount produced, the unit of measure and percentage of global.
Do not return any other explanatory text."""
        
        try:
            result = await self.country_agent.run(
                prompt,
                model=self.model
            )
            
            country_breakdown = result.output.country_list
            top_countries_list = []
            
            for country_line in country_breakdown:
                country_lines = [{
                    "meas_type": "PRODUCTION",
                    "meas_unit": country_line.meas_unit.upper(),
                    "value": country_line.amount,
                    "percent": country_line.percentage
                }]
                
                country_dict = {
                    "country": country_line.country.upper(),
                    "reported_assets": country_lines
                }
                top_countries_list.append(country_dict)
            
            return top_countries_list
            
        except Exception as e:
            print(f"LLM query failed for {material}: {e}")
            return []
    
    async def generate_country_data(
        self, 
        output_file: str,
        mode: str = 'full',
        specific_materials: Optional[List[str]] = None
    ):
        """
        Generate country data for materials
        
        Args:
            output_file: Path to output JSON file
            mode: 'full' (rebuild), 'incremental' (add new), or 'update' (update specific)
            specific_materials: List of specific materials to update (for 'update' mode)
        """
        
        print(f"Starting country data generation at {datetime.now()}")
        print(f"Mode: {mode.upper()}")
        
        # Load existing data
        materials_dict = self._load_existing_data(output_file) if mode != 'full' else {}
        existing_materials = set(materials_dict.keys())
        
        if existing_materials and mode != 'full':
            print(f"Loaded {len(existing_materials)} existing materials from {output_file}")
        
        # Determine which materials to process
        materials_to_process = self._get_materials_to_process(
            mode, 
            existing_materials,
            specific_materials
        )
        
        if len(materials_to_process) == 0:
            print("No materials to process!")
            return
        
        # Process materials
        for idx, row in materials_to_process.iterrows():
            material = row[self.materials_column_name]
            hs_code = row["HS_Code"]
            usgs_material = row["USGS_Name"]
            
            print(f"Processing material: {material} ({idx + 1}/{len(materials_to_process)})")
            
            years_list = []
            
            for year in self.years_to_query:
                src_year = year["src_yr"]
                meas_year = year["meas_yr"]
                
                top_countries_list = []
                query_source = "USGS"
                
                # Try USGS first
                if usgs_material != "NA":
                    top_countries_df = self._query_usgs_top_countries(
                        usgs_material, src_year, meas_year
                    )
                    
                    if top_countries_df is not None and len(top_countries_df) > 0:
                        # USGS has data
                        world_dict = self._query_usgs_world_totals(
                            usgs_material, src_year, meas_year
                        )
                        
                        for _, country_row in top_countries_df.iterrows():
                            country_lines = self._query_usgs_country_details(
                                usgs_material,
                                country_row["COUNTRY"],
                                src_year,
                                meas_year,
                                world_dict
                            )
                            
                            country_dict = {
                                "country": country_row["COUNTRY"],
                                "reported_assets": country_lines
                            }
                            top_countries_list.append(country_dict)
                    else:
                        # Fall back to LLM
                        usgs_material = "NA"
                
                # Use LLM if USGS doesn't have data
                if usgs_material == "NA":
                    query_source = self.model
                    top_countries_list = await self._query_llm_for_countries(
                        material, meas_year
                    )
                
                year_dict = {
                    "year": meas_year,
                    "query_source": query_source,
                    "top_countries": top_countries_list
                }
                years_list.append(year_dict)
            
            # Add or update material in dictionary
            materials_dict[material] = years_list
            print(f"Material {material} {'updated' if material in existing_materials else 'added'}")
            print("*" * 50)
        
        # Close database connection
        self.con.close()
        
        # Create backup of existing file if updating
        if mode != 'full' and os.path.exists(output_file):
            backup_file = f"{output_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(output_file, backup_file)
            print(f"Backup created: {backup_file}")
        
        # Write to JSON file
        with open(output_file, "w") as outfile:
            json.dump(materials_dict, outfile, indent=2)
        
        print(f"Country data written to {output_file}")
        print(f"Total materials in file: {len(materials_dict)}")
        print(f"Completed at {datetime.now()}")


def get_country_data_generator(config: ConfigModel) -> CountryDataGenerator:
    """Factory function to create CountryDataGenerator from config"""
    
    years = [
        {"src_yr": year, "meas_yr": year - 1}
        for year in config.years_to_query
    ]
    
    return CountryDataGenerator(
        materials_hs_codes_file=config.materials_hs_codes_listing,
        materials_column_name=config.materials_column_name,
        usgs_database=config.usgs_database,
        model=config.model,
        top_n=config.top_n_countries,
        years_to_query=years
    )
