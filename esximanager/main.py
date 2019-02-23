import sys
import logging
import argparse
from esximanager.shutdown import Shutdown

# For the time-being, we are just logging to the console
logging.basicConfig(
    format='%(asctime)s,%(levelname)s,%(module)s,%(message)s',
    level=logging.INFO,
    stream=sys.stdout)

logger = logging.getLogger(__name__)

def parse_args():
    parent_parser = argparse.ArgumentParser()
    child_parsers = parent_parser.add_subparsers()

    # Default set of args for all child parsers ###############################
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        '--esxihost',
        type=str,
        required=True,
        help='esxi host to shutdown')

    shared.add_argument(
        '--loglevel',
        type=str,
        default='INFO',
        help='logging output level configuration')

    shared.add_argument(
        '--dryrun',
        action='store_true',
        help='Run in dryrun mode')

    # Shutdown ################################################################
    parser = child_parsers.add_parser(
        'shutdown',
        parents=[shared],
        help='Shuts down the esxi by first powering off vms and then the host itself')
    parser.set_defaults(funct=shutdown)

    return parent_parser.parse_args()

def shutdown(args, logger):
    shutdown = Shutdown(args, logger)
    shutdown.shutdown()

def main():
    args = parse_args()
    # Reconfigure logger
    logger.setLevel(args.loglevel.upper())
    args.funct(args, logger)

###############################################################################
# MAIN
###############################################################################

if __name__ == '__main__':
    main()