from upbankapi import Client, NotAuthorizedException

from stream import Expenses, Linker, TransactionCollection
from config import Config, TransactionType

# use the environment variable UP_TOKEN
client = Client()

# check the token is valid
try:
    user_id = client.ping()
    print("Authorized: " + user_id)
except NotAuthorizedException:
    print("The token is invalid")
    exit()

# get transactions between dates
accounts = client.accounts()
transactions = client.transactions(limit=4000)

# Filter misleading transactions
config = Config("config/personal.yaml")
transactions = config.filter(transactions)

incomes = TransactionCollection(config.income)
savings = TransactionCollection(config.savings)
expenses = Expenses(config.expense)

for t in transactions:
    type = config.classify(t)
    if type is TransactionType.Income:        incomes.insert(t)
    elif type is TransactionType.Expense:     expenses.insert(t)
    elif type is TransactionType.Savings:     savings.insert(t)
    else:
        if type is TransactionType.Ignore:
            message = "Ignoring transaction"
        else:
            message = "Unmatched transaction found"
        if t.settled_at is None:
            print("%s: %s" % (message, t))
        else:
            print("%s for %s: %s" % (message, t.settled_at.date(), t))

expenses.cleanup()
links = Linker(incomes, expenses, savings)

# Write the results to file...
with open('results.txt', 'w') as f:
    print(incomes, file=f)
    print(expenses, file=f)
    print(savings, file=f)
    print(links, file=f)
   

