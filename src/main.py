from .config import Config
from .interface import TransactionCollection
from upbankapi import Client


# obtain access to the Up API
config = Config()
client = config.up_api.init_client(Client)

# add transactions
transactions = TransactionCollection(config)
transactions.add_from_up_api(client)
streams = transactions.as_streams()

# print results
config.print_to_file(streams)
