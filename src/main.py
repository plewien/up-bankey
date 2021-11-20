from category import Categories
from config import Config
from stream import TransactionCollection
from upbankapi import Client, NotAuthorizedException

client = Client()
config = Config("config/personal.yaml")

# check the token is valid
try:
    print("Authorized: " + client.ping())
except NotAuthorizedException:
    print("The token is invalid")
    exit()

# get transactions between dates
transactions = client.transactions(limit=config.limit, since=config.since, until=config.until)
transactions = config.filter(transactions)

# Get data for categories
category_data = client.api("/categories")
categories = Categories(client, category_data)

# Process stream collections
streams = TransactionCollection(config, categories)
streams.addTransactions(transactions)
streams.cleanup()
streams.round()
streams.link()

# Write the results to file
with open('results.txt', 'w') as f:
    print(streams, file=f)

