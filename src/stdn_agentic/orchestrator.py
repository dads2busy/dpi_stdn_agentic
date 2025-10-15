"""
STDN Orchestrator for managing the multi-agent pipeline
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict
from pydantic_ai import UsageLimits, RunUsage

from stdn_agentic.models import STDNDependencies, ConfigModel, ComponentMaterialsList
from stdn_agentic.dependencies import initialize_dependencies
from stdn_agentic.agents import get_component_agent, get_materials_agent
from stdn_agentic.utils import intersect_lists, embed_comma_delimited_str


class STDNOrchestrator:
    """Orchestrates the STDN generation pipeline using multiple agents"""
    
    def __init__(self, config: ConfigModel):
        self.config = config
        self.deps = initialize_dependencies(config)
        self.write_nulls = config.write_nulls_to_output
        self.component_agent = get_component_agent()
        self.materials_agent = get_materials_agent()
        
        # Output file paths
        self.output_file = os.path.join(
            config.output_dir, 
            f"{config.output_csv_filename}.csv"
        )
        self.output_times = os.path.join(
            config.output_dir,
            f"{config.output_csv_filename}_times.csv"
        )
        
        # Usage limits
        self.usage_limits = UsageLimits(
            request_limit=50,
            total_tokens_limit=100000
        )
        
        # Create output directory
        os.makedirs(config.output_dir, exist_ok=True)
    
    async def process_technology(
        self,
        tech: str,
        role: str,
        domain: str,
        usage: RunUsage,
        timeout: int = 180
    ) -> Optional[Dict]:
        """Process a single technology through the pipeline"""
        
        print(f"Starting STDN for technology: {tech}")
        start_time = datetime.now()
        
        try:
            # Step 1: Extract components with timeout
            component_result = await asyncio.wait_for(
                self.component_agent.run(
                    f"You are {role}. Create a list of the primary technology components "
                    f"used in the manufacture of {tech}.",
                    deps=self.deps,
                    usage=usage,
                    usage_limits=self.usage_limits,
                    model=self.config.model
                ),
                timeout=timeout
            )
            
            if not component_result.output.component_list:
                print(f"Could not find components for {tech}")
                return None
            
            components = component_result.output.component_list
            print(f"Found {len(components)} components for {tech}")
            
            # Step 2: Extract materials for components
            materials_prompt = (
                f"ComponentList contains: {', '.join(components)}. "
                f"For each component, return raw materials using only: {self.deps.material_ontology}. "
                "Create a separate element for each raw material."
            )
            
            materials_result = await asyncio.wait_for(
                self.materials_agent.run(
                    materials_prompt,
                    deps=self.deps,
                    usage=usage,
                    usage_limits=self.usage_limits,
                    model=self.config.model
                ),
                timeout=timeout
            )
            
            # Step 3: Build output structure with country data
            output_struct = self._build_output_structure(
                tech=tech,
                domain=domain,
                materials_data=materials_result.output
            )
            
            # Step 4: Write JSON output
            clean_tech = tech.replace(' ', '_')
            json_file = os.path.join(self.config.output_dir, f"{clean_tech}.json")
            with open(json_file, 'w') as f:
                json.dump(output_struct, f, indent=2)
            
            end_time = datetime.now()
            print(f"Done with {tech} in {(end_time - start_time).total_seconds()}s")
            
            return {
                'tech': tech,
                'domain': domain,
                'start': start_time,
                'end': end_time,
                'output': output_struct,
                'success': True
            }
            
        except asyncio.TimeoutError:
            print(f"Tech {tech} timed out after {timeout}s")
            return {'tech': tech, 'success': False, 'error': 'timeout'}
        except Exception as e:
            print(f"Tech {tech} could not be evaluated: {e}")
            return {'tech': tech, 'success': False, 'error': str(e)}
    
    def _build_output_structure(
        self,
        tech: str,
        domain: str,
        materials_data: ComponentMaterialsList
    ) -> Dict:
        """Build the output structure with country enrichment"""
        output_struct = {'technology': tech, 'component_list': []}
        
        for component_rec in materials_data.component_list:
            component = component_rec.component
            raw_materials = intersect_lists(
                component_rec.raw_materials_list,
                self.deps.material_ontology_list
            )
            
            output_raw_materials = []
            print(f"Getting countries for Component: {component}")
            
            for raw_material in raw_materials:
                # Get HS code
                hs_code = self.deps.material_ontology_dict.get(
                    raw_material, {}
                ).get('HSCode', 'NA')
                
                # Get country breakdown
                country_data = self.deps.materials_top_countries_dict.get(raw_material, [])
                year_breakdown = [
                    year_data for year_data in country_data
                    if year_data['year'] in self.deps.years_to_query
                ]
                
                raw_material_dict = {
                    'raw_material': raw_material,
                    'hscode': hs_code,
                    'country_year_breakdown': year_breakdown
                }
                output_raw_materials.append(raw_material_dict)
            
            component_dict = {
                'component': component,
                'raw_material_list': output_raw_materials
            }
            output_struct['component_list'].append(component_dict)
        
        return output_struct
    
    def write_csv_output(self, results: List[Dict], start_new_file: bool = True):
        """Write results to CSV file"""
        mode = 'w' if start_new_file else 'a'
        
        with open(self.output_file, mode) as fout:
            if start_new_file:
                fout.write(
                    "Technology,Component,Material,HS Code,Query Source,Year,"
                    "Country,MeasType,MeasUnit,Amount,Percent\n"
                )
            
            for result in results:
                if not result.get('success'):
                    continue
                
                tech = result['tech']
                output_struct = result['output']
                
                for comp in output_struct['component_list']:
                    component = comp['component']
                    raw_materials = comp['raw_material_list']
                    
                    if self.write_nulls and not raw_materials:
                        fout.write(f"{tech},{embed_comma_delimited_str(component)},,,,,,,\n")
                        continue
                    
                    for rawmat in raw_materials:
                        raw_material = rawmat['raw_material']
                        hs_code = rawmat['hscode']
                        country_struct = rawmat['country_year_breakdown']
                        
                        for year_struct in country_struct:
                            year = year_struct['year']
                            query_source = year_struct['query_source']
                            top_countries = year_struct.get('top_countries', [])
                            
                            if self.write_nulls and not top_countries:
                                fout.write(
                                    f"{tech},{embed_comma_delimited_str(component)},"
                                    f"{embed_comma_delimited_str(raw_material)},"
                                    f"{hs_code},{query_source},{year},,,,\n"
                                )
                                continue
                            
                            for top_country in top_countries:
                                country = top_country['country']
                                reported_assets = top_country.get('reported_assets', [])
                                
                                for asset in reported_assets:
                                    fout.write(
                                        f"{tech},{embed_comma_delimited_str(component)},"
                                        f"{embed_comma_delimited_str(raw_material)},"
                                        f"{hs_code},{query_source},{year},"
                                        f"{embed_comma_delimited_str(country)},"
                                        f"{asset['meas_type']},{asset['meas_unit']},"
                                        f"{asset['value']},{asset['percent']}\n"
                                    )
    
    def write_timing_csv(self, results: List[Dict]):
        """Write timing information"""
        with open(self.output_times, 'w') as f:
            f.write("domain,tech,round,start,end\n")
            for result in results:
                if result.get('success'):
                    f.write(
                        f"{result.get('domain', '')},"
                        f"{result['tech']},1,"
                        f"{result['start']},{result['end']}\n"
                    )
