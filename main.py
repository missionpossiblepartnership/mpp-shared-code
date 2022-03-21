from mppshared.model.carbon_budget import carbon_budget_test
from mppshared.solver.solve import solve


#! Only for development
def main():
    sector = "chemicals"
    solve(sector)


if __name__ == "__main__":
    main()
