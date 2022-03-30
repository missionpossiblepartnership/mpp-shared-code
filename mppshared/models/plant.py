"""Plant and plant stack classes, code adapted from MCC"""
from uuid import uuid4

import pandas as pd

from mppshared.config import (
    DECOMMISSION_RATES,
    CUF_LOWER_THRESHOLD,
)  # , METHANOL_SUPPLY_TECH

from mppshared.utility.utils import first


class Plant:
    def __init__(
        self,
        product,
        technology,
        region,
        start_year,
        capacity_factor,
        plant_lifetime,
        df_plant_capacities,
        type_of_tech="Initial",
        retrofit=False,
        plant_status="new",
    ):
        self.product = product
        self.technology = technology
        self.region = region
        self.start_year = start_year
        self.df_plant_capacities = df_plant_capacities
        self.capacities = self.import_capacities()
        self.capacity_factor = capacity_factor
        self.uuid = uuid4().hex
        self.retrofit = retrofit
        self.plant_status = plant_status
        self.plant_lifetime = plant_lifetime
        self.type_of_tech = type_of_tech

    @property
    def byproducts(self):
        return [k for (k, v) in self.capacities.items() if v != 0]

    def get_age(self, year):
        return year - self.start_year

    def import_capacities(self) -> dict:
        """Import plant capacities for the different products that this plant produces"""
        df = self.df_plant_capacities

        # Find the capacities
        df_capacities = df[
            (df.technology == self.technology) & (df.region == self.region)
        ]

        return {
            product: df_capacities.loc[
                df_capacities["product"] == product, "annual_production_capacity"
            ].values[0]
            for product in df_capacities["product"]
        }

    def get_capacity(self, product=None):
        """Get plant capacity"""
        return self.capacities.get(product or self.product, 0)

    def get_annual_production(self, product):
        return self.get_capacity(product) * self.capacity_factor


def create_plants(n_plants: int, df_plant_capacities: pd.DataFrame, **kwargs) -> list:
    """Convenience function to create a list of plant at once"""
    return [
        Plant(df_plant_capacities=df_plant_capacities, **kwargs)
        for _ in range(n_plants)
    ]


