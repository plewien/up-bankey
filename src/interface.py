from typing import List
from upbankapi.models import OwnershipType

from .config import Config
from .protocol import Account, Client as ClientProtocol, Transaction
from .stream import StreamCollection
from .transaction import GenericTransaction, AccountType


class UpBankApiHelper:
	def __init__(self, client : ClientProtocol):
		# Cache the accounts and categories to avoid triggering API rate-limit
		self.accounts = {account.id : account for account in client.accounts()}
		self.categories = {category.id : category for category in client.categories()}
		self.client = client

	@staticmethod
	def account_type(account : Account):
		if account.ownership_type == OwnershipType.JOINT:
			return AccountType.JOINT
		if account.ownership_type == OwnershipType.INDIVIDUAL:
			return AccountType.PERSONAL

	def transactions(self, config : Config):
		up_transactions = self.client.transactions(limit=config.limit,
										page_size=config.pagesize,
										since=config.since,
										until=config.until)
		return self.to_generic_transactions(up_transactions)

	def to_generic_transactions(self, transactionList : List[Transaction]):
		return [self.to_generic_transaction(source) for source in transactionList]

	def to_generic_transaction(self, transaction : Transaction):
		return GenericTransaction(
			date = transaction.created_at,
			description = transaction.description,
			amount = transaction.amount,
			currency = transaction.currency,
			source = self.source_account_type(transaction),
			destination = self.destination_account_type(transaction),
			category = self.category(transaction),
			parentCategory = self.parent_category(transaction),
			tags = transaction.tags,
			message = transaction.message
		)

	def source_account_type(self, transaction : Transaction):
		relationships = transaction._raw_response['relationships']
		id = relationships['account']['data']['id']
		return UpBankApiHelper.account_type(self.accounts[id])

	def destination_account_type(self, transaction : Transaction):
		relationships = transaction._raw_response['relationships']
		if relationships['transferAccount']['data']:
			id = relationships['transferAccount']['data']['id']
			if id in self.accounts:  # Check if transaction involves some else's upbank account
				return UpBankApiHelper.account_type(self.accounts[id])
		return AccountType.EXTERNAL

	def category(self, transaction : Transaction):
		if transaction.category:
			return self.categories[transaction.category.id].name
		return None

	def parent_category(self, transaction : Transaction):
		if transaction.category and transaction.category.parent:
			return self.categories[transaction.category.parent.id].name
		return None


class TransactionCollection:
	def __init__(self, config : Config):
		self.config : Config = config
		self.transactions : List(GenericTransaction) = []

	def add_from_up_api(self, client : ClientProtocol):
		helper = UpBankApiHelper(client)
		self.transactions.extend(helper.transactions(self.config))

	def as_streams(self):
		streams = StreamCollection(self.config.collections)
		streams.add_transactions(self.transactions)
		return streams.cleanup().link()
