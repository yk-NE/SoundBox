#!/usr/bin/env python3

from konashi import *
import logging
import asyncio
import argparse


async def main(duration):
    logging.info("Scan for Koshian for {} seconds".format(duration))
    ks = await Konashi.search(duration)
    logging.info("Number of Koshian devices discovered: {}".format(len(ks)))
    for k in ks:
        logging.info("  {}".format(k.name))


parser = argparse.ArgumentParser(description="Scan for Koshian devices and print the discovered list.")
parser.add_argument("DUR", type=float, help="The number of seconds to scan for")
args = parser.parse_args()

logging.basicConfig(level=logging.INFO)

loop = asyncio.get_event_loop()
loop.run_until_complete(main(args.DUR))
