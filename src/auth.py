from upbankapi import Client, NotAuthorizedException

from stream import ExpensesCollection, Linker, TransactionCollection
from config import Config, TransactionType
from transaction import TransactionFactory

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
factory = TransactionFactory()
transactions = config.filter(transactions)

incomes = TransactionCollection(config.income)
savings = TransactionCollection(config.savings)
expenses = ExpensesCollection(config.expense)

for t in factory.to_generic_transaction_list(transactions):
    type = config.classify(t)
    if type is TransactionType.Income:        incomes.insert(t)
    elif type is TransactionType.Expense:     expenses.insert(t)
    elif type is TransactionType.Savings:     savings.insert(t)
    else:
        if type is TransactionType.Ignore:
            message = "Ignoring transaction"
        else:
            message = "Unmatched transaction found"
        print("%s for %s" % (message, t))

expenses.cleanup()
links = Linker(incomes, expenses, savings)

incomes.round()
expenses.round()
savings.round()

# Write the results to file...
with open('results.txt', 'w') as f:
    print(incomes, file=f)
    print(expenses, file=f)
    print(savings, file=f)
    print(links, file=f)
