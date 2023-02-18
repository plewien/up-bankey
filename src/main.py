from .config import Config
from .interface import TransactionCollection
from upbankapi import Client


# obtain access to the Up API
config = Config()
client = config.init_client(Client)

# add transactions
transactions = TransactionCollection(config)
transactions.add_from_up_api(client)
streams = transactions.as_streams()

# print results
with open('results.txt', 'w') as f:
	print(streams, file=f)
