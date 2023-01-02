"""Main script for the MPP solver, to run a sector change the SECTOR parameter to the appropriate one."""

# SECTOR = "aluminium"
SECTOR = "ammonia"
# SECTOR = "cement"


if SECTOR == "aluminium":
    from aluminium.main_aluminium import main

    main()

elif SECTOR == "ammonia":
    from ammonia.main_ammonia import main

    main()

elif SECTOR == "cement":
    from cement.main_cement import main

    main()

