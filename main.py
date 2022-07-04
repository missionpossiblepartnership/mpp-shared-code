from mppshared.config import SECTOR

if SECTOR == "aluminium":
    from aluminium.main_aluminium import main

    main()
