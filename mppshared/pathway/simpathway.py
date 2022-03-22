import logging
import math
from collections import defaultdict

import pandas as pd
import plotly.express as px
from plotly.offline import plot
from plotly.subplots import make_subplots

from flow.calculate.calculate_availability import (
    update_availability_from_plant,
    make_empty_methanol_availability,
)
from flow.calculate.recalculate_variables import recalculate_variables
from flow.import_data.intermediate_data import IntermediateDataImporter
from flow.rank.rank_technologies import import_tech_data, rank_tech
from models.plant import PlantStack, create_plants
from util.util import flatten_columns
from config import (
    METHANOL_SUPPLY_TECH,
    METHANOL_TYPES,
    CHEMICALS,
    METHANOL_DEMAND_TECH,
    METHANOL_DEPENDENCY,
    METHANOL_AVAILABILITY_FACTOR,
    MODEL_SCOPE,
    METHANOL_MARGIN_USD,
    CARRYOVER_METHANOL_EMISSIONS,
    LOG_LEVEL,
)


logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)


class SimulationPathway:
    """Contains the current state of the simulated pathway, and methods to adjust that state"""

    def __init__(self, chemicals, start_year, end_year, pathway_name, sensitivity):
        self.pathway_name = pathway_name
        self.sensitivity = sensitivity
        self.chemicals = chemicals
        self.start_year = start_year
        self.end_year = end_year
        self.importer = IntermediateDataImporter(
            pathway=pathway_name, sensitivity=sensitivity, chemicals=chemicals
        )
        logger.debug("Getting plant capacities")
        self.df_plant_capacities = self.importer.get_plant_capacities()

        # logger.debug("Getting multi product ratios")
        # self.df_multi_product_ratio = self.importer.get_multi_product_ratio()

        logger.debug("Making plant stacks")
        self.stacks = self.make_initial_plant_stack()

        logger.debug("Getting demand")
        self.demand = self.importer.get_demand()

        logger.debug("Getting rankings")
        self.rankings = self._import_rankings()

        logger.debug("Getting emissions")
        self.emissions = self.importer.get_process_data(data_type="emissions")

        logger.debug("Getting constraint share")
        self.constraint_share = self.calculate_constraint_share(year=self.start_year)

        logger.debug("Getting availability")
        self.availability = self._import_availability()

        logger.debug("Getting tech")
        self.tech = self.importer.get_tech()

        logger.debug("Getting inputs")
        self.inputs = self.importer.get_inputs()

        logger.debug("Getting process data")
        self.process_data = self.importer.get_all_process_data()
        self.cost = self.importer.get_process_data(data_type="cost")
        self.inputs_pivot = self.importer.get_process_data(data_type="inputs")
        self.plant_specs = self.importer.get_plant_specs()

    def _import_availability(self):
        """Import availabilities of biomass, waste, etc"""
        df_availability = self.importer.get_availabilities()
        df_availability = df_availability.rename(columns={"value": "cap"})
        df_availability["used"] = 0

        # create chemical based availability columns
        for product in SECTOR(CHEMICALS):
            df_availability[f"{chemical}_cap"] = 0
            df_availability[f"{chemical}_used"] = 0
            for material_constraints in ["CO2 storage",
                                         "Biomass",
                                         "Waste water",
                                         "Municipal solid waste RdF",
                                         "Pyrolysis oil",
                                         "Bio-oils"]:

                # If there is no current (on purpose) stack, constraint share should be 0
                try:
                    constraint_share = self.constraint_share[chemical]
                except KeyError:
                    constraint_share = 0

                df_availability.loc[
                    (df_availability.name == material_constraints), f"{chemical}_cap"
                ] = (
                    constraint_share
                    * df_availability.loc[
                        (df_availability.name == material_constraints), "cap"
                    ]
                )

        for plant in self.get_stack(self.start_year).plants:
            logger.debug(plant)
            df_availability = update_availability_from_plant(
                df_availability=df_availability, plant=plant, year=self.start_year
            )

        df_methanol = make_empty_methanol_availability()

        df_availability = pd.concat([df_availability, df_methanol])
        return df_availability.query(f"year <= {self.end_year}")

    def update_methanol_availability_from_stack(self, year):
        """
        Update the available amount of green and black methanol that can be used for MTX

        Args:
            year: update the availability for this year
        """
        df = self.availability

        # Calculate the total amount of methanol green and black
        caps = {}
        for methanol_type in METHANOL_TYPES:
            cap = (
                self.get_stack(year=year).get_yearly_volume(
                    chemical="Methanol", methanol_type=methanol_type
                )
                * METHANOL_AVAILABILITY_FACTOR
                * 1e6
            )
            df.loc[(df.name == methanol_type) & (df.year == year), "cap"] = cap
            caps[methanol_type] = cap
            logger.debug(f"{methanol_type} capacity: {cap}")

        # Get the total Methanol demand (MTX + other), divide it pro rato over green/black
        non_mtx_demand = self.get_demand(chemical="Methanol", year=year, mtx=False)
        for methanol_type in METHANOL_TYPES:
            try:
                non_mtx_share = caps[methanol_type] / sum(caps.values())
            except ZeroDivisionError:
                non_mtx_share = 0

            non_mtx_amount = non_mtx_share * non_mtx_demand

            mtx_type = "Green" if "Green" in methanol_type else "Black"

            mtx_amount = self._get_mtx_demand(mtx_type=mtx_type, year=year)

            df.loc[(df.name == methanol_type) & (df.year == year), "used"] = (
                non_mtx_amount + mtx_amount
            ) * 1e6
        return self

    def _import_rankings(self, japan_only=False):
        """Import ranking for all chemicals and rank types from the CSVs"""
        rankings = defaultdict(dict)
        for rank_type in ["new_build", "retrofit", "decommission"]:
            for chemical in self.chemicals:
                df_rank = self.importer.get_ranking(
                    rank_type=rank_type,
                    chemical=chemical,
                    japan_only=(MODEL_SCOPE == "Japan"),
                )

                rankings[chemical][rank_type] = {}
                for year in range(self.start_year, self.end_year):
                    rankings[chemical][rank_type][year] = df_rank.query(
                        f"year == {year}"
                    )
        return rankings

    def save_rankings(self):
        for chemical in CHEMICALS:
            for ranking in ["decommission", "retrofit", "new_build"]:
                df = pd.concat(
                    [
                        pd.concat([df_ranking])
                        for year, df_ranking in self.rankings[chemical][ranking].items()
                    ]
                )
                self.importer.export_data(
                    df=df,
                    filename=f"{ranking}_post_rank.csv",
                    export_dir=f"ranking/{chemical}",
                )

    def save_demand(self):
        df = self.demand
        df = df[df.year <= self.end_year]
        df = df.pivot(index="chemical", columns="year", values="demand")
        self.importer.export_data(
            df=df,
            filename="demand_output.csv",
            export_dir="final/All",
        )

    def save_availability(self):
        df = self.availability
        self.importer.export_data(
            df=df,
            filename="availability_output.csv",
            export_dir="final/All",
        )

    def get_emissions(self, year, chemical=None):
        """Get  the emissions for a chemical in a year"""
        df = self.emissions.copy()

        return df.query(f"chemical == '{chemical}' & year == {year}").droplevel(
            ["chemical", "year"]
        )

    def get_cost(self, chemical, year):
        """Get  the cost for a chemical in a year"""
        df = self.cost
        return df.query(f"chemical == '{chemical}' & year == {year}").droplevel(
            ["chemical", "year"]
        )

    def get_inputs_pivot(self, chemical, year):
        """Get  the cost for a chemical in a year"""
        df = self.inputs_pivot
        return df.query(f"chemical == '{chemical}' & year == {year}").droplevel(
            ["chemical", "year"]
        )

    def get_specs(self, chemical, year):
        df = self.plant_specs
        return df.query(f"chemical == '{chemical}' & year == {year}").droplevel(
            ["chemical", "year"]
        )

    def get_demand(self, chemical, year, mtx=True, build_new=False):
        """
        Get the demand for a chemical in a year
        Args:
            build_new: overwrite demand after the new build step
            chemical: get for this chemical
            year: and this year
            mtx: also add mtx demand for methanol

        Returns:

        """
        df = self.demand
        demand = df.loc[(df.chemical == chemical) & (df.year == year), "demand"].item()

        # For Methanol, we have to take into account additional demand from MTO/MTP/MTA tech,
        if chemical == "Methanol" and mtx:
            logger.debug(f"Pre-demand: {demand}")
            mtx_demand = self._get_mtx_demand(mtx_type="both", year=year)
            demand += mtx_demand
            logger.debug(f"Post-demand: {demand} & MTX-demand: {mtx_demand}")
            if build_new:
                self.demand.loc[
                    (self.demand.chemical == chemical) & (self.demand.year == year),
                    "demand",
                ] = demand

        return demand

    def _get_mtx_demand(self, mtx_type, year):
        """
        Get methanol demand from MTX technologies

        Args:
            demand: Existing non-mto demand
            mtx_type: get for this methanol type
            year: for this year

        Returns:

        """

        if mtx_type in ["Black", "Green"]:
            methanol_tech = [tech for tech in METHANOL_DEMAND_TECH if mtx_type in tech]
        elif mtx_type == "both":
            methanol_tech = METHANOL_DEMAND_TECH
        else:
            raise ValueError("Has to be 'Black', 'Green', 'both'")

        # Get the capacity of MTO/MTP/MTA (Mton/annum)
        df_mtx = flatten_columns(
            self.stacks[year]
            .aggregate_stack()
            .query(f"technology.isin({methanol_tech})")
        )
        # Get the amount of Methanol used for each (Mton)
        df_inputs = self.get_inputs(year=year)
        df_inputs_mtx = df_inputs[
            (df_inputs.technology.isin(methanol_tech))
            & (df_inputs.name.str.contains("Methanol"))
        ].drop_duplicates(["region", "technology"])
        df = pd.merge(
            df_mtx,
            df_inputs_mtx,
            on=["technology", "region"],
            how="inner",
        )
        # Multiply by multi chemical total volume produced per tech
        mtx_totals = (
            self.df_multi_product_ratio[
                self.df_multi_product_ratio.technology.str.contains("MT")
            ]
            .drop_duplicates(["chemical", "technology"])
            .groupby("technology")
            .agg(total=("ratio", "sum"))
        )

        df = df.merge(mtx_totals, on="technology", how="left").fillna(1)
        df["input"] *= df["total"]

        # filter only for chemicals that we are running for
        chemical_list = list(set(CHEMICALS).intersection(set(METHANOL_DEPENDENCY)))
        df = df[df.chemical.isin(chemical_list)]
        return (df["yearly_volume_total"] * df["input"]).sum()

    def get_inputs(self, year, chemical=None):
        """Get the inputs for a chemical in a year"""
        df = self.inputs

        if chemical is not None:
            df = df[df.chemical == chemical]
        return df[df.year == year]

    def get_all_process_data(self, chemical, year):
        """Get all process data for a chemical in a year"""
        df = self.process_data
        df = df.reset_index(level=["chemical", "year"])
        return df[(df.chemical == chemical) & (df.year == year)]

    def get_ranking(self, chemical, year, rank_type):
        """Get ranking df for a specific year/chemical"""
        allowed_types = ["new_build", "retrofit", "decommission"]
        if rank_type not in allowed_types:
            raise ValueError(
                "Rank type %s not recognized, choose one of %s",
                rank_type,
                allowed_types,
            )

        return self.rankings[chemical][rank_type][year]

    def update_ranking(self, df_rank, chemical, year, rank_type):
        """Update ranking for a chemical, year, type"""
        self.rankings[chemical][rank_type][year] = df_rank

    def calculate_emission_stack(self, year):
        """
        Calculate emission level of the current stack
        """
        df_tech = self.get_stack(year).get_tech(
            id_vars=["technology", "chemical", "region"]
        )
        df_tech = df_tech.reset_index()
        df_tech = df_tech[df_tech.chemical.isin(CHEMICALS)]

        df_emissions = self.emissions
        df_emissions = df_emissions.reset_index()
        df_emissions = df_emissions[
            (df_emissions.year == year) & (df_emissions.chemical.isin(CHEMICALS))
        ]

        df_emission_stack = pd.merge(
            df_emissions, df_tech, how="right", on=["technology", "chemical", "region"]
        )

        emission_column = [
            column
            for column in df_emissions.columns
            if column.startswith("scope") or column == "total"
        ]

        for emission_type in emission_column:
            df_emission_stack[f"{emission_type}_stack_emissions"] = (
                df_emission_stack[emission_type] * df_emission_stack.number_of_plants
            )

        return df_emission_stack

    def calculate_constraint_share(self, year):
        """
        Calculate constraint share based on scope 1 emission
        """
        df_emission_stack = self.calculate_emission_stack(year)

        df_scope_1_emission_stack = df_emission_stack.groupby(["chemical"])[
            "scope_1_stack_emissions"
        ].sum()

        df_constraint_share = (
            df_scope_1_emission_stack / df_scope_1_emission_stack.sum()
        )
        df_constraint_share[df_constraint_share < 0.05] = 0.05

        return (df_constraint_share / df_constraint_share.sum()).to_dict()

    def copy_availability(self, year):
        df = self.availability

        for chemical in CHEMICALS:
            df.loc[df.year == year + 1, f"{chemical}_used"] = list(
                df.loc[df.year == year, f"{chemical}_used"]
            )

        df.loc[df.year == year + 1, "used"] = list(df.loc[df.year == year, "used"])
        df.loc[
            (df.year == year + 1) & (df.name.str.contains("Methanol")), "cap"
        ] = list(
            df.loc[(df.year == year + 1) & (df.name.str.contains("Methanol")), "cap"]
        )

    def update_availability(self, plant, year, remove=False):
        """
        Update the amount used of resources

        Args:
            year: current year
            remove:
            plant: update based on this plant
        """
        df = self.availability
        df = update_availability_from_plant(df, plant=plant, remove=remove, year=year)
        self.availability = df.round(1)
        return self

    def update_plant_status(self, year):
        for plant in self.stacks[year].plants:
            if year - plant.start_year >= plant.plant_lifetime:
                plant.plant_status = "old"
        return self

    def get_availability(self, year=None, name=None):
        df = self.availability.drop(columns=["unit"])

        if year is not None:
            df = df[df.year == year]

        if name is not None:
            df = df[df.name == name]

        return df

    def get_stack(self, year: int) -> PlantStack:
        return self.stacks[year]

    def update_stack(self, year, stack):
        self.stacks[year] = stack
        return self

    def copy_stack(self, year):
        """Copy this year's stack to next year"""
        old_stack = self.get_stack(year=year)
        new_stack = PlantStack(plants=old_stack.plants.copy())
        return self.add_stack(year=year + 1, stack=new_stack)

    def add_stack(self, year, stack):
        if year in self.stacks.keys():
            raise ValueError(
                "Cannot add stack, already present. Please use the update method"
            )

        self.stacks[year] = stack
        return self

    def get_capacity(self, year):
        """Get the capacity for a year"""
        stack = self.get_stack(year=year)
        return stack.get_capacity()

    def aggregate_stacks(self, chemical, this_year=False):
        return pd.concat(
            [
                stack.aggregate_stack(year=year, this_year=this_year, chemical=chemical)
                for year, stack in self.stacks.items()
            ]
        )

    def _validate_only_primary_chemical(self, df_production):
        multi_product_tech = set(self.df_multi_product_ratio.technology)
        df_production_multi = df_production[
            df_production.technology.isin(multi_product_tech)
        ].rename(columns={"chemical": "primary_chemical"})
        valid_options = df_production_multi.merge(
            self.df_multi_product_ratio,
            on=["technology", "primary_chemical", "region"],
        ).drop_duplicates(["technology", "primary_chemical", "region"])

        assert len(df_production_multi) == len(
            valid_options
        ), "Invalid options in the current production input"

    def _calculate_plants_from_production(self):
        """Calculate how many plants are there, based on current production"""

        # If an ethylene by-product, we should check how many pants there already are
        df_plant_size = self.importer.get_plant_sizes()

        # If Japan run, only create Japan plants
        df_production = self.importer.get_current_production(
            japan_only=(MODEL_SCOPE == "Japan")
        )

        # Validate we are only building tech for primary chemicals (to avoid duplication)
        self._validate_only_primary_chemical(df_production)

        df_plants = df_production.merge(df_plant_size, on=["technology", "chemical"])

        df_plants["number_of_plants"] = (
            (
                (df_plants["current_day_production"] / df_plants["capacity_factor"])
                / df_plants["assumed_plant_capacity"]
            )
            .round()
            .astype(int)
        )

        # Calculate number of old and new plants
        df_plants["number_of_plants_old"] = (
            df_plants["number_of_plants"] * df_plants["old_share"]
        ).astype(int)

        df_plants["number_of_plants_new"] = (
            df_plants["number_of_plants"] - df_plants["number_of_plants_old"]
        )
        return df_plants

    def make_initial_plant_stack(self):
        # Calculate how many plants we have to build
        df_plants = self._calculate_plants_from_production()

        # Merge input data on the plants
        df_process_data = self.importer.get_all_process_data()
        df_process_data = df_process_data.reset_index()
        df_process_data.columns = ["_".join(col) for col in df_process_data.columns]

        df_plants = df_plants.merge(
            df_process_data,
            left_on=["region", "chemical", "technology", "year"],
            right_on=["region__", "chemical__", "technology__", "year__"],
        )
        df_plants = df_plants.drop_duplicates(
            subset=["region", "chemical", "technology"]
        )

        # Build them
        all_plants = []
        for plant_status in ["old", "new"]:
            plants = df_plants.apply(
                lambda row: create_plants(
                    n_plants=row[f"number_of_plants_{plant_status}"],
                    technology=row["technology"],
                    region=row["region"],
                    chemical=row["chemical"],
                    # Assumption: old plants started 40 years ago, new ones just 20
                    start_year=self.start_year - 40
                    if plant_status == "old"
                    else self.start_year - 20,
                    biomass_yearly=row["inputs_Raw material_biomass_yearly"],
                    bio_oils_yearly=row["inputs_Raw material_bio_oils_yearly"],
                    pyrolysis_oil_yearly=row[
                        "inputs_Raw material_pyrolysis_oil_yearly"
                    ],
                    waste_water_yearly=row["inputs_Raw material_waste_water_yearly"],
                    municipal_solid_waste_rdf_yearly=row[
                        "inputs_Raw material_municipal_solid_waste_rdf_yearly"
                    ],
                    methanol_green_yearly=row[
                        "inputs_Raw material_methanol_green_yearly"
                    ],
                    methanol_black_yearly=row[
                        "inputs_Raw material_methanol_black_yearly"
                    ],
                    ccs_total=row["emissions__ccs_yearly"],
                    plant_lifetime=40,
                    plant_status=plant_status,
                    capacity_factor=row["spec__capacity_factor"],
                    df_plant_capacities=self.df_plant_capacities,
                ),
                axis=1,
            ).tolist()

            plants = [item for sublist in plants for item in sublist]
            all_plants += plants

        stack = PlantStack(plants=all_plants)
        return {self.start_year: stack}

    def plot_stacks(self, df_stack_agg, groupby, chemical):
        """
        Plot the resulting stacks over the years

        Args:
            df_stack_agg: The dataframe with stacks, aggregated per year / tech / region
            groupby: Groupby this variable, can be 'region' or 'technology'
            timeframe: Show results for this timeframe: 'this_year' or 'cumulative'
        """
        df = df_stack_agg.groupby(["year", groupby]).sum()[[("yearly_volume", "total")]]
        df.columns = df.columns.get_level_values(level=0)
        df = df.reset_index()

        fig = make_subplots()

        wedge_fig = px.area(df, color=groupby, x="year", y="yearly_volume")

        df_demand = self.demand.query(f"chemical=='{chemical}'").query(
            f"year <= {df.year.max()}"
        )
        demand_fig = px.line(df_demand, x="year", y="demand")
        demand_fig.update_traces(line=dict(color="Black", width=2, dash="dash"))

        demand_fig.update_traces(showlegend=True, name="Demand")
        fig.add_traces(wedge_fig.data + demand_fig.data)

        fig.layout.xaxis.title = "Year"
        fig.layout.yaxis.title = "Yearly volume (Mton / annum)"
        fig.layout.title = f"{groupby} over time for {chemical} - {self.pathway_name} - {self.sensitivity}"

        filename = f"output/{self.pathway_name}/{self.sensitivity}/final/{chemical}/{groupby}_over_time"

        plot(
            fig,
            filename=filename + ".html",
            auto_open=False,
        )

        fig.write_image(filename + ".png")

    def plot_methanol_availability(self, df_availability):

        df_availability = df_availability[
            (df_availability.name.isin(["Methanol - Black", "Methanol - Green"]))
            & (df_availability.region == "World")
        ]
        df_availability = df_availability.reset_index()

        fig = px.area(
            df_availability,
            x="year",
            y="cap",
            color="name",
            title=f"Methanol availability over time - {self.pathway_name} - {self.sensitivity}",
        )

        filename = f"output/{self.pathway_name}/{self.sensitivity}/final/Methanol/methanol_availability_over_time"

        plot(
            fig,
            filename=filename + ".html",
            auto_open=False,
        )

        fig.write_image(filename + ".png")

    def _get_weighted_average(
        self, df, vars, chemical, year, methanol_type: str = None, emissions=True
    ):
        """Calculate the weighted average of variables over regions/technologies"""
        df_plants = flatten_columns(
            self.stacks[year].aggregate_stack(chemical=chemical)
        )

        df = pd.merge(
            df_plants.reset_index(),
            df.reset_index(),
            on=["technology", "region"],
        )

        # Keep only black/green methanol
        if methanol_type is not None:
            df = df.query(f"technology.isin({METHANOL_SUPPLY_TECH[methanol_type]})")

        return (
            (
                df[vars].multiply(df["capacity_total"], axis="index").sum()
                / df["capacity_total"].sum()
            ).to_dict()
            if emissions
            else (
                df[vars].multiply(df["capacity_total"], axis="index").sum()
                / df["capacity_total"].sum()
            ).mean()
        )

    def get_average_emissions(
        self, chemical: str, year: int, methanol_type: str = None
    ) -> int:
        """
        Calculate emissions of a chemical, based on the plants that produce it in a year

        Returns:
            Emissions of producing the chemical in this year (averaged over technologies and locations)
        """
        df_emissions = self.get_emissions(chemical=chemical, year=year)

        return self._get_weighted_average(
            df=df_emissions,
            vars=["scope_1", "scope_2", "scope_3_upstream", "scope_3_downstream"],
            year=year,
            chemical=chemical,
            methanol_type=methanol_type,
            emissions=True,
        )

    def get_average_levelized_cost(
        self, chemical: str, year: int, methanol_type: str = None
    ) -> int:
        """
        Calculate levelized cost of a chemical, based on the plants that produce it in a year

        Returns:
            Levelized cost of producing the chemical in this year (averaged over technologies and locations)
        """

        df_lcox = self.get_cost(chemical=chemical, year=year)["lcox"]
        return self._get_weighted_average(
            df_lcox,
            vars=["new_build_brownfield"],
            year=year,
            chemical=chemical,
            methanol_type=methanol_type,
            emissions=False,
        )

    def get_total_volume(self, chemical: str, year: int, methanol_type=None):
        """Get total volume produced of a chemical in a year"""
        df_plants = flatten_columns(
            self.stacks[year].aggregate_stack(chemical=chemical)
        )
        # Keep only black/green methanol
        if methanol_type is not None:
            df_plants = df_plants.query(
                f"technology.isin({METHANOL_SUPPLY_TECH[methanol_type]})"
            )

        # Return total capacity in Mton/annum
        return df_plants["capacity_total"].sum()

    def re_rank_mtx_tech(self, year):
        """
        Re-rank MTX tech based on production of methanol in a year
        """

        # If there is no methanol tech, there is nothing to re-rank
        if self.get_stack(year).get_capacity(chemical="Methanol") == 0:
            return self

        dict_lcox = {}
        dict_emission = {}
        chemical = "Methanol"

        # Calculate LCOX and emissions of methanol and update availability
        for methanol_type in METHANOL_TYPES:
            dict_lcox[methanol_type] = self.get_average_levelized_cost(
                chemical=chemical, year=year, methanol_type=methanol_type
            )
            dict_emission[methanol_type] = self.get_average_emissions(
                chemical=chemical, year=year, methanol_type=methanol_type
            )

        # Add methanol margin
        for methanol_type, lcox in dict_lcox.items():
            if not math.isnan(dict_lcox[methanol_type]):
                dict_lcox[methanol_type] += METHANOL_MARGIN_USD

        # recalculate all variables for year+1 for all other technologies that need methanol
        df_emissions, df_tco = recalculate_variables(
            year=year + 1,
            dict_lcox=dict_lcox,
            dict_emission=dict_emission,
            pathway=self.pathway_name,
            sensitivity=self.sensitivity,
        )

        # replace/update the df_emissions in self
        if CARRYOVER_METHANOL_EMISSIONS:
            df_self_emissions = self.emissions
            df_emissions = df_self_emissions.query(
                f"~(year == {year} + 1 & technology == {METHANOL_DEMAND_TECH})"
            ).append(df_emissions)
            self.emissions = df_emissions
        else:
            df_emissions = self.emissions

        # replace/update the df_cost in self
        df_self_costs = self.cost
        df_cost = df_self_costs.query(
            f"~(year == {year} + 1 & technology == {METHANOL_DEMAND_TECH})"
        ).append(df_tco)
        self.cost = df_cost

        df_tech, df_tech_transitions = import_tech_data(
            pathway=self.pathway_name, sensitivity=self.sensitivity
        )

        # re-rank based on new variables
        self.make_re_rankings(
            df_cost=df_cost,
            df_emissions=df_emissions,
            df_tech=df_tech,
            df_tech_transitions=df_tech_transitions,
            year=year,
        )

        return self

    def make_re_rankings(
        self, df_cost, df_emissions, df_tech, df_tech_transitions, year
    ):
        """
        Make rankings for new builds, retrofits and decommission for a year.
        This is used to re-rank technologies based on the new methanol stack (with associated prices and emissions).

        Uses the calculated variables from `calulate_variables`, data on allowed tech transitions,
        and the pathway configuration and tech_asc to specify the rankings.

        """

        for rank_type in ["retrofit", "new_build", "decommission"]:
            df_rank = rank_tech(
                df_tech_transitions=df_tech_transitions,
                df_tech=df_tech,
                df_cost=df_cost,
                df_emissions=df_emissions,
                rank_type=rank_type,
                year=year + 1,
                pathway=self.pathway_name,
            )

            # Update ranking for each chemical
            for chemical in self.chemicals:
                df_chemical = df_rank.query(f"chemical == '{chemical}'")
                self.update_ranking(
                    df_rank=df_chemical,
                    chemical=chemical,
                    year=year,
                    rank_type=rank_type,
                )

    def filter_tech_primary_chemical(self, df_tech, chemical, col="technology"):
        """
        Filter technologies in a dataframe to keep only the technologies for which this chemical is the primary chemical
        Args:
            df_tech: technologies dataframe
            chemical: chemical we want to filter for
            col: column where the technologies are in

        Returns:

        """
        if ("technology" in df_tech.columns) and ("destination" in df_tech.columns):
            df_tech.drop(columns="technology", inplace=True)

        df = self.df_multi_product_ratio
        primary_chemicals = df.drop_duplicates(["technology", "primary_chemical"])[
            ["technology", "primary_chemical"]
        ]
        technologies = primary_chemicals[primary_chemicals.primary_chemical == chemical]

        multi_product_idx = df_tech[col].isin(primary_chemicals.technology)
        df_single = df_tech[~multi_product_idx]
        df_multi = df_tech[multi_product_idx]

        df_multi = df_multi.merge(
            technologies,
            left_on=[col, "chemical"],
            right_on=["technology", "primary_chemical"],
        )
        return pd.concat([df_multi, df_single])
