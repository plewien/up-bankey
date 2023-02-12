from .config import Config
from .stream import TransactionCollection
from upbankapi import Client, NotAuthorizedException
import sys

# generate user configuration
if len(sys.argv) > 1:
	config = Config(sys.argv[1])
else:
	config = Config()

# obtain access to the Up API
client = Client()
try:
	print("Authorized: " + client.ping())
except NotAuthorizedException:
	print("The token is invalid")
	exit()

# create and write results to file
streams = TransactionCollection(client, config).process()
with open('results.txt', 'w') as f:
	print(streams, file=f)
