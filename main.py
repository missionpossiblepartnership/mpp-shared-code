from mppshared.config import SECTOR

if SECTOR == "aluminium":
    from aluminium.main_aluminium import main

    main()

elif SECTOR == "ammonia":
    from ammonia.main_ammonia import main

    main()
