"""Test Pydantic models"""
from stdn_agentic.agents import (
    ComponentList,
    ComponentMaterials,
    ComponentMaterialsList,
    CountryPercentage,
    CountryList
)

print("Testing Pydantic models...")

# Test ComponentList
components = ComponentList(component_list=["display", "battery", "processor"])
print(f"✓ ComponentList: {len(components.component_list)} components")

# Test ComponentMaterials
mat = ComponentMaterials(
    component="battery",
    materials=["lithium", "cobalt", "nickel"]
)
print(f"✓ ComponentMaterials: {mat.component} with {len(mat.raw_materials)} materials")

# Test ComponentMaterialsList
mat_list = ComponentMaterialsList(
    component_list=[
        {"component": "display", "materials": ["glass", "indium"]},
        {"component": "battery", "materials": ["lithium", "cobalt"]}
    ]
)
print(f"✓ ComponentMaterialsList: {len(mat_list.component_list)} components")

# Test CountryPercentage
country = CountryPercentage(
    country="China",
    meas_unit="metric tons",
    amount=100000,
    percentage=65.5
)
print(f"✓ CountryPercentage: {country.country} at {country.percentage}%")

# Test CountryList
countries = CountryList(
    country_list=[
        {"country": "China", "meas_unit": "tons", "amount": 100000, "percentage": 65},
        {"country": "Australia", "meas_unit": "tons", "amount": 42000, "percentage": 27}
    ]
)
print(f"✓ CountryList: {len(countries.country_list)} countries")

print("\n✓ All model tests passed!")
