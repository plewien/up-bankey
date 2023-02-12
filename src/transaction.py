from upbankapi.models import Transaction, OwnershipType
from .protocol import Account, Client
from datetime import datetime
from numbers import Number
from typing import Optional
from enum import Enum

# 1. Obtain data from source(s)
# 2. Read into generic transaction array
# 3. Parse into streams
# 4. Format into SankeyMatic

AccountType = Enum('AccountType', ['JOINT', 'PERSONAL', 'EXTERNAL'])

class GenericTransaction:
	def __init__(self, date, description, amount, currency, source=None, destination=None, category=None, parentCategory=None, tags=list(), message=None):
		self.date: datetime = date
		self.description: str = description
		self.amount: float = amount
		self.currency: str = currency
		self.source: Optional[AccountType] = source
		self.destination: Optional[AccountType] = destination
		self.category: Optional[str] = category
		self.parentCategory: Optional[str] = parentCategory
		self.tags: list[str] = tags
		self.message: Optional[str] = message

	def __repr__(self):
		return f"<Transaction {self.date}: {self.amount} {self.currency} [{self.description}]>"

	@property
	def total(self) -> float:
		return self.amount # TODO: Determine split

	@property
	def internal(self) -> bool:
		return self.source == self.destination and self.source in (AccountType.JOINT, AccountType.PERSONAL)
	
	@property
	def requires_splitting(self) -> bool:
		return {self.source, self.destination} == {AccountType.PERSONAL, AccountType.JOINT}


class TransactionHelper:
	def __init__(self, client : Client):
		self.accounts = {account.id : account for account in client.accounts()}

	@staticmethod
	def account_type(account : Account):
		if account.ownership_type == OwnershipType.JOINT:
			return AccountType.JOINT
		if account.ownership_type == OwnershipType.INDIVIDUAL:
			return AccountType.PERSONAL

	def source_account_type(self, transaction : Transaction):
		relationships = transaction._raw_response['relationships']
		id = relationships['account']['data']['id']
		return TransactionHelper.account_type(self.accounts[id])

	def destination_account_type(self, transaction : Transaction):
		relationships = transaction._raw_response['relationships']
		if relationships['transferAccount']['data']:
			id = relationships['transferAccount']['data']['id']
			if id in self.accounts:  # Check if transaction involves some else's upbank account
				return TransactionHelper.account_type(self.accounts[id])
		return AccountType.EXTERNAL

	@staticmethod
	def category(transaction : Transaction):
		return transaction.category.category().name if transaction.category else None

	@staticmethod
	def parent_category(transaction : Transaction):
		category = transaction.category
		if not category or not category.parent:
			return None
		full_category = category.parent.category()
		return full_category.name


class TransactionFactory:
	def __init__(self, client : Client):
		self.helper = TransactionHelper(client)

	def to_generic_transactions(self, sourceList):
		return [self.to_generic_transaction(source) for source in sourceList]

	def to_generic_transaction(self, *argv):
		if isinstance(argv[0], Transaction):
			return self._create_from_up(argv[0])
		if len(argv) == 2 and isinstance(argv[0], Number) and isinstance(argv[1], str):
			return self._create_from_value(argv[0], argv[1])
		print("Warning: No matching transaction type found for arguments", str(argv))
		return None

	def _create_from_up(self, transaction : Transaction):
		return GenericTransaction(
			date = transaction.created_at,
			description = transaction.description,
			amount = transaction.amount,
			currency = transaction.currency,
			source = self.helper.source_account_type(transaction),
			destination = self.helper.destination_account_type(transaction),
			category = TransactionHelper.category(transaction),
			parentCategory = TransactionHelper.parent_category(transaction),
			tags = transaction.tags,
			message = transaction.message
		)

	def _create_from_value(self, amount : float, description):
		return GenericTransaction(
			date = datetime.now(),
			description = description,
			amount = amount,
			currency = "AUD"  # TODO: Default currency
		)