class PlantStack:
    def __init__(self, plants: list):
        self.plants = plants
        # Keep track of all plants added this year
        self.new_ids = []

    def remove(self, remove_plant):
        self.plants.remove(remove_plant)

    def append(self, new_plant):
        self.plants.append(new_plant)
        self.new_ids.append(new_plant.uuid)

    def empty(self):
        """Return True if no plant in stack"""
        return not self.plants

    def filter_plants(self, sector=None, region=None, technology=None, product=None):
        """Filter plant based on one or more criteria"""
        plants = self.plants
        if sector is not None:
            plants = filter(lambda plant: plant.sector == sector, plants)
        if region is not None:
            plants = filter(lambda plant: plant.region == region, plants)
        if technology is not None:
            plants = filter(lambda plant: plant.technology == technology, plants)
        if product is not None:
            plants = filter(
                lambda plant: (plant.product == product)
                or (product in plant.byproducts),
                plants,
            )
        # Commenting out the following lines as it is not cleare if we will need
        # something similar for ammonia and aluminium
        # if methanol_type is not None:
        #     plant = filter(
        #         lambda plant: plant.technology in METHANOL_SUPPLY_TECH[methanol_type],
        #         plant,
        #     )

        return list(plants)

    def get_fossil_plants(self, product):
        return [
            plant
            for plant in self.plants
            if (
                (plant.technology in DECOMMISSION_RATES.keys())
                and (plant.product == product)
            )
        ]

    def get_capacity(self, product, methanol_type=None, **kwargs):
        """Get the plant capacity, optionally filtered by region, technology, product"""
        if methanol_type is not None:
            kwargs["methanol_type"] = methanol_type

        plants = self.filter_plants(product=product, **kwargs)
        return sum(plant.get_capacity(product) for plant in plants)

    def get_annual_production(self, product, methanol_type=None, **kwargs):
        """Get the yearly volume, optionally filtered by region, technology, product"""
        if methanol_type is not None:
            kwargs["methanol_type"] = methanol_type

        plants = self.filter_plants(product=product, **kwargs)
        return sum(plant.get_annual_production(product=product) for plant in plants)

    def get_tech(self, id_vars, product=None):
        """
        Get technologies of this stack

        Args:
            id_vars: aggregate by these variables

        Returns:
            Dataframe with technologies
        """

        df = pd.DataFrame(
            [
                {
                    "product": plant.product,
                    "technology": plant.technology,
                    "region": plant.region,
                    "retrofit": plant.retrofit,
                    "capacity": plant.get_capacity(product),
                }
                for plant in self.plants
            ]
        )
        try:
            return df.groupby(id_vars).agg(
                capacity=("capacity", "sum"), number_of_plants=("capacity", "count")
            )
        except KeyError:
            # There are no plant
            return pd.DataFrame()

    def get_new_plant_stack(self):
        return PlantStack(
            plants=[plant for plant in self.plants if plant.plant_status == "new"]
        )

    def get_old_plant_stack(self):
        return PlantStack(
            plants=[plant for plant in self.plants if plant.plant_status == "old"]
        )

    def get_unique_tech(self, product=None):
        if product is not None:
            plants = self.filter_plants(product=product)
        else:
            plants = self.plants

        valid_combos = {(plant.technology, plant.region) for plant in plants}
        return pd.DataFrame(valid_combos, columns=["technology", "region"])

    def get_regional_contribution(self):
        df_agg = (
            pd.DataFrame(
                [
                    {
                        "region": plant.region,
                        "capacity": plant.get_capacity(),
                    }
                    for plant in self.plants
                ]
            )
            .groupby("region", as_index=False)
            .sum()
        )
        df_agg["proportion"] = df_agg["capacity"] / df_agg["capacity"].sum()
        return df_agg

    def aggregate_stack(self, product=None, year=None, this_year=False):

        # Filter for product
        if product is not None:
            plants = self.filter_plants(product=product)
        else:
            plants = self.plants

        # Keep only plant that were built in a year
        if this_year:
            plants = [plant for plant in plants if plant.uuid in self.new_ids]

        # Calculate capacity and number of plant for new and retrofit
        try:
            df_agg = (
                pd.DataFrame(
                    [
                        {
                            "capacity": plant.get_capacity(product),
                            "yearly_volume": plant.get_annual_production(
                                product=product
                            ),
                            "technology": plant.technology,
                            "region": plant.region,
                            "retrofit": plant.retrofit,
                        }
                        for plant in plants
                    ]
                )
                .groupby(["technology", "region", "retrofit"], as_index=False)
                .agg(
                    capacity=("capacity", "sum"),
                    number_of_plants=("capacity", "count"),
                    yearly_volume=("yearly_volume", "sum"),
                )
            ).fillna(0)

            # Helper column to avoid having True and False as column names
            df_agg["build_type"] = "new_build"
            df_agg.loc[df_agg.retrofit, "build_type"] = "retrofit"

            df = df_agg.pivot_table(
                values=["capacity", "number_of_plants", "yearly_volume"],
                index=["region", "technology"],
                columns="build_type",
                dropna=False,
                fill_value=0,
            )

            # Make sure all columns are present
            for col in [
                ("capacity", "retrofit"),
                ("capacity", "new_build"),
                ("number_of_plants", "retrofit"),
                ("number_of_plants", "new_build"),
                ("yearly_volume", "retrofit"),
                ("yearly_volume", "new_build"),
            ]:
                if col not in df.columns:
                    df[col] = 0

            # Add totals
            df[("capacity", "total")] = (
                df[("capacity", "new_build")] + df[("capacity", "retrofit")]
            )
            df[("number_of_plants", "total")] = (
                df[("number_of_plants", "new_build")]
                + df[("number_of_plants", "retrofit")]
            )
            df[("yearly_volume", "total")] = (
                df[("yearly_volume", "new_build")] + df[("yearly_volume", "retrofit")]
            )

        # No plant exist
        except KeyError:
            return pd.DataFrame()

        df.columns.names = ["quantity", "build_type"]

        # Add year to index if passed (to help identify chunks)
        if year is not None:
            df["year"] = year
            df = df.set_index("year", append=True)

        return df

    def get_tech_plant_stack(self, technology: str):
        return PlantStack(
            plants=[plant for plant in self.plants if plant.technology == technology]
        )


def make_new_plant(
    best_transition, df_process_data, year, retrofit, product, df_plant_capacities
):
    """
    Make a new plant, based on a transition entry from the ranking dataframe

    Args:
        best_transition: The best transition (destination is the plant to build)
        df_process_data: The inputs dataframe (needed for plant specs)
        year: Build the plant in this year
        retrofit: Plant is retrofitted from an old plant

    Returns:
        The new plant
    """
    df_process_data = df_process_data.reset_index()
    spec = df_process_data[
        (df_process_data.sector == best_transition["sector"])
        & (  # add the sector to the specs to map
            df_process_data.technology == best_transition["destination"]
        )
        & (df_process_data.year == best_transition["year"])
        & (df_process_data.region == best_transition["region"])
    ]

    # Map tech type back from ints
    types_of_tech = {1: "Initial", 2: "Transition", 3: "End-state"}
    type_of_tech = types_of_tech[best_transition["type_of_tech_destination"]]

    return Plant(
        sector=first(spec["sector"]),
        product=product,
        technology=first(spec["technology"]),
        region=first(spec["region"]),
        start_year=year,
        retrofit=retrofit,
        ccs_total=first(spec["emissions", "", "ccs_total"]),
        plant_lifetime=first(spec["spec", "", "plant_lifetime"]),
        capacity_factor=first(spec["spec", "", "capacity_factor"]),
        type_of_tech=type_of_tech,
        df_plant_capacities=df_plant_capacities,
    )


def get_assets_eligible_for_decommission(self) -> list():
    """Return a list of Plants from the PlantStack that are eligible for decommissioning

    Returns:
        list of Plants
    """
    # Filter for CUF < threshold
    #! For development only
    cuf_placeholder = 0.95
    candidates = filter(
        lambda plant: plant.capacity_factor < cuf_placeholder, self.plants
    )

    # TODO: filter based on asset age

    return candidates
