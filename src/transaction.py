from .config import CollectionConfig, TransactionType
from .protocol import Transaction
from datetime import datetime
from typing import Optional, List, Mapping
from enum import Enum


AccountType = Enum('AccountType', ['JOINT', 'PERSONAL', 'EXTERNAL'])

class GenericTransaction(Transaction):
	def __init__(self,
			description,
			amount,
			date=datetime.now(),
			currency="AUD",
			source=None,
			destination=None,
			category=None,
			parentCategory=None,
			tags=list(),
			message=None):
		self.description = description
		self.amount: float = amount
		self.currency: str = currency
		self.date: datetime = date
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


class TransactionAliaser:
	def __init__(self, config : CollectionConfig):
		self.config = config

	def get_alias(self, transaction : GenericTransaction):
		alias = self.get_alias_by_tag(transaction)
		if alias is not None:
			return alias
		alias = self.get_alias_by_account(transaction)
		if alias is not None:
			return alias
		return transaction.description

	def get_alias_by_tag(self, transaction : GenericTransaction):
		return next((self.config.tags.get_alias(tag) for tag in transaction.tags), None)
	
	def get_alias_by_account(self, transaction : GenericTransaction):		
		return self.config.accounts.get_alias(transaction.description)


class TransactionMatcher:
	def __init__(self, config : CollectionConfig):
		self.config = config

	def match(self, transaction : GenericTransaction) -> bool:
		return self.match_by_tag(transaction) or self.match_by_account(transaction)

	def match_by_tag(self, transaction : GenericTransaction) -> bool:
		return any([self.config.tags.contains(tag) for tag in transaction.tags])

	def match_by_account(self, transaction : GenericTransaction) -> bool:
		return self.config.accounts.contains(transaction.description)


class TransactionClassifier:
	def __init__(self, config : Mapping[TransactionType, CollectionConfig]):
		self.matchers = {type : TransactionMatcher(collection) for type, collection in config.items()}

	def classify(self, transaction : GenericTransaction) -> TransactionType:
		classifierOrder = [
			self.classify_by_tag,
			self.classify_by_category_presence,
			self.classify_by_source_and_destination,
			self.classify_by_account,
			self.classify_by_postive_value,
		]
		for classifier in classifierOrder:
			classification = classifier(transaction)
			if classification is not TransactionType.Unknown:
				return classification
		return TransactionType.Unknown

	def classify_by_tag(self, transaction : GenericTransaction) -> TransactionType:
		for type, collection in self.matchers.items():
			if collection.match_by_tag(transaction):
				return type
		return TransactionType.Unknown

	def classify_by_account(self, transaction : GenericTransaction) -> TransactionType:
		for type, collection in self.matchers.items():
			if collection.match_by_account(transaction):
				return type
		return TransactionType.Unknown

	def classify_by_source_and_destination(self, transaction : GenericTransaction) -> TransactionType:
		if transaction.internal:
			return TransactionType.Ignore
		return TransactionType.Unknown

	def classify_by_category_presence(self, transaction : GenericTransaction) -> TransactionType:
		if transaction.category:
			return TransactionType.Expense
		return TransactionType.Unknown

	def classify_by_postive_value(self, transaction : GenericTransaction) -> TransactionType:
		if transaction.amount > 0:
			return TransactionType.Income
		return TransactionType.Unknown
