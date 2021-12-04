from category import Categories
from config import Config
from stream import TransactionCollection
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

# get transactions between dates
transactions = client.transactions(limit=config.limit, 
									page_size=config.pagesize, 
									since=config.since, 
									until=config.until)

# Get data for categories
category_data = client.api("/categories")
categories = Categories(client, category_data)

# Process stream collections
streams = TransactionCollection(config, categories)
streams.add_transactions(transactions)
streams.cleanup()
streams.link()

# Write the results to file
with open('results.txt', 'w') as f:
	print(streams, file=f)
