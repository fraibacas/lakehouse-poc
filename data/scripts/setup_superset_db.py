
import logging
from superset import SupersetConfigurator


logger = logging.getLogger(__name__)

def main(superset_url = "http://superset:8088"):
    configurator = SupersetConfigurator(superset_url)
    configurator.create_trino_db()


def set_up_logger():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
                        datefmt='%Y/%m/%d %H:%M:%S')


if __name__ == "__main__":
    set_up_logger()
    main()